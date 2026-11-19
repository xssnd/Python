#!/usr/bin/env python3
"""Inventory listening TCP sockets and bound UDP ports with owning processes."""
from __future__ import annotations
import argparse, csv, json, logging, signal, socket, sys, time
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

LOG = logging.getLogger("open_ports_checker")
CONSOLE = Console() if Console else None
FIELDS = ["timestamp_utc", "protocol", "local_address", "port", "state", "exposure",
          "pid", "process", "username", "executable", "command"]

def require_dependencies():
    if psutil is None:
        raise RuntimeError("Missing dependency. Install with: python -m pip install -r requirements.txt")

def address_parts(address):
    if not address:
        return "", 0
    if hasattr(address, "ip"):
        return str(address.ip), int(address.port)
    return str(address[0]), int(address[1])

def is_wildcard_address(host):
    return host in ("0.0.0.0", "::", "*", "")

def process_details(pid):
    if pid is None:
        return {"process": "permission denied / unavailable", "username": "", "executable": "", "command": ""}
    try:
        proc = psutil.Process(pid)
        info = proc.as_dict(attrs=["name", "username", "exe", "cmdline"], ad_value=None)
        return {"process": info.get("name") or "unknown", "username": info.get("username") or "",
                "executable": info.get("exe") or "", "command": " ".join(info.get("cmdline") or [])[:500]}
    except psutil.NoSuchProcess:
        return {"process": "exited", "username": "", "executable": "", "command": ""}
    except (psutil.AccessDenied, psutil.ZombieProcess):
        return {"process": "access denied", "username": "", "executable": "", "command": ""}
    except Exception as exc:
        LOG.debug("Could not inspect PID %s: %s", pid, exc)
        return {"process": "unavailable", "username": "", "executable": "", "command": ""}

def collect_listeners():
    """Collect TCP LISTEN sockets and UDP sockets bound to a local port."""
    require_dependencies()
    try:
        connections = psutil.net_connections(kind="inet")
    except psutil.AccessDenied as exc:
        raise RuntimeError("Permission denied while reading system sockets. Re-run with elevated privileges "
                           "(for example, sudo on Linux) to see all processes and ports.") from exc
    records = []
    for conn in connections:
        if not conn.laddr:
            continue
        host, port = address_parts(conn.laddr)
        if port <= 0:
            continue
        if conn.type == socket.SOCK_STREAM:
            if conn.status != psutil.CONN_LISTEN:
                continue
            protocol, state = "tcp", "LISTEN"
        elif conn.type == socket.SOCK_DGRAM:
            protocol, state = "udp", "BOUND"
        else:
            continue
        records.append({"timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "protocol": protocol, "local_address": host, "port": port, "state": state,
                        "exposure": "ALL INTERFACES" if is_wildcard_address(host) else "SPECIFIC ADDRESS",
                        "pid": conn.pid, **process_details(conn.pid)})
    return sorted(records, key=lambda r: (r["port"], r["protocol"], r["local_address"], r["pid"] or 0))

def filter_records(records, args):
    result = records
    if args.protocol != "all":
        result = [r for r in result if r["protocol"] == args.protocol]
    if args.port:
        wanted = set(args.port)
        result = [r for r in result if r["port"] in wanted]
    if args.pid is not None:
        result = [r for r in result if r["pid"] == args.pid]
    if args.process:
        needle = args.process.casefold()
        result = [r for r in result if needle in r["process"].casefold() or needle in r["command"].casefold()]
    if args.exposed_only:
        result = [r for r in result if r["exposure"] == "ALL INTERFACES"]
    return result

