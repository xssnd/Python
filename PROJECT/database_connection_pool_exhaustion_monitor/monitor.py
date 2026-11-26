#!/usr/bin/env python3
"""Database Connection Pool Exhaustion Monitor (stdlib-first, optional DB drivers)."""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "1.0.0"

def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

def run_command(cmd: list[str], timeout: float = 5) -> str:
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return cp.stdout or ""
    except (OSError, subprocess.TimeoutExpired):
        return ""

def get_socket_count(host: str, port: int) -> tuple[int, str]:
    """Count established client-side sockets to host:port; may be partial due to permissions."""
    system = platform.system().lower()
    if system == "linux" and shutil.which("ss"):
        raw = run_command(["ss", "-H", "-tn", "state", "established"])
        count = 0
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) >= 5 and endpoint_matches(parts[-1], host, port):
                count += 1
        return count, "ss"
    if shutil.which("netstat"):
        args = ["netstat", "-ano"] if system == "windows" else ["netstat", "-tn"]
        raw = run_command(args)
        count = 0
        for line in raw.splitlines():
            if "ESTABLISHED" not in line.upper():
                continue
            parts = line.split()
            # Windows netstat: protocol, local, foreign, state, PID
            # Unix netstat: proto, recv, send, local, foreign, state
            endpoint = parts[-3] if system == "windows" and len(parts) >= 4 else (parts[-2] if len(parts) >= 6 else parts[-1])
            if endpoint_matches(endpoint, host, port):
                count += 1
        return count, "netstat"
    try:
        import psutil  # optional fallback
        count = sum(1 for c in psutil.net_connections(kind="tcp")
                    if c.status == psutil.CONN_ESTABLISHED and c.raddr and
                    c.raddr.port == port and host_matches(c.raddr.ip, host))
        return count, "psutil"
    except ImportError:
        return -1, "unavailable"

def endpoint_matches(endpoint: str, host: str, port: int) -> bool:
    endpoint = endpoint.strip()
    # ss/netstat IPv6 endpoints often look like [::1]:5432; Windows IPv4 host:port
    match = re.match(r"^(.+):(\d+)$", endpoint)
    if not match or int(match.group(2)) != port:
        return False
    remote_host = match.group(1).strip("[]")
    return host_matches(remote_host, host)

def host_matches(remote: str, target: str) -> bool:
    if remote.lower() == target.lower():
        return True
    try:
        return set(socket.getaddrinfo(remote, None)) & set(socket.getaddrinfo(target, None)) != set()
    except OSError:
        return False

def query_db(args: argparse.Namespace) -> dict[str, Any]:
    """Fetch live/max connection counts using optional driver and database-specific SQL."""
    db = args.db_type.lower()
    host, port = args.host, args.port
    username = args.username or os.getenv("DBMON_USER")
    password = args.password or os.getenv("DBMON_PASSWORD")
    timeout = args.connect_timeout
    result: dict[str, Any] = {"current": None, "maximum": None, "driver": "not installed", "db_error": None}
    try:
        if db == "postgresql":
            import psycopg  # type: ignore
            conn = psycopg.connect(host=host, port=port, user=username, password=password,
                                  dbname=args.database or "postgres", connect_timeout=timeout)
            result["driver"] = "psycopg"
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM pg_stat_activity")
                result["current"] = int(cur.fetchone()[0])
                cur.execute("SELECT setting::int FROM pg_settings WHERE name='max_connections'")
                result["maximum"] = int(cur.fetchone()[0])
            conn.close()
        elif db == "mysql":
            import mysql.connector  # type: ignore
            conn = mysql.connector.connect(host=host, port=port, user=username, password=password,
                                         database=args.database, connection_timeout=timeout)
            result["driver"] = "mysql-connector-python"
            cur = conn.cursor()
            cur.execute("SHOW GLOBAL STATUS LIKE 'Threads_connected'")
            result["current"] = int(cur.fetchone()[1])
            cur.execute("SHOW GLOBAL VARIABLES LIKE 'max_connections'")
            result["maximum"] = int(cur.fetchone()[1])
            cur.close(); conn.close()
        elif db in ("mssql", "sqlserver"):
            import pymssql  # type: ignore
            conn = pymssql.connect(server=host, port=port, user=username, password=password,
                                  database=args.database or "master", login_timeout=timeout)
            result["driver"] = "pymssql"
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM sys.dm_exec_sessions WHERE is_user_process=1")
            result["current"] = int(cur.fetchone()[0])
            cur.execute("SELECT value_in_use FROM sys.configurations WHERE name='user connections'")
            configured = int(cur.fetchone()[0])
            cur.execute("SELECT @@MAX_CONNECTIONS")
            engine_limit = int(cur.fetchone()[0])
            result["maximum"] = configured if configured > 0 else engine_limit
            cur.close(); conn.close()
        else:
            result["db_error"] = f"Unsupported DB type: {db}"
    except ImportError as exc:
        result["db_error"] = f"Missing optional driver: {exc.name}"
    except Exception as exc:
        result["db_error"] = f"{type(exc).__name__}: {exc}"
    return result

def percent_used(current: int, maximum: int) -> float:
    return 100.0 * current / maximum if maximum > 0 else 0.0

def notify_webhook(url: str | None, payload: dict[str, Any]) -> None:
    if not url:
        return
    try:
        request = urllib.request.Request(url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=5) as response:
            response.read(256)
    except Exception as exc:
        print(f"Webhook delivery failed: {exc}", file=sys.stderr)

