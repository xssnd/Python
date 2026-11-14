#!/usr/bin/env python3
"""CPU temperature and Linux thermal-throttling monitor."""
from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import re
import signal
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

try:
    import psutil
except ImportError:
    psutil = None

BASE_DIR = Path(__file__).resolve().parent
LOG = logging.getLogger("thermal-monitor")


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


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None


def read_hwmon() -> list[Temperature]:
    """Read Linux hwmon temperature channels; labels often identify CPU cores."""
    results: list[Temperature] = []
    root = Path("/sys/class/hwmon")
    if not root.exists():
        return results
    for hwmon in sorted(root.glob("hwmon*")):
        chip = _read_text(hwmon / "name") or hwmon.name
        for inp in sorted(hwmon.glob("temp*_input")):
            raw = _read_text(inp)
            if raw is None:
                continue
            try:
                value = float(raw) / 1000.0
            except ValueError:
                continue
            stem = inp.name.removesuffix("_input")
            label = _read_text(hwmon / f"{stem}_label") or stem
            results.append(Temperature(chip, label, value, str(inp)))
    return results


def read_psutil_temperatures() -> list[Temperature]:
    """Read sensors exposed by psutil (primarily Linux and some BSD systems)."""
    if psutil is None or not hasattr(psutil, "sensors_temperatures"):
        return []
    try:
        groups = psutil.sensors_temperatures(fahrenheit=False) or {}
    except (OSError, RuntimeError):
        return []
    results = []
    for chip, entries in groups.items():
        for entry in entries:
            if entry.current is None:
                continue
            results.append(Temperature(chip, entry.label or chip, float(entry.current), "psutil"))
    return results


def read_temperatures() -> list[Temperature]:
    """Prefer hwmon's explicit labels; use psutil as a fallback."""
    hwmon = read_hwmon()
    psutil_values = read_psutil_temperatures()
    seen = {(x.sensor, x.label, round(x.celsius, 1)) for x in hwmon}
    return hwmon + [x for x in psutil_values
                    if (x.sensor, x.label, round(x.celsius, 1)) not in seen]


def read_throttle_counters() -> list[ThrottleCounter]:
    """Read Linux kernel thermal-throttle counters when the CPU driver exposes them."""
    root = Path("/sys/devices/system/cpu")
    counters: list[ThrottleCounter] = []
    if not root.exists():
        return counters
    for cpu_dir in sorted(root.glob("cpu[0-9]*")):
        throttle = cpu_dir / "thermal_throttle"
        for filename in ("core_throttle_count", "package_throttle_count"):
            path = throttle / filename
            raw = _read_text(path)
            if raw is not None:
                try:
                    counters.append(ThrottleCounter(f"{cpu_dir.name}:{filename}", int(raw), str(path)))
                except ValueError:
                    pass
    return counters


def load_config(path: Path) -> dict:
    defaults = {
        "interval_seconds": 5,
        "warning_celsius": 80,
        "critical_celsius": 90,
        "consecutive_samples": 2,
        "cooldown_seconds": 300,
        "log_file": "thermal_monitor.log",
        "alerts": {"telegram": {"enabled": False}, "discord": {"enabled": False},
                   "email": {"enabled": False}}
    }
    if path.exists():
        user = json.loads(path.read_text(encoding="utf-8"))
        defaults.update(user)
        defaults["alerts"] = {**defaults["alerts"], **user.get("alerts", {})}
    if not (1 <= int(defaults["interval_seconds"]) <= 3600):
        raise ValueError("interval_seconds must be between 1 and 3600")
    if float(defaults["warning_celsius"]) >= float(defaults["critical_celsius"]):
        raise ValueError("warning_celsius must be lower than critical_celsius")
    if int(defaults["consecutive_samples"]) < 1:
        raise ValueError("consecutive_samples must be at least 1")
    return defaults


