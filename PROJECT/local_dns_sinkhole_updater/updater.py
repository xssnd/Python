#!/usr/bin/env python3
"""Cross-platform hosts-file ad/malware blocklist updater (Python 3.9+, stdlib only)."""
import argparse, gzip, ipaddress, json, os, re, shutil, sys, tempfile, urllib.request
from datetime import datetime
from pathlib import Path

START="# >>> LOCAL-DNS-SINKHOLE: BEGIN MANAGED BLOCK >>>"
END="# <<< LOCAL-DNS-SINKHOLE: END MANAGED BLOCK <<<"
DEFAULT_FEEDS=[
 "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
 "https://raw.githubusercontent.com/AdAway/adaway.github.io/master/hosts.txt",
]
HOSTS=Path(r"C:\\Windows\\System32\\drivers\\etc\\hosts") if os.name=="nt" else Path("/etc/hosts")
DOMAIN=re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z]{2,63}$",re.I)

def valid_domain(d):
 d=d.strip().lower().rstrip(".")
 if d in {"localhost","local","localdomain","broadcasthost"}: return False
 try: ipaddress.ip_address(d); return False
 except ValueError: pass
 return bool(DOMAIN.fullmatch(d))

def parse_feed(text):
 out=set()
 for line in text.splitlines():
  s=line.strip()
  if not s or s.startswith(("#","!","[")) or s.startswith("@@"): continue
  if s.startswith("||"): s=s[2:].split("^",1)[0].split("/",1)[0]
  elif s.startswith("|"): s=s.lstrip("|").split("^",1)[0].split("/",1)[0]
  if "*" in s or "$" in s: continue
  fields=s.split()
  candidates=fields[1:] if len(fields)>1 and fields[0] in {"0.0.0.0","127.0.0.1","::","::1"} else fields[:1]
  for d in candidates:
   d=d.lower().strip(".")
   if valid_domain(d): out.add(d)
 return out

def download(url, timeout, limit):
 req=urllib.request.Request(url,headers={"User-Agent":"LocalDNSBlockUpdater/1.0"})
 with urllib.request.urlopen(req,timeout=timeout) as r:
  data=r.read(limit+1)
  if len(data)>limit: raise ValueError("feed size limit exceeded")
  if r.headers.get("Content-Encoding","").lower()=="gzip" or url.endswith(".gz"):
   data=gzip.decompress(data)
   if len(data)>limit: raise ValueError("decompressed feed size limit exceeded")
 return parse_feed(data.decode("utf-8",errors="replace"))

def fetch_feeds(cfg, override=None):
 feeds=override or cfg.get("feeds",DEFAULT_FEEDS)
 domains=set()
 for url in feeds:
  try:
   found=download(url,int(cfg.get("timeout",20)),int(cfg.get("max_bytes",25000000)))
   if not found: print(f"[!] Empty/unsupported feed skipped: {url}"); continue
   domains.update(found); print(f"[+] {len(found):,} domains: {url}")
  except Exception as e: print(f"[!] Feed error ({url}): {e}")
 if not domains: raise RuntimeError("All feeds failed or parsed empty; no files changed.")
 allow={d.strip().lower().rstrip(".") for d in cfg.get("allowlist",[]) if valid_domain(d)}
 return {d for d in domains if not any(d==a or d.endswith("."+a) for a in allow)}

def make_block(domains,cfg):
 ipv4=cfg.get("block_ipv4","0.0.0.0"); ipv6=cfg.get("block_ipv6","::")
 ipaddress.ip_address(ipv4)
 if ipv6 not in ("disabled","none",""): ipaddress.ip_address(ipv6)
 rows=[START,"# Generated automatically. Edit feeds/config, not this section."]
 for d in sorted(domains):
  rows.append(f"{ipv4} {d}")
  if ipv6 not in ("disabled","none",""): rows.append(f"{ipv6} {d}")
 rows.append(END)
 return "\\n".join(rows)+"\\n"

