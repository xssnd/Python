#!/usr/bin/env python3
"""Monitor inode consumption on mounted Linux filesystems (read-only)."""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import signal
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

LOG = logging.getLogger("inode_usage_monitor")
MOUNTINFO = Path("/proc/self/mountinfo")
PSEUDO_FS = {"autofs", "bpf", "cgroup", "cgroup2", "configfs", "debugfs", "devpts", "devtmpfs", "efivarfs", "fusectl", "hugetlbfs", "mqueue", "nsfs", "proc", "pstore", "rpc_pipefs", "securityfs", "sysfs", "tracefs"}


@dataclass(frozen=True)
class InodeStatus:
    device: str
    mountpoint: str
    filesystem: str
    total_inodes: int
    used_inodes: int
    free_inodes: int
    available_inodes: int
    used_percent: float
    free_percent: float
    level: str

    def to_dict(self) -> dict:
        return asdict(self)


def decode_mount_field(value: str) -> str:
    """Decode octal escapes used by proc mount tables."""
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), value)


def read_mounts(path: Path = MOUNTINFO) -> list[tuple[str, str, str]]:
    """Return (device, mountpoint, filesystem) tuples from Linux mountinfo."""
    mounts = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            fields = line.rstrip("\n").split()
            try:
                separator = fields.index("-")
                device = fields[separator + 2]
                filesystem = fields[separator + 1]
                mountpoint = decode_mount_field(fields[4])
            except (ValueError, IndexError):
                LOG.debug("Ignoring malformed mountinfo row: %s", line.rstrip())
                continue
            mounts.append((device, mountpoint, filesystem))
    return mounts


def classify(used_percent: float, warning: float = 80.0, critical: float = 90.0) -> str:
    if used_percent >= critical:
        return "CRITICAL"
    if used_percent >= warning:
        return "WARNING"
    return "OK"


def inspect_mounts(
    mounts: Iterable[tuple[str, str, str]] | None = None,
    statvfs_fn: Callable = os.statvfs,
    ignored_mounts: Iterable[str] = (),
    include_pseudo: bool = False,
) -> list[InodeStatus]:
    ignored = {str(Path(p)) for p in ignored_mounts}
    results: list[InodeStatus] = []
    seen: set[str] = set()
    for device, mountpoint, filesystem in mounts if mounts is not None else read_mounts():
        if mountpoint in seen or mountpoint in ignored:
            continue
        if not include_pseudo and filesystem.lower() in PSEUDO_FS:
            continue
        seen.add(mountpoint)
        try:
            stats = statvfs_fn(mountpoint)
            total = int(stats.f_files)
            free = int(stats.f_ffree)
            available = int(stats.f_favail)
            if total <= 0:
                LOG.debug("Filesystem %s has no finite inode counter", mountpoint)
                continue
            used = max(0, total - free)
            used_pct = min(100.0, max(0.0, used / total * 100))
            free_pct = 100.0 - used_pct
            results.append(InodeStatus(
                device=str(device), mountpoint=str(mountpoint), filesystem=str(filesystem),
                total_inodes=total, used_inodes=used, free_inodes=free,
                available_inodes=available, used_percent=round(used_pct, 2),
                free_percent=round(free_pct, 2), level="OK",
            ))
        except (OSError, PermissionError, ValueError) as exc:
            LOG.debug("Cannot inspect %s: %s", mountpoint, exc)
    return results


def evaluate(records: Iterable[InodeStatus], warning: float, critical: float) -> list[InodeStatus]:
    if not (0 <= warning <= critical <= 100):
        raise ValueError("Thresholds must satisfy 0 <= warning <= critical <= 100")
    return [
        InodeStatus(**{**row.to_dict(), "level": classify(row.used_percent, warning, critical)})
        for row in records
    ]


def bar(percent: float, width: int = 22) -> str:
    filled = min(width, max(0, round(percent / 100 * width)))
    return "█" * filled + "░" * (width - filled)


