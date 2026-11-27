#!/usr/bin/env python3
"""
Hardware Inventory & Serial Number Harvester
Cross-platform inventory collector (Linux and Windows) with SQLite/CSV persistence.
Serial collection can be disabled with --redact-serials.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import platform
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

APP = "hardware_inventory"
DEFAULT_DB = Path.home() / ".local" / "share" / APP / "inventory.sqlite3"
DEFAULT_CSV = Path.home() / ".local" / "share" / APP / "inventory.csv"
SCHEMA = """
CREATE TABLE IF NOT EXISTS inventory (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 collected_at TEXT NOT NULL,
 hostname TEXT NOT NULL,
 os_name TEXT NOT NULL,
 os_version TEXT,
 architecture TEXT,
 manufacturer TEXT,
 model TEXT,
 motherboard_manufacturer TEXT,
 motherboard_product TEXT,
 motherboard_serial TEXT,
 bios_vendor TEXT,
 bios_version TEXT,
 bios_date TEXT,
 cpu_model TEXT,
 cpu_physical_cores INTEGER,
 cpu_logical_cores INTEGER,
 ram_total_bytes INTEGER,
 disks_json TEXT NOT NULL,
 source_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_inventory_host_time ON inventory(hostname, collected_at);
"""

def run_cmd(args: list[str], timeout: int = 12) -> str:
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""

def clean(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in {"none", "unknown", "not specified", "to be filled by o.e.m.", "default string", "system serial number"}:
        return None
    return s

def parse_linux_dmi() -> dict[str, Any]:
    result: dict[str, Any] = {}
    base = Path("/sys/class/dmi/id")
    mapping = {
        "manufacturer": "sys_vendor", "model": "product_name",
        "motherboard_manufacturer": "board_vendor", "motherboard_product": "board_name",
        "motherboard_serial": "board_serial", "bios_vendor": "bios_vendor",
        "bios_version": "bios_version", "bios_date": "bios_date",
    }
    for key, filename in mapping.items():
        try:
            result[key] = clean((base / filename).read_text(errors="ignore"))
        except OSError:
            result[key] = None
    if not result.get("motherboard_serial"):
        for key, cmd in [("motherboard_serial", ["sudo", "-n", "dmidecode", "-s", "baseboard-serial-number"]),
                          ("bios_version", ["sudo", "-n", "dmidecode", "-s", "bios-version"])]:
            result[key] = clean(run_cmd(cmd))
    return result

def parse_windows_powershell() -> dict[str, Any]:
    ps = shutil.which("powershell") or shutil.which("pwsh")
    if not ps:
        return {}
    script = r"""
$cs=Get-CimInstance Win32_ComputerSystem
$bb=Get-CimInstance Win32_BaseBoard
$bios=Get-CimInstance Win32_BIOS
$cpu=Get-CimInstance Win32_Processor | Select-Object -First 1
$ram=(Get-CimInstance Win32_PhysicalMemory | Measure-Object Capacity -Sum).Sum
$disks=Get-CimInstance Win32_DiskDrive | Select-Object Model,SerialNumber,Size,Status,InterfaceType
[PSCustomObject]@{
 Manufacturer=$cs.Manufacturer; Model=$cs.Model
 BoardManufacturer=$bb.Manufacturer; BoardProduct=$bb.Product; BoardSerial=$bb.SerialNumber
 BiosVendor=$bios.Manufacturer; BiosVersion=($bios.SMBIOSBIOSVersion -join ' '); BiosDate=$bios.ReleaseDate
 CpuName=$cpu.Name; CpuCores=$cpu.NumberOfCores; CpuThreads=$cpu.NumberOfLogicalProcessors
 RamBytes=$ram; Disks=$disks
} | ConvertTo-Json -Depth 5 -Compress
"""
    output = run_cmd([ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script], timeout=20)
    try:
        obj = json.loads(output)
        return {
            "manufacturer": clean(obj.get("Manufacturer")), "model": clean(obj.get("Model")),
            "motherboard_manufacturer": clean(obj.get("BoardManufacturer")),
            "motherboard_product": clean(obj.get("BoardProduct")),
            "motherboard_serial": clean(obj.get("BoardSerial")),
            "bios_vendor": clean(obj.get("BiosVendor")), "bios_version": clean(obj.get("BiosVersion")),
            "bios_date": clean(obj.get("BiosDate")), "cpu_model": clean(obj.get("CpuName")),
            "cpu_physical_cores": obj.get("CpuCores"), "cpu_logical_cores": obj.get("CpuThreads"),
            "ram_total_bytes": int(obj.get("RamBytes") or 0),
            "disks": obj.get("Disks") or [],
        }
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        return {}

def get_cpu_ram() -> dict[str, Any]:
    data: dict[str, Any] = {}
    if platform.system() == "Linux":
        cpu = run_cmd(["bash", "-c", "awk -F: '/model name/{gsub(/^ +/, \"\", $2); print $2; exit}' /proc/cpuinfo"])
        try:
            text = Path("/proc/meminfo").read_text()
            match = re.search(r"^MemTotal:\s+(\d+)\s+kB", text, re.M)
            if match: data["ram_total_bytes"] = int(match.group(1)) * 1024
            cores = len(re.findall(r"^processor\s*:", Path("/proc/cpuinfo").read_text(), re.M))
            data["cpu_logical_cores"] = cores or None
            data["cpu_model"] = clean(cpu)
            data["cpu_physical_cores"] = None
        except OSError:
            pass
    else:
        try:
            import psutil
            data["ram_total_bytes"] = int(psutil.virtual_memory().total)
            data["cpu_logical_cores"] = psutil.cpu_count(logical=True)
            data["cpu_physical_cores"] = psutil.cpu_count(logical=False)
        except ImportError:
            pass
    return data

def linux_disks(redact: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    lsblk = shutil.which("lsblk")
    if lsblk:
        raw = run_cmd([lsblk, "-J", "-b", "-d", "-o", "NAME,MODEL,SERIAL,SIZE,TYPE,ROTA,TRAN"])
        try:
            for item in json.loads(raw).get("blockdevices", []):
                if item.get("type") != "disk":
                    continue
                rows.append({"name": item.get("name"), "model": clean(item.get("model")),
                    "serial": None if redact else clean(item.get("serial")), "size_bytes": item.get("size"),
                    "rotational": item.get("rota"), "transport": item.get("tran"), "smart_health": None})
        except (json.JSONDecodeError, TypeError):
            pass
    smartctl = shutil.which("smartctl")
    if smartctl:
        for disk in rows:
            device = "/dev/" + str(disk["name"])
            output = run_cmd([smartctl, "-H", device])
            if output:
                m = re.search(r"SMART overall-health self-assessment test result:\s*(\S.+)", output)
                if not m:
                    m = re.search(r"SMART Health Status:\s*(\S.+)", output)
                disk["smart_health"] = clean(m.group(1)) if m else ("SMART data available; health line not recognized" if output else None)
    return rows

def collect(redact: bool = False) -> dict[str, Any]:
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    system = platform.system()
    hardware: dict[str, Any] = {}
    if system == "Linux":
        hardware.update(parse_linux_dmi())
        hardware.update(get_cpu_ram())
        disks = linux_disks(redact)
    elif system == "Windows":
        hardware.update(parse_windows_powershell())
        disks = hardware.pop("disks", [])
    else:
        hardware.update(get_cpu_ram())
        disks = []
    if redact:
        hardware["motherboard_serial"] = None
        for d in disks:
            d["serial"] = None
    hardware.setdefault("ram_total_bytes", None)
    hardware.setdefault("cpu_model", None)
    hardware.setdefault("cpu_physical_cores", None)
    hardware.setdefault("cpu_logical_cores", None)
    return {
        "collected_at": now, "hostname": socket.gethostname(),
        "os_name": f"{system} {platform.release()}", "os_version": platform.version(),
        "architecture": platform.machine(), "manufacturer": hardware.get("manufacturer"),
        "model": hardware.get("model"), "motherboard_manufacturer": hardware.get("motherboard_manufacturer"),
        "motherboard_product": hardware.get("motherboard_product"), "motherboard_serial": hardware.get("motherboard_serial"),
        "bios_vendor": hardware.get("bios_vendor"), "bios_version": hardware.get("bios_version"),
        "bios_date": hardware.get("bios_date"), "cpu_model": hardware.get("cpu_model"),
        "cpu_physical_cores": hardware.get("cpu_physical_cores"), "cpu_logical_cores": hardware.get("cpu_logical_cores"),
        "ram_total_bytes": hardware.get("ram_total_bytes"), "disks": disks, "sources": {"collector": "native OS tools", "redacted": redact},
    }

def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)

def save_db(record: dict[str, Any], path: Path) -> None:
    init_db(path)
    fields = ["collected_at","hostname","os_name","os_version","architecture","manufacturer","model",
        "motherboard_manufacturer","motherboard_product","motherboard_serial","bios_vendor","bios_version",
        "bios_date","cpu_model","cpu_physical_cores","cpu_logical_cores","ram_total_bytes","disks_json","source_json"]
    values = [record.get(f) for f in fields[:-2]] + [json.dumps(record["disks"], ensure_ascii=False),
        json.dumps(record["sources"], ensure_ascii=False)]
    with sqlite3.connect(path) as db:
        db.execute(f"INSERT INTO inventory ({','.join(fields)}) VALUES ({','.join(['?']*len(fields))})", values)

def export_csv(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["collected_at","hostname","os_name","os_version","architecture","manufacturer","model",
        "motherboard_manufacturer","motherboard_product","motherboard_serial","bios_vendor","bios_version",
        "bios_date","cpu_model","cpu_physical_cores","cpu_logical_cores","ram_total_bytes","disks_json","source_json"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = {k: record.get(k) for k in fields}
            row["disks_json"] = json.dumps(record.get("disks", []), ensure_ascii=False)
            row["source_json"] = json.dumps(record.get("sources", {}), ensure_ascii=False)
            writer.writerow(row)

def bytes_human(value: int | None) -> str:
    if not value: return "Unknown"
    n=float(value)
    for unit in ("B","KB","MB","GB","TB","PB"):
        if n < 1024 or unit == "PB": return f"{n:.1f} {unit}"
        n /= 1024
    return str(value)

def print_record(r: dict[str, Any]) -> None:
    print("\n\033[1;36m╭─ Hardware Inventory ─────────────────────────────╮\033[0m")
    for label,key in [("Host","hostname"),("OS","os_name"),("Manufacturer","manufacturer"),("Model","model"),
        ("Board vendor","motherboard_manufacturer"),("Board product","motherboard_product"),
        ("Board serial","motherboard_serial"),("BIOS vendor","bios_vendor"),("BIOS version","bios_version"),
        ("BIOS date","bios_date"),("CPU","cpu_model"),("Physical cores","cpu_physical_cores"),
        ("Logical cores","cpu_logical_cores"),("Installed RAM","ram_total_bytes")]:
        val=r.get(key)
        if key=="ram_total_bytes": val=bytes_human(val)
        print(f"│ {label:<16}: {val or 'Unknown'}")
    print("├─ Disks ─────────────────────────────────────────")
    for d in r.get("disks", []):
        print(f"│ {d.get('name','?'):<10} {d.get('model') or 'Unknown model'} | {bytes_human(d.get('size_bytes'))} | Serial: {d.get('serial') or 'redacted/unknown'} | SMART: {d.get('smart_health') or 'N/A'}")
    print("╰─────────────────────────────────────────────────\n")

def main() -> int:
    parser=argparse.ArgumentParser(description="Cross-platform hardware inventory collector for Linux and Windows")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite database path (default: {DEFAULT_DB})")
    parser.add_argument("--csv", type=Path, help="Export this collection to CSV")
    parser.add_argument("--redact-serials", action="store_true", help="Omit motherboard and disk serial numbers")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--quiet", action="store_true", help="Suppress human-readable output")
    parser.add_argument("--watch", type=int, metavar="SECONDS", help="Repeat collection at interval (minimum 30 seconds)")
    parser.add_argument("--no-db", action="store_true", help="Skip SQLite storage")
    args=parser.parse_args()
    if args.watch is not None and args.watch < 30:
        parser.error("--watch interval must be at least 30 seconds")
    try:
        while True:
            record=collect(args.redact_serials)
            if not args.no_db:
                save_db(record,args.db)
            if args.csv:
                export_csv([record],args.csv)
            if args.json:
                print(json.dumps(record,indent=2,ensure_ascii=False))
            elif not args.quiet:
                print_record(record)
            if args.watch is None: break
            time.sleep(args.watch)
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