def merge_hosts(existing,block):
 a=existing.find(START); b=existing.find(END)
 if (a<0)!=(b<0): raise RuntimeError("Unmatched managed-block marker; aborting.")
 if a>=0:
  if b<a: raise RuntimeError("Managed-block markers reversed; aborting.")
  b+=len(END)
  return existing[:a]+block.rstrip("\\n")+existing[b:].lstrip("\\n")
 return existing.rstrip("\\n")+("\\n\\n" if existing.strip() else "")+block

def atomic_write(path,text):
 path.parent.mkdir(parents=True,exist_ok=True)
 mode=path.stat().st_mode & 0o777 if path.exists() else 0o644
 fd,tmp=tempfile.mkstemp(prefix="."+path.name+".tmp-",dir=path.parent)
 try:
  with os.fdopen(fd,"w",encoding="utf-8",newline="\\n") as f:
   f.write(text); f.flush(); os.fsync(f.fileno())
  os.chmod(tmp,mode); os.replace(tmp,path)
 finally:
  if os.path.exists(tmp): os.unlink(tmp)

def update(path,cfg,feeds=None,dry=False):
 domains=fetch_feeds(cfg,feeds)
 original=path.read_text(encoding="utf-8",errors="replace") if path.exists() else ""
 new=merge_hosts(original,make_block(domains,cfg))
 print(f"\\nTotal blocked domains after allowlist: {len(domains):,}")
 if dry: print("[dry-run] Nothing written."); return
 if path.exists():
  backup=path.with_name(path.name+".dns-sinkhole-backup-"+datetime.now().strftime("%Y%m%d-%H%M%S"))
  shutil.copy2(path,backup); print("[+] Backup:",backup)
 atomic_write(path,new)
 print("[+] Hosts updated:",path)

def status(path):
 if not path.exists(): print("Hosts file missing:",path); return
 s=path.read_text(encoding="utf-8",errors="replace")
 a,b=s.find(START),s.find(END)
 if a<0 or b<a: print("Managed block: not installed"); return
 count=sum(1 for ln in s[a:b].splitlines() if ln.startswith(("0.0.0.0 ",":: ")))
 print(f"Managed block detected; approx. entries: {count:,}\\nHosts file: {path}")

def rollback(path):
 backups=sorted(path.parent.glob(path.name+".dns-sinkhole-backup-*"))
 if not backups: raise RuntimeError("No backups found.")
 shutil.copy2(backups[-1],path); print("[+] Restored:",backups[-1])

def main():
 p=argparse.ArgumentParser(description="Update local hosts-file ad/malware domain blocking from threat feeds.")
 p.add_argument("--config",default=str(Path(__file__).with_name("feeds.example.json")))
 sub=p.add_subparsers(dest="cmd",required=True)
 u=sub.add_parser("update",help="Fetch feeds and update managed hosts section")
 u.add_argument("--hosts",default=str(HOSTS)); u.add_argument("--feed",action="append",help="Override configured feed URLs (repeatable)")
 u.add_argument("--dry-run",action="store_true")
 s=sub.add_parser("status",help="Check managed block status"); s.add_argument("--hosts",default=str(HOSTS))
 r=sub.add_parser("rollback",help="Restore newest hosts backup"); r.add_argument("--hosts",default=str(HOSTS))
 args=p.parse_args()
 try:
  cfg=json.loads(Path(args.config).read_text(encoding="utf-8"))
  target=Path(args.hosts)
  if args.cmd=="update": update(target,cfg,args.feed,args.dry_run)
  elif args.cmd=="status": status(target)
  elif args.cmd=="rollback": rollback(target)
 except (OSError,json.JSONDecodeError,RuntimeError,ValueError) as e:
  print("Error:",e,file=sys.stderr); return 1
 except KeyboardInterrupt: print("Interrupted."); return 130
 return 0
if __name__=="__main__": sys.exit(main())