def build_parser():
    parser = argparse.ArgumentParser(
        description="Show listening TCP ports and bound UDP ports with their owning processes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="Examples:\n  python monitor.py\n  sudo python monitor.py --protocol tcp\n"
               "  python monitor.py --port 22 --port 443\n  sudo python monitor.py --watch --interval 3\n"
               "  sudo python monitor.py --exposed-only --json\n"
               "  sudo python monitor.py --export reports/open-ports.csv --format csv")
    parser.add_argument("--protocol", choices=("all", "tcp", "udp"), default="all")
    parser.add_argument("-p", "--port", type=int, action="append", help="filter by port; repeatable")
    parser.add_argument("--pid", type=int, help="filter by process ID")
    parser.add_argument("--process", help="case-insensitive process name/command filter")
    parser.add_argument("--exposed-only", action="store_true", help="show wildcard-bound sockets only")
    parser.add_argument("--watch", action="store_true", help="refresh continuously")
    parser.add_argument("--interval", type=float, default=5.0, help="refresh interval in seconds")
    parser.add_argument("--duration", type=float, help="stop after N seconds when watching")
    parser.add_argument("--json", action="store_true", help="emit JSON Lines to stdout")
    parser.add_argument("--export", metavar="PATH", help="append results to CSV or JSONL")
    parser.add_argument("--format", choices=("csv", "json"), default="csv")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--log-file")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--version", action="version", version="Open Ports Checker 1.0.0")
    return parser

def validate_args(args):
    if args.interval <= 0:
        raise ValueError("--interval must be greater than 0.")
    if args.duration is not None and args.duration <= 0:
        raise ValueError("--duration must be greater than 0.")
    if args.port and any(p < 1 or p > 65535 for p in args.port):
        raise ValueError("Ports must be between 1 and 65535.")
    if args.pid is not None and args.pid <= 0:
        raise ValueError("--pid must be a positive integer.")

def render(records, color=True):
    tcp = sum(r["protocol"] == "tcp" for r in records)
    udp = sum(r["protocol"] == "udp" for r in records)
    exposed = sum(r["exposure"] == "ALL INTERFACES" for r in records)
    if CONSOLE and color:
        table = Table(title="OPEN PORTS CHECKER", header_style="bold cyan")
        for name, justify in [("PROTO", "left"), ("LOCAL ADDRESS", "left"), ("PORT", "right"),
                              ("STATE", "left"), ("PID", "right"), ("PROCESS", "left"),
                              ("USER", "left"), ("EXPOSURE", "left")]:
            table.add_column(name, justify=justify, overflow="fold")
        for r in records:
            table.add_row(r["protocol"].upper(), r["local_address"], str(r["port"]), r["state"],
                          str(r["pid"] or "-"), r["process"], r["username"] or "-", r["exposure"])
        CONSOLE.clear()
        CONSOLE.print(table)
        CONSOLE.print(f"Total: {len(records)} | TCP: {tcp} | UDP: {udp} | Wildcard-bound: {exposed} | Ctrl+C to stop")
        return
    print("\033[2J\033[H", end="")
    print("OPEN PORTS CHECKER")
    print("=" * 112)
    print(f"{'PROTO':<7} {'LOCAL ADDRESS':<25} {'PORT':>6} {'STATE':<8} {'PID':>8} {'PROCESS':<24} {'USER':<16} EXPOSURE")
    print("-" * 112)
    for r in records:
        print(f"{r['protocol'].upper():<7} {r['local_address']:<25.25} {r['port']:>6} {r['state']:<8} "
              f"{str(r['pid'] or '-'):>8} {r['process']:<24.24} {(r['username'] or '-'):<16.16} {r['exposure']}")
    if not records:
        print("No matching listening/bound ports found.")
    print("-" * 112)
    print(f"Total: {len(records)} | TCP: {tcp} | UDP: {udp} | Wildcard-bound: {exposed} | Ctrl+C to stop")

def append_export(path, output_format, records):
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        with target.open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return
    exists = target.exists() and target.stat().st_size > 0
    with target.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerows(records)

def configure_logging(path=None, verbose=False):
    handlers = [logging.StreamHandler()]
    if path:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(target, encoding="utf-8"))
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s", handlers=handlers, force=True)

def run(args):
    validate_args(args)
    started, stop = time.monotonic(), False
    def request_stop(_signum, _frame):
        nonlocal stop
        stop = True
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, request_stop)
    while not stop:
        records = filter_records(collect_listeners(), args)
        if args.json:
            for record in records:
                print(json.dumps(record, ensure_ascii=False), flush=True)
        else:
            render(records, color=not args.no_color)
        if args.export:
            append_export(args.export, args.format, records)
        if not args.watch or (args.duration is not None and time.monotonic() - started >= args.duration):
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
