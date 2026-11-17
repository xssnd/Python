#!/usr/bin/env python3
"""Linux CPU temperature monitor with sensors, dashboard, alerts, and JSON output."""
from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import psutil
except ImportError:
    psutil = None

BASE_DIR = Path(__file__).resolve().parent
LOG = logging.getLogger("temperature-monitor")
ANSI = {"reset": "\033[0m", "bold": "\033[1m", "green": "\033[32m",
        "yellow": "\033[33m", "red": "\033[31m", "cyan": "\033[36m",
        "dim": "\033[2m"}
TEMP_RE = re.compile(r"^\s*([^:]+):\s*([+-]?\d+(?:\.\d+)?)\s*°?C\b", re.I)


@dataclass
class Temperature:
    sensor: str
    label: str
    celsius: float
    source: str


@dataclass
class ThrottleCounter:
    name: str
    count: int
    path: str


def read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None


def read_sensors(command: str = "sensors", timeout: int = 8) -> list[Temperature]:
    """Parse lm-sensors human-readable output; ignore limit/threshold lines."""
    executable = shutil.which(command)
    if not executable:
        return []
    try:
        result = subprocess.run([executable], capture_output=True, text=True,
                                timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        LOG.warning("Could not execute sensors: %s", exc)
        return []
    if result.returncode != 0:
        LOG.warning("sensors exited with status %s: %s", result.returncode,
                    (result.stderr or "").strip()[:300])
        return []
    chip = "lm-sensors"
    readings: list[Temperature] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.endswith(":") and not TEMP_RE.match(line):
            chip = stripped[:-1]
            continue
        match = TEMP_RE.match(line)
        if match:
            label, value = match.groups()
            readings.append(Temperature(chip, label.strip(), float(value), "sensors"))
    return readings


def read_hwmon() -> list[Temperature]:
    readings: list[Temperature] = []
    for hwmon in sorted(Path("/sys/class/hwmon").glob("hwmon*")):
        chip = read_text(hwmon / "name") or hwmon.name
        for inp in sorted(hwmon.glob("temp*_input")):
            raw = read_text(inp)
            if raw is None:
                continue
            try:
                value = float(raw) / 1000
            except ValueError:
                continue
            stem = inp.name.removesuffix("_input")
            label = read_text(hwmon / f"{stem}_label") or stem
            readings.append(Temperature(chip, label, value, "hwmon"))
    return readings


def read_psutil() -> list[Temperature]:
    if psutil is None or not hasattr(psutil, "sensors_temperatures"):
        return []
    try:
        groups = psutil.sensors_temperatures(fahrenheit=False) or {}
    except (OSError, RuntimeError):
        return []
    return [Temperature(chip, entry.label or chip, float(entry.current), "psutil")
            for chip, entries in groups.items() if entry.current is not None]


def collect_temperatures(command: str = "sensors") -> list[Temperature]:
    """Prefer sensors output and supplement it with non-duplicate OS readings."""
    readings = read_sensors(command) + read_hwmon() + read_psutil()
    unique: dict[tuple[str, str, float], Temperature] = {}
    for item in readings:
        key = (item.sensor.casefold(), item.label.casefold(), round(item.celsius, 1))
        unique.setdefault(key, item)
    return sorted(unique.values(), key=lambda item: item.celsius, reverse=True)


def read_throttle_counters() -> list[ThrottleCounter]:
    counters = []
    root = Path("/sys/devices/system/cpu")
    for cpu_dir in sorted(root.glob("cpu[0-9]*")):
        for filename in ("core_throttle_count", "package_throttle_count"):
            path = cpu_dir / "thermal_throttle" / filename
            raw = read_text(path)
            if raw is not None:
                try:
                    counters.append(ThrottleCounter(f"{cpu_dir.name}:{filename}", int(raw), str(path)))
                except ValueError:
                    pass
    return counters


def load_config(path: Path) -> dict:
    config = {
        "interval_seconds": 5, "warning_celsius": 80.0, "critical_celsius": 90.0,
        "consecutive_samples": 2, "cooldown_seconds": 300,
        "log_file": "temperature_monitor.log",
        "alerts": {"telegram": {"enabled": False}, "discord": {"enabled": False}},
    }
    if path.exists():
        user = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(user, dict):
            raise ValueError("Configuration root must be a JSON object")
        config.update({k: v for k, v in user.items() if k != "alerts"})
        config["alerts"].update(user.get("alerts", {}))
    config["interval_seconds"] = int(config["interval_seconds"])
    config["consecutive_samples"] = int(config["consecutive_samples"])
    config["cooldown_seconds"] = int(config["cooldown_seconds"])
    config["warning_celsius"] = float(config["warning_celsius"])
    config["critical_celsius"] = float(config["critical_celsius"])
    if not 1 <= config["interval_seconds"] <= 3600:
        raise ValueError("interval_seconds must be between 1 and 3600")
    if not -20 <= config["warning_celsius"] < config["critical_celsius"] <= 150:
        raise ValueError("temperature thresholds must satisfy -20 <= warning < critical <= 150")
    if config["consecutive_samples"] < 1 or config["cooldown_seconds"] < 0:
        raise ValueError("consecutive_samples must be >= 1 and cooldown_seconds >= 0")
    return config


def color(text: str, level: str, enabled: bool) -> str:
    return f"{ANSI.get(level, '')}{text}{ANSI['reset']}" if enabled else text


def render_dashboard(readings: list[Temperature], warning: float, critical: float,
                     counters: list[ThrottleCounter], use_color: bool = True) -> str:
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    width = 72
    lines = [color("╭" + "─" * (width - 2) + "╮", "cyan", use_color),
             color("│  CPU TEMPERATURE MONITOR".ljust(width - 1) + "│", "bold", use_color),
             color(("│  " + platform.node() + "  •  " + now)[:width - 1].ljust(width - 1) + "│", "dim", use_color),
             color("├" + "─" * (width - 2) + "┤", "cyan", use_color)]
    if not readings:
        lines.append("│  No temperature readings. Check lm-sensors and sensor permissions.".ljust(width - 1) + "│")
    for item in readings:
        state = "CRITICAL" if item.celsius >= critical else "WARNING" if item.celsius >= warning else "NORMAL"
        level = "red" if state == "CRITICAL" else "yellow" if state == "WARNING" else "green"
        label = f"{item.sensor}/{item.label}"[:39]
        bar_len = max(0, min(20, int(max(0, item.celsius) / 110 * 20)))
        bar = "█" * bar_len + "░" * (20 - bar_len)
        row = f"│ {label:<39} {item.celsius:6.1f}°C  {bar} {state}"
        lines.append(color(row[:width - 1].ljust(width - 1) + "│", level, use_color))
    lines.append(color("├" + "─" * (width - 2) + "┤", "cyan", use_color))
    lines.append(f"│ Thresholds: warning {warning:.1f}°C | critical {critical:.1f}°C".ljust(width - 1) + "│")
    if counters:
        lines.append(f"│ Linux throttle counters available: {len(counters)}".ljust(width - 1) + "│")
    else:
        lines.append("│ Linux throttle counters: unavailable on this hardware/driver".ljust(width - 1) + "│")
    lines.append(color("╰" + "─" * (width - 2) + "╯", "cyan", use_color))
    return "\n".join(lines)


def send_alert(message: str, config: dict) -> None:
    import urllib.request
    alerts = config.get("alerts", {})
    tg = alerts.get("telegram", {})
    if tg.get("enabled"):
        token = os.getenv("TELEGRAM_BOT_TOKEN", tg.get("bot_token", ""))
        chat = os.getenv("TELEGRAM_CHAT_ID", tg.get("chat_id", ""))
        if token and chat:
            try:
                import urllib.parse
                data = urllib.parse.urlencode({"chat_id": chat, "text": message}).encode()
                req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
                with urllib.request.urlopen(req, timeout=10) as response:
                    response.read()
            except Exception as exc:
                LOG.error("Telegram notification failed: %s", exc)
        else:
            LOG.warning("Telegram is enabled but credentials are missing")
    dc = alerts.get("discord", {})
    if dc.get("enabled"):
        url = os.getenv("DISCORD_WEBHOOK_URL", dc.get("webhook_url", ""))
        if url:
            try:
                payload = json.dumps({"content": message}).encode()
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as response:
                    response.read()
            except Exception as exc:
                LOG.error("Discord notification failed: %s", exc)
        else:
            LOG.warning("Discord is enabled but DISCORD_WEBHOOK_URL is missing")


def main() -> int:
    parser = argparse.ArgumentParser(description="Live CPU temperature monitor using lm-sensors.")
    parser.add_argument("-c", "--config", type=Path, default=BASE_DIR / "config.json")
    parser.add_argument("-i", "--interval", type=int, help="sampling interval in seconds")
    parser.add_argument("--warning", type=float, help="warning threshold in Celsius")
    parser.add_argument("--critical", type=float, help="critical threshold in Celsius")
    parser.add_argument("--once", action="store_true", help="take one reading and exit")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--no-color", action="store_true", help="disable colored dashboard")
    parser.add_argument("--sensors-command", default="sensors", help="lm-sensors executable name/path")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        interval = args.interval if args.interval is not None else config["interval_seconds"]
        warning = args.warning if args.warning is not None else config["warning_celsius"]
        critical = args.critical if args.critical is not None else config["critical_celsius"]
        if not 1 <= interval <= 3600 or not -20 <= warning < critical <= 150:
            raise ValueError("invalid interval or thresholds (require -20 <= warning < critical <= 150)")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    log_path = Path(config["log_file"])
    if not log_path.is_absolute():
        log_path = BASE_DIR / log_path
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(sys.stderr),
                                  logging.FileHandler(log_path, encoding="utf-8")])
    stopped = False
    def stop(_signum, _frame):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)

    streak, last_alert = 0, 0.0
    previous = {}
    while not stopped:
        readings = collect_temperatures(args.sensors_command)
        counters = read_throttle_counters()
        hottest = max((x.celsius for x in readings), default=None)
        now = datetime.now(timezone.utc).isoformat()
        if args.json:
            print(json.dumps({"timestamp": now, "hostname": platform.node(),
                              "readings": [asdict(x) for x in readings],
                              "hottest_celsius": hottest, "warning_celsius": warning,
                              "critical_celsius": critical,
                              "throttle_counters": [asdict(x) for x in counters]}), flush=True)
        else:
            if sys.stdout.isatty():
                print("\033[2J\033[H", end="")
            print(render_dashboard(readings, warning, critical, counters, not args.no_color and sys.stdout.isatty()),
                  flush=True)
        current = {x.name: x.count for x in counters}
        throttle_events = [name for name, count in current.items() if count > previous.get(name, count)]
        previous = current
        is_critical = hottest is not None and hottest >= critical
        streak = streak + 1 if is_critical else 0
        if hottest is not None and hottest >= warning:
            LOG.warning("Temperature threshold reached: hottest sensor %.1f°C", hottest)
        if throttle_events:
            LOG.warning("Thermal throttling counter increased: %s", ", ".join(throttle_events))
        should_alert = (streak >= config["consecutive_samples"] or bool(throttle_events))
        monotonic_now = time.monotonic()
        if should_alert and monotonic_now - last_alert >= config["cooldown_seconds"]:
            send_alert(f"⚠️ CPU OVERHEATING on {platform.node()}\nHottest: {hottest:.1f}°C\n"
                       f"Critical threshold: {critical:.1f}°C", config)
            last_alert = monotonic_now
        if args.once:
            return 0 if readings else 1
        for _ in range(interval):
            if stopped:
                break
            time.sleep(1)
    LOG.info("Temperature monitor stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
