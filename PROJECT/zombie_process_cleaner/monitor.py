#!/usr/bin/env python3
"""Detect Linux zombie processes and safely inspect their parent processes."""
from __future__ import annotations
import argparse, csv, json, logging, os, signal, sys, time
from datetime import datetime, timezone
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except ImportError:
    Console = Panel = Table = None

LOG = logging.getLogger("zombie_process_cleaner")
console = Console() if Console else None
FIELDS = ["pid", "ppid", "name", "username", "age_seconds", "started_at", "parent_name", "parent_status"]

def require_dependencies():
    if psutil is None:
        raise RuntimeError("Missing dependency: run 'python -m pip install -r requirements.txt'")
    if not hasattr(psutil, "STATUS_ZOMBIE"):
        raise RuntimeError("psutil does not expose zombie status; upgrade psutil.")

def safe(call, default=None):
    try:
        return call()
    except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied, OSError, ProcessLookupError):
        return default

def collect_zombies(now=None, min_age=0):
    """Collect zombie records without signaling or modifying any process."""
    require_dependencies()
    if min_age < 0:
        raise ValueError("min_age cannot be negative")
    now = time.time() if now is None else now
    records = []
    for proc in psutil.process_iter():
        try:
            with proc.oneshot():
                if proc.status() != psutil.STATUS_ZOMBIE:
                    continue
                pid, ppid = proc.pid, proc.ppid()
                name = safe(proc.name, "?") or "?"
                username = safe(proc.username, "?") or "?"
                created = safe(proc.create_time, None)
            age = max(0.0, now - created) if created is not None else None
            if age is not None and age < min_age:
                continue
            parent_name, parent_status = "unknown", "unknown"
            if ppid:
                parent = safe(lambda: psutil.Process(ppid), None)
                if parent is not None:
                    parent_name = safe(parent.name, "unknown") or "unknown"
                    parent_status = safe(parent.status, "unknown") or "unknown"
            records.append({
                "pid": int(pid), "ppid": int(ppid or 0), "name": str(name),
                "username": str(username), "age_seconds": round(age, 1) if age is not None else None,
                "started_at": datetime.fromtimestamp(created, timezone.utc).isoformat(timespec="seconds") if created else None,
                "parent_name": str(parent_name), "parent_status": str(parent_status),
            })
        except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied, ProcessLookupError, PermissionError):
            continue
        except (OSError, ValueError, TypeError):
            LOG.debug("Unable to inspect PID %s", getattr(proc, "pid", "?"), exc_info=True)
    return sorted(records, key=lambda row: (row["ppid"], row["pid"]))

def group_by_parent(records):
    groups = {}
    for row in records:
        group = groups.setdefault(row["ppid"], {
            "ppid": row["ppid"], "parent_name": row["parent_name"],
            "parent_status": row["parent_status"], "count": 0, "zombie_pids": []})
        group["count"] += 1
        group["zombie_pids"].append(row["pid"])
    return sorted(groups.values(), key=lambda row: (-row["count"], row["ppid"]))

def build_report(records, threshold=1):
    if threshold < 1:
        raise ValueError("threshold must be at least 1")
    groups = group_by_parent(records)
    oldest = max((r["age_seconds"] for r in records if r["age_seconds"] is not None), default=None)
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hostname": os.environ.get("COMPUTERNAME") or getattr(os, "uname", lambda: None)().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "unknown"),
        "zombie_count": len(records), "parent_count": len(groups), "oldest_age_seconds": oldest,
        "threshold": threshold, "alert": len(records) >= threshold,
        "zombies": records, "parents": groups,
        "note": "Zombies have exited. Their parent must reap them with wait()/waitpid().",
    }

def export_report(report, path, output_format="json"):
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    elif output_format == "csv":
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(report["zombies"])
    else:
        raise ValueError("format must be json or csv")
    return target

