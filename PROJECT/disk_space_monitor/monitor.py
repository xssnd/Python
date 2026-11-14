#!/usr/bin/env python3
"""Disk Space Monitor: partition discovery, threshold evaluation and alert delivery."""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

import psutil

from notifiers import build_notifiers

LOG = logging.getLogger("disk_space_monitor")


@dataclass(frozen=True)
class DiskStatus:
    device: str
    mountpoint: str
    filesystem: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    free_percent: float
    used_percent: float
    level: str

    def to_dict(self) -> dict:
        return asdict(self)


def classify(free_percent: float, warning: float = 10.0, critical: float = 5.0) -> str:
    if free_percent <= critical:
        return "CRITICAL"
    if free_percent <= warning:
        return "WARNING"
    return "OK"


def discover_disks(
    partitions: Iterable | None = None,
    usage_fn: Callable = psutil.disk_usage,
    ignored_mounts: Iterable[str] = (),
    include_removable: bool = True,
) -> list[DiskStatus]:
    """Return readable mounted filesystems; inaccessible/pseudo filesystems are skipped."""
    ignored = {str(Path(p)) for p in ignored_mounts}
    found: list[DiskStatus] = []
    seen: set[str] = set()
    for part in partitions if partitions is not None else psutil.disk_partitions(all=False):
        mount = part.mountpoint
        if mount in seen or mount in ignored:
            continue
        if not include_removable and "removable" in getattr(part, "opts", "").lower():
            continue
        seen.add(mount)
        try:
            usage = usage_fn(mount)
            total = int(usage.total)
            if total <= 0:
                continue
            free = int(usage.free)
            used = int(usage.used)
            free_pct = max(0.0, min(100.0, free / total * 100))
            found.append(DiskStatus(
                device=str(part.device), mountpoint=str(mount),
                filesystem=str(getattr(part, "fstype", "") or "unknown"),
                total_bytes=total, used_bytes=used, free_bytes=free,
                free_percent=round(free_pct, 2),
                used_percent=round(used / total * 100, 2),
                level="OK",
            ))
        except (OSError, PermissionError, ValueError):
            LOG.debug("Skipping inaccessible filesystem %s", mount, exc_info=True)
    return found


def evaluate_disks(disks: Iterable[DiskStatus], warning: float, critical: float) -> list[DiskStatus]:
    return [
        DiskStatus(**{**disk.to_dict(), "level": classify(disk.free_percent, warning, critical)})
        for disk in disks
    ]


def format_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if size < 1024 or unit == "PiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PiB"


class AlertManager:
    """Suppress repeated alerts per mount and announce recovery transitions."""
    def __init__(self, notifiers, cooldown_seconds: int = 3600, recovery_alerts: bool = True):
        self.notifiers = list(notifiers)
        self.cooldown = max(0, int(cooldown_seconds))
        self.recovery_alerts = recovery_alerts
        self.last_alert: dict[str, float] = {}
        self.previous_level: dict[str, str] = {}

    def process(self, disks: Iterable[DiskStatus], now: float | None = None) -> list[str]:
        now = time.time() if now is None else now
        sent: list[str] = []
        for disk in disks:
            previous = self.previous_level.get(disk.mountpoint, "OK")
            self.previous_level[disk.mountpoint] = disk.level
            if disk.level == "OK":
                if previous != "OK" and self.recovery_alerts:
                    message = f"RECOVERY: {disk.mountpoint} is healthy again ({disk.free_percent:.1f}% free)."
                    self._send(message)
                    sent.append(message)
                continue
            last = self.last_alert.get(disk.mountpoint, 0)
            if now - last < self.cooldown and previous == disk.level:
                continue
            message = (
                f"{disk.level}: low disk space on {disk.mountpoint} "
                f"({disk.free_percent:.1f}% free, {format_bytes(disk.free_bytes)} free "
                f"of {format_bytes(disk.total_bytes)})."
            )
            self._send(message)
            self.last_alert[disk.mountpoint] = now
            sent.append(message)
        return sent

    def _send(self, message: str) -> None:
        for notifier in self.notifiers:
            try:
                notifier.send(message)
            except Exception:
                LOG.exception("Notification delivery failed via %s", type(notifier).__name__)


