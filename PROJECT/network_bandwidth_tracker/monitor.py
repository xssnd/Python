#!/usr/bin/env python3
"""Track per-interface network traffic rates and cumulative byte counters."""
from __future__ import annotations

import argparse
import csv
import json
import logging
import signal
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

try:
    from rich.console import Console
    from rich.table import Table
except ImportError:
    Console = Table = None

LOG = logging.getLogger("network_bandwidth_tracker")
CONSOLE = Console() if Console else None
CSV_FIELDS = [
    "timestamp_utc", "interface", "rx_bytes_total", "tx_bytes_total",
    "rx_bytes_per_sec", "tx_bytes_per_sec", "rx_mbps", "tx_mbps",
]


def require_dependencies():
    if psutil is None:
        raise RuntimeError("Missing dependency. Install with: python -m pip install -r requirements.txt")


def list_interfaces():
    """Return available interface names and their up/down state."""
    require_dependencies()
    stats = psutil.net_if_stats()
    counters = psutil.net_io_counters(pernic=True) or {}
    return [
        {"name": name, "is_up": bool(stats.get(name).isup) if name in stats else None,
         "rx_bytes": int(counters[name].bytes_recv), "tx_bytes": int(counters[name].bytes_sent)}
        for name in sorted(counters)
    ]


def select_interfaces(requested=None):
    available = {item["name"] for item in list_interfaces()}
    if not available:
        raise RuntimeError("No network interfaces with traffic counters were found.")
    if not requested or requested == ["all"]:
        return sorted(available)
    unknown = sorted(set(requested) - available)
    if unknown:
        raise ValueError(f"Unknown interface(s): {', '.join(unknown)}. Use --list-interfaces.")
    return sorted(set(requested))


def take_snapshot(interfaces):
    """Capture cumulative counters for selected interfaces."""
    require_dependencies()
    all_counters = psutil.net_io_counters(pernic=True) or {}
    missing = [name for name in interfaces if name not in all_counters]
    if missing:
        raise RuntimeError(f"Interface disappeared: {', '.join(missing)}")
    now = time.monotonic()
    return {
        name: {"time": now, "rx": int(all_counters[name].bytes_recv),
               "tx": int(all_counters[name].bytes_sent)}
        for name in interfaces
    }


def calculate_rates(previous, current):
    """Calculate non-negative byte rates; counter resets produce zero for that direction."""
    elapsed = current["time"] - previous["time"]
    if elapsed <= 0:
        raise ValueError("Sampling timestamps must move forward.")
    rx_delta = current["rx"] - previous["rx"]
    tx_delta = current["tx"] - previous["tx"]
    rx_rate = max(0, rx_delta) / elapsed
    tx_rate = max(0, tx_delta) / elapsed
    return {
        "rx_bytes_total": current["rx"], "tx_bytes_total": current["tx"],
        "rx_bytes_per_sec": rx_rate, "tx_bytes_per_sec": tx_rate,
        "rx_mbps": rx_rate * 8 / 1_000_000, "tx_mbps": tx_rate * 8 / 1_000_000,
        "interval_seconds": elapsed,
    }


def format_bytes(value):
    value = float(value)
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    for unit in units:
        if abs(value) < 1024 or unit == units[-1]:
            return f"{value:,.2f} {unit}"
        value /= 1024
    return f"{value:,.2f} PB"


def sparkline(values, width=24):
    """Small dependency-free terminal trend graph."""
    glyphs = "▁▂▃▄▅▆▇█"
    values = list(values)[-width:]
    if not values:
        return "—"
    low, high = min(values), max(values)
    if high == low:
        return glyphs[0] * len(values)
    return "".join(glyphs[min(7, int((v - low) / (high - low) * 7))] for v in values)


def build_record(interface, rates, timestamp=None):
    return {"timestamp_utc": timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "interface": interface, **rates}


def append_export(path, output_format, records):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        # JSON Lines makes continuous monitoring append-safe and stream-friendly.
        with path.open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    elif output_format == "csv":
        exists = path.exists() and path.stat().st_size > 0
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
            if not exists:
                writer.writeheader()
            writer.writerows(records)
    else:
        raise ValueError("Export format must be json or csv.")


def render_dashboard(records, histories, elapsed, color=True):
    if CONSOLE and color:
        table = Table(title="NETWORK BANDWIDTH TRACKER", header_style="bold cyan")
        table.add_column("INTERFACE", style="bold")
        table.add_column("RX RATE", justify="right", style="green")
        table.add_column("TX RATE", justify="right", style="yellow")
        table.add_column("RX TOTAL", justify="right")
        table.add_column("TX TOTAL", justify="right")
        table.add_column("RX TREND")
        table.add_column("TX TREND")
        for record in records:
            name = record["interface"]
            table.add_row(name, f'{format_bytes(record["rx_bytes_per_sec"])}/s',
                          f'{format_bytes(record["tx_bytes_per_sec"])}/s',
                          format_bytes(record["rx_bytes_total"]), format_bytes(record["tx_bytes_total"]),
                          sparkline(histories[name]["rx"]), sparkline(histories[name]["tx"]))
        CONSOLE.clear()
        CONSOLE.print(table)
        CONSOLE.print(f"Sampling interval: {elapsed:.2f}s  |  Ctrl+C to stop")
        return

    lines = ["NETWORK BANDWIDTH TRACKER", "=" * 112,
             f"{'INTERFACE':<18} {'RX RATE':>15} {'TX RATE':>15} {'RX TOTAL':>16} {'TX TOTAL':>16}  {'RX TREND':<12} {'TX TREND':<12}",
             "-" * 112]
    for record in records:
        name = record["interface"]
        lines.append(f'{name:<18} {format_bytes(record["rx_bytes_per_sec"])+"/s":>15} '
                     f'{format_bytes(record["tx_bytes_per_sec"])+"/s":>15} '
                     f'{format_bytes(record["rx_bytes_total"]):>16} {format_bytes(record["tx_bytes_total"]):>16}  '
                     f'{sparkline(histories[name]["rx"]):<12} {sparkline(histories[name]["tx"]):<12}')
    lines.append(f"Sampling interval: {elapsed:.2f}s  |  Ctrl+C to stop")
    print("\033[2J\033[H" + "\n".join(lines))