def signal_parent(parent_pid, records, assume_yes=False):
    """Send SIGCHLD to a verified parent; this is not a guaranteed cleanup."""
    require_dependencies()
    if not hasattr(signal, "SIGCHLD"):
        raise RuntimeError("SIGCHLD is not supported on this platform.")
    if parent_pid <= 1 or parent_pid == os.getpid():
        raise ValueError("Refusing to signal PID 1, this cleaner, or an invalid parent.")
    if not any(row["ppid"] == parent_pid for row in records):
        raise ValueError(f"No detected zombie currently has parent PID {parent_pid}.")
    parent = psutil.Process(parent_pid)
    if not parent.is_running() or parent.status() == psutil.STATUS_ZOMBIE:
        raise RuntimeError("Parent is no longer running or is itself a zombie.")
    if not assume_yes:
        answer = input(f"Send SIGCHLD to parent {parent_pid} ({parent.name()})? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            return False
    os.kill(parent_pid, signal.SIGCHLD)
    LOG.warning("Sent SIGCHLD to PID %s; cleanup depends on parent signal handling.", parent_pid)
    return True

def render_dashboard(report, plain=False):
    if console and Table and Panel and not plain:
        console.clear()
        console.print(Panel.fit(
            f"[bold cyan]ZOMBIE PROCESS CLEANER[/bold cyan]\nHost: {report['hostname']} | "
            f"Zombies: [bold {'red' if report['alert'] else 'green'}]{report['zombie_count']}[/] | "
            f"Parents: {report['parent_count']} | Threshold: {report['threshold']}", border_style="cyan"))
        table = Table(title="Detected Zombie Processes", header_style="bold magenta")
        for col in ("PID", "PPID", "PROCESS", "USER", "AGE", "PARENT", "PARENT STATE"):
            table.add_column(col)
        for row in report["zombies"]:
            age = f"{row['age_seconds']:.0f}s" if row["age_seconds"] is not None else "N/A"
            table.add_row(str(row["pid"]), str(row["ppid"]), row["name"], row["username"],
                          age, row["parent_name"], row["parent_status"])
        if not report["zombies"]:
            table.add_row("-", "-", "No zombie processes detected", "-", "-", "-", "-")
        console.print(table)
        parents = Table(title="Parent Process Summary", header_style="bold yellow")
        for col in ("PPID", "PARENT", "STATE", "COUNT", "ZOMBIE PIDs"):
            parents.add_column(col)
        for row in report["parents"]:
            parents.add_row(str(row["ppid"]), row["parent_name"], row["parent_status"],
                            str(row["count"]), ", ".join(map(str, row["zombie_pids"])))
        if report["parents"]:
            console.print(parents)
        console.print("[dim]Read-only scan. Zombies are already exited; investigate the parent.[/dim]")
        return
    print("=" * 76, "\n ZOMBIE PROCESS CLEANER")
    print(f"Host: {report['hostname']} | Zombies: {report['zombie_count']} | Parents: {report['parent_count']}")
    if not report["zombies"]:
        print("No zombie processes detected.")
    for row in report["zombies"]:
        age = f"{row['age_seconds']:.0f}s" if row["age_seconds"] is not None else "N/A"
        print(f"PID {row['pid']:>7} PPID {row['ppid']:>7} {row['name']:<20} age={age:<8} parent={row['parent_name']}")
    print("A zombie cannot be killed; its parent must call wait()/waitpid().")

def configure_logging(path=None, verbose=False):
    handlers = [logging.StreamHandler()]
    if path:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(target, encoding="utf-8"))
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s", handlers=handlers, force=True)

def build_parser():
    parser = argparse.ArgumentParser(
        description="Detect and report Linux zombie processes. Safe/read-only by default.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=("Examples:\n  python monitor.py\n  python monitor.py --watch --interval 3\n"
                "  python monitor.py --min-age 60 --threshold 5\n"
                "  python monitor.py --export reports/zombies.json\n"
                "  python monitor.py --signal-parent 1234  # asks for confirmation\n"
                "  python monitor.py --signal-parent 1234 --yes"))
    parser.add_argument("--watch", action="store_true", help="continuously refresh dashboard")
    parser.add_argument("--interval", type=float, default=5.0, help="refresh interval in seconds")
    parser.add_argument("--min-age", type=float, default=0, help="minimum zombie age in seconds")
    parser.add_argument("--threshold", type=int, default=1, help="alert when zombie count reaches this number")
    parser.add_argument("--json", action="store_true", help="print report as JSON")
    parser.add_argument("--export", metavar="PATH", help="write JSON or CSV report")
    parser.add_argument("--format", choices=("json", "csv"), default="json", help="export format")
    parser.add_argument("--signal-parent", type=int, metavar="PPID", help="send SIGCHLD to a detected zombie's parent")
    parser.add_argument("--yes", action="store_true", help="explicitly approve signal without prompt")
    parser.add_argument("--log-file", help="optional diagnostic log")
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")
    parser.add_argument("--no-color", action="store_true", help="use plain terminal output")
    parser.add_argument("--version", action="version", version="Zombie Process Cleaner 1.0.0")
    return parser

def run(args):
    if args.interval <= 0: raise ValueError("--interval must be greater than zero")
    if args.min_age < 0: raise ValueError("--min-age cannot be negative")
    if args.threshold < 1: raise ValueError("--threshold must be at least 1")
    if args.yes and args.signal_parent is None: raise ValueError("--yes requires --signal-parent")
    stopped = False
    def stop_handler(_signum, _frame):
        nonlocal stopped
        stopped = True
    if args.watch:
        signal.signal(signal.SIGINT, stop_handler)
        if hasattr(signal, "SIGTERM"): signal.signal(signal.SIGTERM, stop_handler)
    while not stopped:
        records = collect_zombies(min_age=args.min_age)
        if args.signal_parent is not None:
            signal_parent(args.signal_parent, records, args.yes)
            time.sleep(0.5)
            records = collect_zombies(min_age=args.min_age)
        report = build_report(records, args.threshold)
        if args.json:
            print(json.dumps(report, ensure_ascii=False))
        else:
            render_dashboard(report, args.no_color)
            if report["alert"]: print(f"WARNING: zombie count reached threshold ({args.threshold}).")
        if args.export: export_report(report, args.export, args.format)
        if not args.watch: break
        deadline = time.monotonic() + args.interval
        while not stopped and time.monotonic() < deadline:
            time.sleep(min(0.2, max(0, deadline - time.monotonic())))
    return 0

def main(argv=None):
    args = build_parser().parse_args(argv)
    configure_logging(args.log_file, args.verbose)
    try:
        require_dependencies()
        if not sys.platform.startswith("linux"):
            raise RuntimeError("Zombie detection currently requires Linux /proc process-state support.")
        return run(args)
    except Exception as exc:
        LOG.error("%s", exc)
        return 2

if __name__ == "__main__":
    sys.exit(main())
