#!/usr/bin/env python3
"""Inspect the processes consuming the most CPU time or physical memory."""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

LOG = logging.getLogger("top_resource_consumers")
FIELDS = ["pid", "name", "username", "status", "cpu_percent", "memory_percent", "memory_mb", "threads"]


def require_psutil():
    if psutil is None:
        raise RuntimeError("Missing dependency: install requirements with 'python -m pip install -r requirements.txt'")


def collect_processes(sample_seconds=0.1, name_filter=None, user_filter=None):
    """Collect a safe, best-effort process snapshot; inaccessible processes are skipped."""
    require_psutil()
    if sample_seconds < 0:
        raise ValueError("sample_seconds cannot be negative")
    records = []
    for proc in psutil.process_iter():
        try:
            with proc.oneshot():
                info = proc.as_dict(attrs=["pid", "name", "username", "status", "memory_percent", "memory_info", "num_threads"])
            name = info.get("name") or "?"
            username = info.get("username") or "?"
            if name_filter and name_filter.casefold() not in name.casefold():
                continue
            if user_filter and user_filter.casefold() not in username.casefold():
                continue
            cpu = proc.cpu_percent(interval=sample_seconds) if sample_seconds else proc.cpu_percent(interval=None)
            mem_info = info.get("memory_info")
            rss = int(mem_info.rss) if mem_info else 0
            records.append({
                "pid": int(info["pid"]), "name": name, "username": username,
                "status": info.get("status") or "unknown",
                "cpu_percent": round(max(0.0, float(cpu)), 2),
                "memory_percent": round(max(0.0, float(info.get("memory_percent") or 0.0)), 2),
                "memory_mb": round(rss / (1024 * 1024), 2),
                "threads": int(info.get("num_threads") or 0),
            })
        except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied, ProcessLookupError, PermissionError):
            continue
        except (OSError, ValueError, TypeError):
            LOG.debug("Skipping process %s due to an unavailable metric", getattr(proc, "pid", "?"), exc_info=True)
    return records


def rank_processes(records, sort_by="cpu", top=5):
    if sort_by not in {"cpu", "memory"}:
        raise ValueError("sort_by must be 'cpu' or 'memory'")
    if top < 1:
        raise ValueError("top must be at least 1")
    key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
    return sorted(records, key=lambda item: (item.get(key, 0), item.get("memory_mb", 0)), reverse=True)[:top]


def format_bytes_mb(value):
    return f"{float(value):,.2f} MB"


def render_bar(value, width=18):
    filled = min(width, max(0, int(round(float(value) / 100 * width))))
    return "█" * filled + "░" * (width - filled)


def render_table(records, title, color=True):
    if not records:
        return f"\n{title}\nNo matching processes found."
    lines = [f"\n{title}", f"{'PID':>7}  {'PROCESS':<24} {'USER':<16} {'CPU %':>8} {'RAM %':>8} {'RAM':>12} {'THR':>4}"]
    lines.append("─" * 91)
    for item in records:
        name = item["name"][:24]
        user = item["username"][:16]
        lines.append(f"{item['pid']:>7}  {name:<24} {user:<16} {item['cpu_percent']:>7.2f}% {item['memory_percent']:>7.2f}% {format_bytes_mb(item['memory_mb']):>12} {item['threads']:>4}")
    return "\n".join(lines)


def system_summary():
    require_psutil()
    cpu = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cpu_percent": round(float(cpu), 2),
        "memory_percent": round(float(memory.percent), 2),
        "memory_used_mb": round(memory.used / (1024 * 1024), 2),
        "memory_total_mb": round(memory.total / (1024 * 1024), 2),
    }


def export_records(records, path, output_format):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    elif output_format == "csv":
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
    else:
        raise ValueError("output format must be json or csv")