def load_config(path: str | None) -> dict:
    config = {
        "warning_percent": 10,
        "critical_percent": 5,
        "interval_seconds": 300,
        "cooldown_seconds": 3600,
        "recovery_alerts": True,
        "include_removable": True,
        "ignored_mounts": [],
        "log_file": None,
        "notifications": {"telegram": {}, "discord": {}, "email": {}},
    }
    if path:
        with open(path, encoding="utf-8") as handle:
            loaded = json.load(handle)
        config.update(loaded)
    # Secrets can be supplied without storing them in the JSON file.
    env_map = {
        "telegram": {"bot_token": "DSM_TELEGRAM_BOT_TOKEN", "chat_id": "DSM_TELEGRAM_CHAT_ID"},
        "discord": {"webhook_url": "DSM_DISCORD_WEBHOOK_URL"},
        "email": {
            "smtp_host": "DSM_SMTP_HOST", "smtp_port": "DSM_SMTP_PORT",
            "username": "DSM_SMTP_USERNAME", "password": "DSM_SMTP_PASSWORD",
            "sender": "DSM_EMAIL_FROM", "recipient": "DSM_EMAIL_TO",
        },
    }
    notifications = config.setdefault("notifications", {})
    for channel, fields in env_map.items():
        target = notifications.setdefault(channel, {})
        for key, env_name in fields.items():
            if os.getenv(env_name):
                target[key] = os.environ[env_name]
    return config


def configure_logging(log_file: str | None) -> None:
    handlers = [logging.StreamHandler()]
    if log_file:
        Path(log_file).expanduser().parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(Path(log_file).expanduser(), encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers, force=True,
    )


def run(config: dict, once: bool = False, json_output: bool = False) -> int:
    warning = float(config.get("warning_percent", 10))
    critical = float(config.get("critical_percent", 5))
    if not (0 <= critical <= warning <= 100):
        raise ValueError("Thresholds must satisfy 0 <= critical_percent <= warning_percent <= 100")
    interval = max(5, int(config.get("interval_seconds", 300)))
    alert_manager = AlertManager(
        build_notifiers(config.get("notifications", {})),
        config.get("cooldown_seconds", 3600),
        config.get("recovery_alerts", True),
    )
    stop = False

    def request_stop(_signum, _frame):
        nonlocal stop
        stop = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, request_stop)

    while not stop:
        disks = evaluate_disks(
            discover_disks(
                ignored_mounts=config.get("ignored_mounts", []),
                include_removable=config.get("include_removable", True),
            ), warning, critical,
        )
        timestamp = datetime.now(timezone.utc).isoformat()
        if json_output:
            print(json.dumps({"timestamp": timestamp, "partitions": [d.to_dict() for d in disks]}))
        else:
            print(f"\nDisk Space Monitor — {timestamp}")
            if not disks:
                print("No readable mounted partitions found.")
            for disk in disks:
                print(
                    f"[{disk.level:8}] {disk.mountpoint:<24} "
                    f"free {disk.free_percent:6.2f}% "
                    f"({format_bytes(disk.free_bytes)} / {format_bytes(disk.total_bytes)})"
                )
        alert_manager.process(disks)
        if once:
            break
        for _ in range(interval):
            if stop:
                break
            time.sleep(1)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monitor mounted disk partitions and alert on low free space.")
    parser.add_argument("-c", "--config", default="config.json", help="JSON config file (default: config.json)")
    parser.add_argument("--once", action="store_true", help="Run one scan and exit")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--version", action="version", version="Disk Space Monitor 1.0.0")
    args = parser.parse_args(argv)
    config_path = args.config if Path(args.config).is_file() else None
    config = load_config(config_path)
    configure_logging(config.get("log_file"))
    try:
        return run(config, once=args.once, json_output=args.json)
    except (ValueError, OSError) as exc:
        LOG.error("%s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
