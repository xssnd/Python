#!/usr/bin/env python3
"""
Hybrid Patch Compliance Auditor
Cross-platform inventory and patch posture report for Linux and Windows.

Linux:
  - Detects apt/dpkg or dnf/yum/rpm.
  - Checks pending updates using the local package manager (repository metadata).
  - Retrieves vendor security-advisory reference data from Debian/Ubuntu APIs.
Windows:
  - Collects installed KB hotfixes via PowerShell.
  - Retrieves Microsoft Security Response Center (MSRC) update metadata for reference.
Important: vendor advisories are correlated as reference context, not a definitive
package-to-CVE remediation verdict. A definitive status requires distro-specific
version mapping and backport-aware comparison.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

APP = "Hybrid Patch Compliance Auditor"
VERSION = "1.0.0"
USER_AGENT = "HybridPatchComplianceAuditor/1.0 (+https://github.com/xssnd/Python)"
TIMEOUT = 18

def run_cmd(cmd: list[str], timeout: int = 40) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=timeout, check=False)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)

def fetch_json(url: str, timeout: int = TIMEOUT) -> Any:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))

def get_os() -> dict[str, str]:
    info = {"system": platform.system(), "name": platform.platform(),
            "release": platform.release(), "version": platform.version()}
    if info["system"] == "Linux":
        try:
            data = {}
            with open("/etc/os-release", encoding="utf-8") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.rstrip().split("=", 1)
                        data[k] = v.strip('"')
            info.update({"distro": data.get("ID", "unknown"),
                         "distro_name": data.get("PRETTY_NAME", "Linux"),
                         "distro_version": data.get("VERSION_ID", "")})
        except OSError:
            pass
    return info

def linux_updates() -> dict[str, Any]:
    result = {"manager": "unknown", "updates": [], "error": None}
    if shutil.which("apt") and shutil.which("dpkg-query"):
        result["manager"] = "apt"
        # Refresh is intentionally NOT run; this remains read-only and uses cached indexes.
        rc, out, err = run_cmd(["apt", "list", "--upgradable"], timeout=40)
        if rc not in (0,):
            result["error"] = err or f"apt exited with status {rc}"
        else:
            for line in out.splitlines():
                if line.startswith("Listing") or not line.strip() or "/" not in line:
                    continue
                fields = line.split()
                if len(fields) >= 2:
                    result["updates"].append({"package": fields[0].split("/")[0],
                                          "candidate": fields[1],
                                          "source": "apt cached repository metadata"})
        result["note"] = "Run apt update first for fresh repository metadata; auditor does not refresh indexes."
        return result
    if shutil.which("dnf"):
        result["manager"] = "dnf"
        rc, out, err = run_cmd(["dnf", "-q", "check-update"], timeout=60)
        # dnf check-update returns 100 when updates exist.
        if rc not in (0, 100):
            result["error"] = err or f"dnf exited with status {rc}"
        for line in out.splitlines():
            fields = line.split()
            if len(fields) >= 3 and "." in fields[0]:
                result["updates"].append({"package": fields[0], "candidate": fields[1],
                                         "repository": fields[2], "source": "dnf"})
        return result
    if shutil.which("yum"):
        result["manager"] = "yum"
        rc, out, err = run_cmd(["yum", "-q", "check-update"], timeout=60)
        if rc not in (0, 100):
            result["error"] = err or f"yum exited with status {rc}"
        for line in out.splitlines():
            fields = line.split()
            if len(fields) >= 3 and "." in fields[0]:
                result["updates"].append({"package": fields[0], "candidate": fields[1],
                                         "repository": fields[2], "source": "yum"})
        return result
    result["error"] = "No supported package manager found (apt, dnf, yum)."
    return result

def debian_advisory_summary() -> dict[str, Any]:
    url = "https://security-tracker.debian.org/tracker/data/json"
    try:
        data = fetch_json(url)
        return {"source": url, "status": "available",
                "package_count": len(data) if isinstance(data, dict) else None,
                "note": "Debian Security Tracker reference feed downloaded; this script does not automatically map every installed package to affected releases."}
    except Exception as exc:
        return {"source": url, "status": "unavailable", "error": str(exc)}

def ubuntu_oval_summary() -> dict[str, Any]:
    # Official Ubuntu OVAL feeds, version-specific; select a feed based on detected release.
    osinfo = get_os()
    release = osinfo.get("distro_version", "")
    if osinfo.get("system") == "Linux":
        try:
            with open("/etc/os-release", encoding="utf-8") as os_file:
                for os_line in os_file:
                    if os_line.startswith("VERSION_CODENAME="):
                        release = os_line.split("=", 1)[1].strip().strip("\\"")
                        break
        except OSError:
            pass
    url = "https://security.ubuntu.com/oval/com.ubuntu." + (release or "unknown") + ".usn.oval.xml"
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=TIMEOUT) as response:
            raw = response.read()
        # Lightweight count of USN identifiers; avoid pretending to parse remediation state.
        usn_count = len(set(re.findall(rb"USN-[0-9]+-[0-9]+", raw)))
        return {"source": url, "status": "available", "bytes": len(raw),
                "usn_count": usn_count,
                "note": "Official Ubuntu OVAL feed fetched for reference; package-level fix status requires distro-aware version comparison."}
    except Exception as exc:
        return {"source": url, "status": "unavailable", "error": str(exc)}

def windows_inventory() -> dict[str, Any]:
    ps = shutil.which("powershell") or shutil.which("pwsh")
    if not ps:
        return {"error": "PowerShell not found. Run this tool in Windows PowerShell or install PowerShell 7."}
    script = "Get-HotFix | Select-Object HotFixID,Description,InstalledOn | ConvertTo-Json -Compress"
    rc, out, err = run_cmd([ps, "-NoProfile", "-NonInteractive", "-Command", script], timeout=60)
    if rc != 0:
        return {"error": err or "PowerShell hotfix inventory failed"}
    try:
        parsed = json.loads(out) if out else []
        if isinstance(parsed, dict):
            parsed = [parsed]
        return {"hotfix_count": len(parsed), "hotfixes": parsed}
    except json.JSONDecodeError as exc:
        return {"error": f"Could not parse PowerShell output: {exc}", "raw": out[:2000]}

def msrc_reference() -> dict[str, Any]:
    # Microsoft Security Update Guide API: current CVRF document collection.
    url = "https://api.msrc.microsoft.com/cvrf/v3.0/updates"
    try:
        data = fetch_json(url)
        updates = data.get("value", []) if isinstance(data, dict) else []
        return {"source": url, "status": "available", "update_count": len(updates),
                "recent_titles": [u.get("Title") or u.get("Alias") for u in updates[:8]],
                "note": "MSRC update catalog reference. KB-to-OS build applicability is not automatically asserted."}
    except Exception as exc:
        return {"source": url, "status": "unavailable", "error": str(exc)}

def build_report(no_vendor: bool = False) -> dict[str, Any]:
    osinfo = get_os()
    report: dict[str, Any] = {
        "tool": APP, "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": platform.node() or "unknown",
        "os": osinfo, "mode": "read-only",
    }
    if osinfo["system"] == "Linux":
        report["package_updates"] = linux_updates()
        if not no_vendor:
            distro = osinfo.get("distro", "").lower()
            if distro in ("ubuntu",):
                report["vendor_security_feed"] = ubuntu_oval_summary()
            elif distro in ("debian",):
                report["vendor_security_feed"] = debian_advisory_summary()
            else:
                report["vendor_security_feed"] = {
                    "status": "not_configured",
                    "note": "Vendor advisory integration is currently enabled for Debian and Ubuntu; other distributions are inventoried via their package manager."
                }
    elif osinfo["system"] == "Windows":
        report["installed_hotfixes"] = windows_inventory()
        if not no_vendor:
            report["vendor_security_feed"] = msrc_reference()
    else:
        report["status"] = "unsupported_os"
        report["message"] = "Supported targets: Linux (apt/dnf/yum) and Windows."
    return report

def human(report: dict[str, Any]) -> None:
    print(f"\n{APP}  v{VERSION}")
    print("=" * 66)
    print(f"Host: {report.get('host')} | OS: {report.get('os', {}).get('distro_name', report.get('os', {}).get('name'))}")
    print(f"Generated: {report.get('generated_at')} | Mode: read-only")
    if "package_updates" in report:
        updates = report["package_updates"]
        print(f"Package manager: {updates.get('manager')}")
        pending = updates.get("updates", [])
        print(f"Pending package updates: {len(pending)}")
        for item in pending[:30]:
            print(f"  • {item.get('package')} -> {item.get('candidate')}")
        if len(pending) > 30:
            print(f"  ... and {len(pending)-30} more (see JSON/CSV output)")
        if updates.get("note"):
            print(f"Note: {updates['note']}")
        if updates.get("error"):
            print(f"Warning: {updates['error']}")
    if "installed_hotfixes" in report:
        hotfix = report["installed_hotfixes"]
        if hotfix.get("error"):
            print(f"Windows hotfix inventory error: {hotfix['error']}")
        else:
            print(f"Installed Windows hotfix entries: {hotfix.get('hotfix_count', 0)}")
            for kb in hotfix.get("hotfixes", [])[:20]:
                print(f"  • {kb.get('HotFixID')} | {kb.get('Description')} | {kb.get('InstalledOn')}")
    feed = report.get("vendor_security_feed")
    if feed:
        print("\nVendor advisory API:")
        print(f"  Status: {feed.get('status', 'unknown')}")
        print(f"  Source: {feed.get('source', 'n/a')}")
        if feed.get("error"):
            print(f"  Error: {feed['error']}")
        if feed.get("note"):
            print(f"  Note: {feed['note']}")
        if feed.get("package_count") is not None:
            print(f"  Advisory packages: {feed['package_count']}")
        if feed.get("usn_count") is not None:
            print(f"  Ubuntu USN references: {feed['usn_count']}")
        if feed.get("update_count") is not None:
            print(f"  MSRC update entries: {feed['update_count']}")
    print("\nCompliance summary")
    print("-" * 66)
    if "package_updates" in report:
        n = len(report["package_updates"].get("updates", []))
        print(f"  Pending updates: {n}")
        print("  Status: " + ("PATCHES_PENDING" if n else "NO_PENDING_UPDATES_IN_CACHED_METADATA"))
        print("  (This is repository/package-manager status, not a CVE-level guarantee.)")
    elif "installed_hotfixes" in report:
        print("  Status: INVENTORY_ONLY")
        print("  (KB inventory and MSRC feed are reference data; OS-build applicability is not yet evaluated.)")
    print()

def write_csv(report: dict[str, Any], path: str) -> None:
    rows = []
    for item in report.get("package_updates", {}).get("updates", []):
        rows.append({"host": report.get("host"), "platform": "Linux", "kind": "package_update",
                     "item": item.get("package"), "target_version": item.get("candidate"),
                     "details": json.dumps(item, ensure_ascii=False)})
    for item in report.get("installed_hotfixes", {}).get("hotfixes", []):
        rows.append({"host": report.get("host"), "platform": "Windows", "kind": "installed_kb",
                     "item": item.get("HotFixID"), "target_version": "",
                     "details": json.dumps(item, ensure_ascii=False)})
    fields = ["host", "platform", "kind", "item", "target_version", "details"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventory OS patch posture and cross-check official vendor advisory feeds.",
        epilog="Read-only. Does not install updates or refresh package indexes.",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    parser.add_argument("--csv", metavar="FILE", help="Export inventory/update rows to CSV")
    parser.add_argument("--no-vendor", action="store_true", help="Skip online vendor advisory requests")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args = parser.parse_args()
    try:
        report = build_report(no_vendor=args.no_vendor)
        if args.csv:
            write_csv(report, args.csv)
            print(f"CSV exported: {args.csv}")
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            human(report)
        return 1 if report.get("package_updates", {}).get("updates") else 0
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130

if __name__ == "__main__":
    raise SystemExit(main())