def render(records: list[InodeStatus], color: bool = True) -> str:
    lines = ["INODE USAGE MONITOR  |  LINUX FILESYSTEM INSPECTOR", "─" * 112]
    if not records:
        return "\n".join(lines + ["No readable filesystems with inode counters found."])
    for row in sorted(records, key=lambda item: item.used_percent, reverse=True):
        level = row.level
        if color and sys.stdout.isatty():
            code = {"OK": "32", "WARNING": "33", "CRITICAL": "31"}[level]
            level = f"\033[1;{code}m{level}\033[0m"
        lines.append(
            f"{level:<18} {row.mountpoint[:28]:<28} {row.filesystem:<12} "
            f"{row.used_percent:6.2f}% [{bar(row.used_percent)}] "
            f"{row.used_inodes:,}/{row.total_inodes:,} used | {row.available_inodes:,} available"
        )
    return "\n".join(lines)


def export_records(records: list[InodeStatus], path: str, output_format: str) -> None:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = [row.to_dict() for row in records]
    if output_format == "json":
        target.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    else:
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(InodeStatus.__dataclass_fields__))
            writer.writeheader()
            writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monitor inode exhaustion on mounted Linux filesystems. Read-only; never deletes files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="Examples:\n  python monitor.py --once\n  python monitor.py --warning 75 --critical 90\n  python monitor.py --watch --interval 30\n  python monitor.py --mount /var --json\n  python monitor.py --export reports/inodes.csv --format csv",
    )
    parser.add_argument("--once", action="store_true", help="perform one scan and exit (default when not watching)")
    parser.add_argument("--watch", action="store_true", help="refresh continuously until Ctrl+C")
    parser.add_argument("--interval", type=float, default=30.0, help="refresh interval in seconds")
    parser.add_argument("--warning", type=float, default=80.0, help="warning threshold for inode usage percent")
    parser.add_argument("--critical", type=float, default=90.0, help="critical threshold for inode usage percent")
    parser.add_argument("--mount", action="append", default=[], help="only inspect this mount point; may be repeated")
    parser.add_argument("--ignore-mount", action="append", default=[], help="skip this mount point; may be repeated")
    parser.add_argument("--include-pseudo", action="store_true", help="include pseudo filesystems such as proc and sysfs")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON to stdout")
    parser.add_argument("--export", metavar="PATH", help="write a report file")
    parser.add_argument("--format", choices=("json", "csv"), default="json", help="export format")
    parser.add_argument("--log-file", help="optional diagnostic log file")
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")
    parser.add_argument("--no-color", action="store_true", help="disable terminal colors")
    parser.add_argument("--version", action="version", version="Inode Usage Monitor 1.0.0")
    return parser


def configure_logging(path: str | None, verbose: bool) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if path:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(target, encoding="utf-8"))
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s", handlers=handlers, force=True,
    )


def run(args: argparse.Namespace) -> int:
    if args.interval <= 0:
        raise ValueError("--interval must be greater than 0")
    if not (0 <= args.warning <= args.critical <= 100):
        raise ValueError("Thresholds must satisfy 0 <= --warning <= --critical <= 100")
    selected_mounts = set(args.mount)
    stop = False

    def request_stop(_signum, _frame):
        nonlocal stop
        stop = True

    if args.watch:
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, request_stop)
    while not stop:
        mounts = read_mounts()
        if selected_mounts:
            mounts = [item for item in mounts if item[1] in selected_mounts]
            missing = selected_mounts - {item[1] for item in mounts}
            for mount in sorted(missing):
                LOG.warning("Requested mount point not found: %s", mount)
        records = evaluate(
            inspect_mounts(mounts, ignored_mounts=args.ignore_mount, include_pseudo=args.include_pseudo),
            args.warning, args.critical,
        )
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if args.json:
            print(json.dumps({
                "timestamp_utc": timestamp,
                "thresholds": {"warning": args.warning, "critical": args.critical},
                "filesystems": [row.to_dict() for row in records],
            }, ensure_ascii=False), flush=True)
        else:
            if args.watch:
                print("\033[2J\033[H", end="")
            print(f"\nInode Usage Monitor | {timestamp}")
            print(render(records, color=not args.no_color))
            print(f"\nFilesystems: {len(records)} | Warning: {args.warning:g}% | Critical: {args.critical:g}%")
            if args.watch:
                print(f"Refreshing every {args.interval:g}s | Ctrl+C to stop")
        if args.export:
            export_records(records, args.export, args.format)
        if not args.watch:
            return 1 if any(row.level == "CRITICAL" for row in records) else 0
        deadline = time.monotonic() + args.interval
        while not stop and time.monotonic() < deadline:
            time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.log_file, args.verbose)
    try:
        return run(args)
    except (OSError, ValueError) as exc:
        LOG.error("%s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
