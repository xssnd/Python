#!/usr/bin/env python3
"""
SMB/NFS Share Permission Auditor
Read-only auditor for mounted network shares. Detects risky Unix mode bits,
world-accessible sensitive files, optional ACL findings, and mount metadata.
"""
from __future__ import annotations
import argparse, csv, json, os, re, shutil, stat, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.0.0"
SENSITIVE_EXT = {".pem", ".key", ".p12", ".pfx", ".env", ".sql", ".bak", ".backup", ".conf", ".cfg", ".ini", ".db", ".sqlite", ".kdbx"}
SENSITIVE_NAMES = {"id_rsa", "id_ed25519", "authorized_keys", "shadow", "passwd", "credentials", "secrets", "secret", "token"}
SEVERITY = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}

def mount_info():
    mounts=[]
    try:
        with open("/proc/mounts", encoding="utf-8", errors="replace") as f:
            for line in f:
                parts=line.split()
                if len(parts) < 4: continue
                source, target, fstype, options = parts[:4]
                if fstype.lower() in ("nfs","nfs4","cifs","smb3","fuse.sshfs"):
                    mounts.append({"source":source, "mountpoint":target, "fstype":fstype, "options":options.split(",")})
    except OSError: pass
    return mounts

def is_sensitive(path: Path):
    name=path.name.lower()
    return name in SENSITIVE_NAMES or path.suffix.lower() in SENSITIVE_EXT or any(k in name for k in ("secret","credential","password","private_key"))

def mode_str(mode): return stat.filemode(mode)

def check_acl(path: Path):
    """Return concise ACL observations; absence of getfacl means ACL audit unavailable."""
    tool=shutil.which("getfacl")
    if not tool: return []
    try:
        p=subprocess.run([tool, "-cp", str(path)], capture_output=True, text=True, timeout=3)
        lines=p.stdout.splitlines()
        findings=[]
        for line in lines:
            # Named user/group entries with effective write, and mask entries.
            if re.match(r"^(user|group):[^:]+:.*w", line) and not line.startswith(("user::","group::")):
                findings.append(line.strip())
            if line.startswith("other::") and "w" in line.split(":")[-1]:
                findings.append(line.strip())
        return findings
    except (OSError, subprocess.TimeoutExpired): return []

def classify(path, st, acl_lines):
    findings=[]
    mode=stat.S_IMODE(st.st_mode)
    sensitive=is_sensitive(path)
    if mode & stat.S_IWOTH:
        findings.append(("HIGH" if sensitive else "MEDIUM", "WORLD_WRITABLE", "Other/world has write permission"))
    if mode & stat.S_IROTH and sensitive:
        findings.append(("HIGH", "SENSITIVE_WORLD_READABLE", "Sensitive-looking file is readable by everyone"))
    if mode & stat.S_IWGRP and sensitive:
        findings.append(("HIGH", "SENSITIVE_GROUP_WRITABLE", "Sensitive-looking file is writable by group"))
    if mode == 0o777:
        findings.append(("HIGH", "MODE_777", "Mode is exactly 777"))
    for acl in acl_lines:
        findings.append(("HIGH" if sensitive else "MEDIUM", "ACL_WRITE_ACCESS", f"ACL entry may grant write access: {acl}"))
    if sensitive and not findings:
        findings.append(("INFO", "SENSITIVE_FILE", "Sensitive-name/type heuristic; permissions appear restrictive"))
    return findings