def send_alert(message: str, config: dict) -> None:
    """Best-effort notifications; missing optional settings never stop monitoring."""
    import urllib.request
    alerts = config.get("alerts", {})
    telegram = alerts.get("telegram", {})
    if telegram.get("enabled"):
        token = os.getenv("TELEGRAM_BOT_TOKEN", telegram.get("bot_token", ""))
        chat = os.getenv("TELEGRAM_CHAT_ID", telegram.get("chat_id", ""))
        if token and chat:
            try:
                import urllib.parse
                data = urllib.parse.urlencode({"chat_id": chat, "text": message}).encode()
                req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
                urllib.request.urlopen(req, timeout=10).read()
            except Exception as exc:
                LOG.error("Telegram notification failed: %s", exc)
        else:
            LOG.warning("Telegram enabled but token/chat ID is missing")
    discord = alerts.get("discord", {})
    if discord.get("enabled"):
        url = os.getenv("DISCORD_WEBHOOK_URL", discord.get("webhook_url", ""))
        if url:
            try:
                payload = json.dumps({"content": message}).encode()
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=10).read()
            except Exception as exc:
                LOG.error("Discord notification failed: %s", exc)
        else:
            LOG.warning("Discord enabled but webhook URL is missing")


def format_report(temps: list[Temperature], counters: list[ThrottleCounter]) -> str:
    lines = [f"Thermal Monitor | {platform.node()} | {time.strftime('%Y-%m-%d %H:%M:%S')}"]
    if temps:
        lines.extend(f"- {t.sensor} / {t.label}: {t.celsius:.1f} °C [{t.source}]" for t in temps)
    else:
        lines.append("- No temperature sensors exposed by this OS/hardware.")
    if counters:
        lines.append("Linux thermal-throttle counters:")
        lines.extend(f"- {c.name}: {c.count}" for c in counters)
    else:
        lines.append("Thermal-throttle counters: unavailable on this system/driver.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor CPU temperatures and thermal-throttling counters.")
    parser.add_argument("-c", "--config", type=Path, default=BASE_DIR / "config.json")
    parser.add_argument("--once", action="store_true", help="Collect one sample and exit.")
    args = parser.parse_args()
    config = load_config(args.config)
    log_path = Path(config.get("log_file", "thermal_monitor.log"))
    if not log_path.is_absolute():
        log_path = BASE_DIR / log_path
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(log_path, encoding="utf-8")])
    stop = False

    def request_stop(_signum, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    hot_streak = 0
    last_alert = 0.0
    previous_counts: dict[str, int] = {}
    while not stop:
        temps = read_temperatures()
        counters = read_throttle_counters()
        report = format_report(temps, counters)
        LOG.info("\n%s", report)
        hottest = max((t.celsius for t in temps), default=None)
        current_counts = {c.name: c.count for c in counters}
        throttle_events = [name for name, count in current_counts.items()
                           if count > previous_counts.get(name, count)]
        previous_counts = current_counts
        critical = hottest is not None and hottest >= float(config["critical_celsius"])
        warning = hottest is not None and hottest >= float(config["warning_celsius"])
        hot_streak = hot_streak + 1 if critical else 0
        reason = []
        if warning:
            reason.append(f"temperature reached {hottest:.1f} °C")
        if throttle_events:
            reason.append("thermal-throttle counter increased: " + ", ".join(throttle_events))
        should_alert = bool(reason) and (hot_streak >= int(config["consecutive_samples"]) or throttle_events)
        now = time.monotonic()
        if should_alert and now - last_alert >= int(config["cooldown_seconds"]):
            send_alert("⚠️ CPU thermal warning on " + platform.node() + "\n" +
                       "; ".join(reason) + "\n\n" + report, config)
            last_alert = now
        if args.once:
            break
        for _ in range(int(config["interval_seconds"])):
            if stop:
                break
            time.sleep(1)
    LOG.info("Thermal monitor stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