def display(data: dict[str, Any], json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(data, indent=2, default=str))
        return
    db = data["database"]
    print("\n" + "=" * 68)
    print(f" DB CONNECTION CAPACITY MONITOR  |  {data['timestamp']}")
    print("=" * 68)
    print(f"Target : {data['target']} ({data['db_type']})")
    print(f"OS TCP : {data['os_connections']} established [{data['socket_tool']}]")
    if db["current"] is not None and db["maximum"] is not None:
        pct = data["usage_percent"]
        bar_width = 28
        filled = min(bar_width, int(bar_width * pct / 100))
        bar = "#" * filled + "-" * (bar_width - filled)
        print(f"DB     : {db['current']}/{db['maximum']} ({pct:.1f}%) [{bar}]")
        print(f"Status : {data['status']}")
    else:
        print("DB stats: unavailable (OS socket count is still reported)")
        if db["db_error"]:
            print(f"Reason  : {db['db_error']}")
    if data["status"] in ("WARNING", "CRITICAL"):
        print(f"ALERT  : {data['status']} - {data['message']}")
    print("=" * 68)

def append_csv(path: str, data: dict[str, Any]) -> None:
    file = Path(path).expanduser()
    file.parent.mkdir(parents=True, exist_ok=True)
    row = {"timestamp": data["timestamp"], "target": data["target"], "db_type": data["db_type"],
           "os_connections": data["os_connections"], "db_current": data["database"]["current"],
           "db_maximum": data["database"]["maximum"], "usage_percent": data["usage_percent"],
           "status": data["status"], "message": data["message"]}
    exists = file.exists()
    with file.open("a", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(row))
        if not exists:
            writer.writeheader()
        writer.writerow(row)

def load_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as fp:
            config = json.load(fp)
        if not isinstance(config, dict):
            raise ValueError("Configuration must be a JSON object.")
        return config
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"Config error: {exc}")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monitor database connection pressure and warn before connection exhaustion.")
    parser.add_argument("--config", help="JSON config file")
    parser.add_argument("--db-type", choices=["postgresql", "mysql", "mssql"], help="Database engine")
    parser.add_argument("--host", help="Database hostname/IP")
    parser.add_argument("--port", type=int, help="Database TCP port")
    parser.add_argument("--database", help="Database name (optional/default engine DB)")
    parser.add_argument("--username", help="Database user (or DBMON_USER env)")
    parser.add_argument("--password", help="Password (prefer DBMON_PASSWORD environment variable)")
    parser.add_argument("--warning", type=float, help="Warning threshold percent (default 75)")
    parser.add_argument("--critical", type=float, help="Critical threshold percent (default 90)")
    parser.add_argument("--interval", type=float, help="Repeat interval seconds (default 30)")
    parser.add_argument("--duration", type=float, help="Run duration seconds; 0 means forever when --watch is used")
    parser.add_argument("--watch", action="store_true", help="Monitor repeatedly")
    parser.add_argument("--csv", help="Append metrics to CSV")
    parser.add_argument("--webhook", help="Webhook URL for threshold alerts")
    parser.add_argument("--connect-timeout", type=int, default=4, help="DB connect timeout seconds")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of terminal dashboard")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    cfg = load_config(args.config)
    for key in ("db_type", "host", "port", "database", "username", "password", "warning", "critical", "interval", "duration", "csv", "webhook"):
        if getattr(args, key, None) is None and key in cfg:
            setattr(args, key, cfg[key])
    args.db_type = args.db_type or "postgresql"
    args.host = args.host or "127.0.0.1"
    defaults = {"postgresql": 5432, "mysql": 3306, "mssql": 1433}
    args.port = args.port or defaults[args.db_type]
    args.warning = args.warning if args.warning is not None else 75.0
    args.critical = args.critical if args.critical is not None else 90.0
    args.interval = args.interval if args.interval is not None else 30.0
    args.duration = args.duration if args.duration is not None else 0.0
    if args.warning < 0 or args.critical > 100 or args.warning >= args.critical:
        parser.error("Thresholds must satisfy 0 <= warning < critical <= 100.")
    if args.port < 1 or args.port > 65535 or args.interval < 1 or args.connect_timeout < 1:
        parser.error("Port, interval and connect timeout must be positive valid values.")
    start = time.monotonic()
    previous_status = None
    while True:
        sockets, tool = get_socket_count(args.host, args.port)
        db = query_db(args)
        pct = percent_used(db["current"], db["maximum"]) if db["current"] is not None and db["maximum"] else None
        if pct is None:
            status, message = "UNKNOWN", db["db_error"] or "Database metrics unavailable"
        elif pct >= args.critical:
            status, message = "CRITICAL", f"Connections at {pct:.1f}% of configured limit"
        elif pct >= args.warning:
            status, message = "WARNING", f"Connections at {pct:.1f}% of configured limit"
        else:
            status, message = "OK", "Connection usage within configured thresholds"
        payload = {"timestamp": now_iso(), "target": f"{args.host}:{args.port}", "db_type": args.db_type,
                   "os_connections": sockets, "socket_tool": tool, "database": db,
                   "usage_percent": pct, "status": status, "message": message}
        display(payload, args.json)
        if args.csv:
            append_csv(args.csv, payload)
        if status in ("WARNING", "CRITICAL") and status != previous_status:
            notify_webhook(args.webhook, payload)
        previous_status = status
        if not args.watch:
            return 0 if status == "OK" else 2 if status in ("WARNING", "CRITICAL") else 1
        if args.duration and time.monotonic() - start >= args.duration:
            return 0
        time.sleep(args.interval)

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        raise SystemExit(130)