def scan(root, max_files=None, skip_dirs=None, include_hidden=True):
    root=Path(root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Path is not an accessible directory: {root}")
    skip=set(skip_dirs or [])
    records=[]; count=0; errors=[]
    def onerror(exc): errors.append(str(exc))
    for dirpath, dirs, files in os.walk(root, followlinks=False, onerror=onerror):
        dirs[:] = [d for d in dirs if d not in skip and (include_hidden or not d.startswith("."))]
        for name in files:
            if not include_hidden and name.startswith("."): continue
            path=Path(dirpath)/name
            count+=1
            if max_files and count>max_files: break
            try:
                st=path.stat(follow_symlinks=False)
                if not (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode)): continue
                acl=check_acl(path) if stat.S_ISREG(st.st_mode) else []
                findings=classify(path, st, acl)
                for severity, code, detail in findings:
                    records.append({"severity":severity,"code":code,"path":str(path),"type":"directory" if stat.S_ISDIR(st.st_mode) else "file","mode":oct(stat.S_IMODE(st.st_mode)),"mode_text":mode_str(st.st_mode),"owner_uid":st.st_uid,"owner_gid":st.st_gid,"size_bytes":st.st_size,"detail":detail})
            except (PermissionError,OSError) as e:
                errors.append(f"{path}: {e}")
        if max_files and count>max_files: break
    records.sort(key=lambda r:(SEVERITY.get(r["severity"],9),r["path"]))
    return records, count, errors

def main():
    p=argparse.ArgumentParser(description="Read-only SMB/NFS share permissions auditor")
    p.add_argument("paths", nargs="*", help="Mounted share directories to scan. If omitted, show detected SMB/NFS mounts.")
    p.add_argument("--format", choices=("text","json","csv"), default="text", help="Report format")
    p.add_argument("--output", help="Write report to file (default: stdout)")
    p.add_argument("--max-files", type=int, help="Limit inspected entries per scan (safety)")
    p.add_argument("--skip-dir", action="append", default=[], help="Directory name to skip (repeatable)")
    p.add_argument("--no-hidden", action="store_true", help="Skip hidden files and directories")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    args=p.parse_args()
    mounts=mount_info()
    if not args.paths:
        print("Detected network mounts:")
        if mounts:
            for m in mounts: print(f"  {m['fstype']:6} {m['source']} -> {m['mountpoint']} ({','.join(m['options'])})")
        else: print("  No SMB/NFS mounts detected (or mount table unavailable).")
        print("\nUsage: pass one or more mounted directories to scan.")
        return 0
    all_findings=[]; scan_stats=[]; errors=[]
    for root in args.paths:
        try:
            findings, inspected, errs=scan(root,args.max_files,args.skip_dir,not args.no_hidden)
            all_findings.extend(findings); errors.extend(errs)
            scan_stats.append({"path":str(Path(root).expanduser()),"inspected":inspected,"findings":len(findings)})
        except ValueError as e: errors.append(str(e))
    payload={"tool":"SMB/NFS Share Permission Auditor","version":VERSION,"generated_at":datetime.now(timezone.utc).isoformat(),"scans":scan_stats,"mounts":mounts,"findings":all_findings,"errors":errors}
    if args.format=="json": out=json.dumps(payload,indent=2)
    elif args.format=="csv":
        import io
        sio=io.StringIO(); fields=["severity","code","path","type","mode","mode_text","owner_uid","owner_gid","size_bytes","detail"]
        w=csv.DictWriter(sio,fieldnames=fields); w.writeheader(); w.writerows(all_findings); out=sio.getvalue()
    else:
        out_lines=[f"\nSMB/NFS SHARE PERMISSION AUDIT  |  {payload['generated_at']}","-"*78]
        for s in scan_stats: out_lines.append(f"SCAN {s['path']} | inspected={s['inspected']} | findings={s['findings']}")
        out_lines.append("")
        if not all_findings: out_lines.append("No permission findings detected (heuristic scan).")
        for f in all_findings:
            out_lines.append(f"[{f['severity']:<8}] {f['code']:<28} {f['mode']:<5} {f['path']}\n           {f['detail']}")
        if errors: out_lines.extend(["","Errors/warnings:"]+[f"  - {e}" for e in errors[:30]])
        out_lines.extend(["","Note: mounted-view permissions cannot fully reveal remote SMB share ACLs, Windows Everyone/Authenticated Users mappings, NFS server export policy, or server-side inheritance. Use native server-side auditing for authoritative results."])
        out="\n".join(out_lines)
    if args.output:
        Path(args.output).write_text(out+"\n",encoding="utf-8")
        print(f"Report saved: {args.output}")
    else: print(out)
    return 1 if any(f["severity"] in ("HIGH","CRITICAL") for f in all_findings) else 0

if __name__=="__main__":
    raise SystemExit(main())