def configure_logging(log_file=None, verbose=False):
    handlers = [logging.StreamHandler()]
    if log_file:
        path = Path(log_file).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(path, encoding="utf-8"))
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s", handlers=handlers, force=True)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Show the processes consuming the most CPU or RAM. Read-only; no process is modified.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="Examples:\n  python monitor.py\n  python monitor.py --sort memory --top 10\n  python monitor.py --watch --interval 2 --sort cpu\n  python monitor.py --filter python --json\n  python monitor.py --export top.csv --format csv",
    )
    parser.add_argument("--sort", choices=("cpu", "memory", "both"), default="cpu", help="resource ranking")
    parser.add_argument("--top", type=int, default=5, help="number of processes per ranking")
    parser.add_argument("--watch", action="store_true", help="refresh continuously until Ctrl+C")
    parser.add_argument("--interval", type=float, default=2.0, help="watch refresh interval in seconds")
    parser.add_argument("--filter", dest="name_filter", help="case-insensitive process-name substring")
    parser.add_argument("--user", dest="user_filter", help="filter by username")
    parser.add_argument("--pid", type=int, help="show details for one PID")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--export", metavar="PATH", help="save the selected ranking to a file")
    parser.add_argument("--format", choices=("json", "csv"), default="json", help="export format")
    parser.add_argument("--log-file", help="optional diagnostic log file")
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")
    parser.add_argument("--no-color", action="store_true", help="disable terminal styling (plain output is default)")
    parser.add_argument("--version", action="version", version="Top Resource Consumers 1.0.0")
    return parser


def run(args):
    require_psutil()
    if args.top < 1:
        raise ValueError("--top must be at least 1")
    if args.interval <= 0:
        raise ValueError("--interval must be greater than 0")
    if args.pid is not None and args.pid < 1:
        raise ValueError("--pid must be a positive integer")

    stop = False
    def request_stop(_signum, _frame):
        nonlocal stop
        stop = True
    if args.watch:
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, request_stop)

    while not stop:
        if args.pid is not None:
            try:
                proc = psutil.Process(args.pid)
                records = collect_processes(0.1)
                records = [item for item in records if item["pid"] == args.pid]
            except psutil.NoSuchProcess:
                records = []
            if not records:
                raise ValueError(f"Process with PID {args.pid} was not found or is not accessible")
        else:
            records = collect_processes(0.1, args.name_filter, args.user_filter)

        selected = []
        if args.sort in ("cpu", "both"):
            cpu_rows = rank_processes(records, "cpu", args.top)
            selected = cpu_rows if args.sort == "cpu" else cpu_rows
        if args.sort == "memory":
            selected = rank_processes(records, "memory", args.top)
        if args.sort == "both":
            mem_rows = rank_processes(records, "memory", args.top)
            selected = list({item["pid"]: item for item in cpu_rows + mem_rows}.values())

        summary = system_summary()
        if args.json:
            payload = {"system": summary, "sort": args.sort, "top": args.top, "processes": selected}
            print(json.dumps(payload, ensure_ascii=False))
        else:
            if args.watch:
                print("\033[2J\033[H", end="")
            print("TOP RESOURCE CONSUMERS  |  READ-ONLY PROCESS INSPECTOR")
            print(f"Host: {os.environ.get('COMPUTERNAME') or os.uname().nodename if hasattr(os, 'uname') else os.environ.get('COMPUTERNAME', 'Windows')}")
            print(f"CPU {summary['cpu_percent']:5.1f}%  {render_bar(summary['cpu_percent'])}   RAM {summary['memory_percent']:5.1f}%  {render_bar(summary['memory_percent'])}")
            print(f"Memory: {summary['memory_used_mb']:,.0f} / {summary['memory_total_mb']:,.0f} MB  |  {summary['timestamp_utc']}")
            if args.sort in ("cpu", "both"):
                print(render_table(rank_processes(records, "cpu", args.top), f"TOP {args.top} CPU PROCESSES"))
            if args.sort in ("memory", "both"):
                print(render_table(rank_processes(records, "memory", args.top), f"TOP {args.top} MEMORY PROCESSES"))
            if args.watch:
                print(f"\nRefreshing every {args.interval:g}s  |  Press Ctrl+C to exit")
        if args.export:
            export_records(selected, args.export, args.format)
        if not args.watch:
            break
        deadline = time.monotonic() + args.interval
        while not stop and time.monotonic() < deadline:
            time.sleep(min(0.2, max(0, deadline - time.monotonic())))
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    configure_logging(args.log_file, args.verbose)
    try:
        return run(args)
    except (RuntimeError, ValueError, OSError) as exc:
        LOG.error("%s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