def build_parser():
    parser = argparse.ArgumentParser(
        description="Monitor RX/TX bandwidth and cumulative traffic per network interface.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="Examples:\n  python monitor.py --list-interfaces\n  python monitor.py --interface eth0 --watch\n"
               "  python monitor.py --interface wlan0 --interval 1 --duration 60\n"
               "  python monitor.py --interface all --json\n"
               "  python monitor.py --interface eth0 --export reports/traffic.csv --format csv",
    )
    parser.add_argument("-i", "--interface", action="append", help="interface name (repeatable); default: all")
    parser.add_argument("--list-interfaces", action="store_true", help="list detected interfaces and exit")
    parser.add_argument("--watch", action="store_true", help="continuously refresh until stopped")
    parser.add_argument("--interval", type=float, default=1.0, help="sampling interval in seconds")
    parser.add_argument("--duration", type=float, help="stop after this many seconds (also works with --watch)")
    parser.add_argument("--alert-mbps", type=float, help="warn when RX or TX rate reaches this Mbps threshold")
    parser.add_argument("--json", action="store_true", help="emit JSON Lines to stdout")
    parser.add_argument("--export", metavar="PATH", help="append samples to a JSONL or CSV file")
    parser.add_argument("--format", choices=("json", "csv"), default="csv", help="export format")
    parser.add_argument("--no-color", action="store_true", help="use plain terminal output")
    parser.add_argument("--log-file", help="optional diagnostic log file")
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")
    parser.add_argument("--version", action="version", version="Network Bandwidth Tracker 1.0.0")
    return parser


def configure_logging(path=None, verbose=False):
    handlers = [logging.StreamHandler()]
    if path:
        log_path = Path(path).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s", handlers=handlers, force=True)


def run(args):
    require_dependencies()
    if args.interval <= 0:
        raise ValueError("--interval must be greater than 0.")
    if args.duration is not None and args.duration <= 0:
        raise ValueError("--duration must be greater than 0.")
    if args.alert_mbps is not None and args.alert_mbps <= 0:
        raise ValueError("--alert-mbps must be greater than 0.")

    if args.list_interfaces:
        for item in list_interfaces():
            state = "UP" if item["is_up"] else "DOWN" if item["is_up"] is False else "UNKNOWN"
            print(f'{item["name"]:<20} {state:<8} RX {format_bytes(item["rx_bytes"]):>14}  TX {format_bytes(item["tx_bytes"]):>14}')
        return 0

    interfaces = select_interfaces(args.interface)
    previous = take_snapshot(interfaces)
    histories = {name: {"rx": deque(maxlen=32), "tx": deque(maxlen=32)} for name in interfaces}
    started = time.monotonic()
    stop = False

    def request_stop(_signum, _frame):
        nonlocal stop
        stop = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, request_stop)

    while not stop:
        deadline = time.monotonic() + args.interval
        while not stop and time.monotonic() < deadline:
            time.sleep(min(0.2, max(0, deadline - time.monotonic())))
        if stop:
            break
        current = take_snapshot(interfaces)
        records = []
        sample_elapsed = 0.0
        for name in interfaces:
            rates = calculate_rates(previous[name], current[name])
            sample_elapsed = max(sample_elapsed, rates["interval_seconds"])
            histories[name]["rx"].append(rates["rx_bytes_per_sec"])
            histories[name]["tx"].append(rates["tx_bytes_per_sec"])
            records.append(build_record(name, rates))
        previous = current

        if args.json:
            for record in records:
                print(json.dumps(record, ensure_ascii=False), flush=True)
        else:
            render_dashboard(records, histories, sample_elapsed, color=not args.no_color)

        if args.export:
            append_export(args.export, args.format, records)
        if args.alert_mbps is not None:
            for record in records:
                if max(record["rx_mbps"], record["tx_mbps"]) >= args.alert_mbps:
                    LOG.warning("%s bandwidth threshold reached: RX %.3f Mbps / TX %.3f Mbps",
                                record["interface"], record["rx_mbps"], record["tx_mbps"])
                    if not args.json:
                        print(f'WARNING: {record["interface"]} reached threshold '
                              f'(RX {record["rx_mbps"]:.2f} Mbps / TX {record["tx_mbps"]:.2f} Mbps)')

        if args.duration is not None and time.monotonic() - started >= args.duration:
            break
        if not args.watch:
            break
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
