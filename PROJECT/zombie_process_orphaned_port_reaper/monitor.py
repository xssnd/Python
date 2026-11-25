#!/usr/bin/env python3
"""Idle I/O + resource threshold detector and guarded systemd service restarter."""
import argparse,json,os,signal,subprocess,sys,time
from pathlib import Path
import psutil
STOP=False
def halt(*a):
 global STOP
 STOP=True
def load(p):
 c=json.loads(Path(p).read_text());s=c.setdefault("settings",{})
 for k,v in dict(interval_seconds=30,idle_hours=2,cpu_percent_threshold=20,memory_mb_threshold=512,restart_cooldown_seconds=3600,max_restarts_per_day=1).items():s.setdefault(k,v)
 seen=set()
 for e in c.get("processes",[]):
  if not e.get("name") or e["name"] in seen or not e.get("match") or not e.get("systemd_service"):raise ValueError("Entries require unique name, match, systemd_service")
  seen.add(e["name"])
  if any(x in e["systemd_service"] for x in " ;|&$<>\n"):raise ValueError("Invalid systemd service name")
 return c
def matched(p,patterns):
 try:
  d=p.as_dict(attrs=["name","exe","cmdline"]);names=[str(d.get("name") or "").lower(),Path(str(d.get("exe") or "/")).name.lower()];cmd=" ".join(d.get("cmdline") or []).lower()
  return any(x.lower() in names or x.lower() in cmd for x in patterns)
 except psutil.Error:return False
def sockets(pid):
 try:return [str(c.laddr) for c in psutil.net_connections("inet") if c.pid==pid and c.status==psutil.CONN_LISTEN]
 except psutil.Error:return []
class Watch:
 def __init__(self,c):self.c=c;self.state={};self.history={}
 def scan(self):
  now=time.monotonic();out=[]
  for e in self.c.get("processes",[]):
   for p in psutil.process_iter():
    if not matched(p,e["match"]):continue
    try:
     if p.pid<=1 or p.pid==os.getpid() or p.status()==psutil.STATUS_ZOMBIE:continue
     cpu=p.cpu_percent();ram=p.memory_info().rss/1048576;io=p.io_counters();ctr=(io.read_bytes,io.write_bytes);k=(e["name"],p.pid);prev=self.state.get(k);since=now if prev is None or ctr!=prev[0] else prev[1];self.state[k]=(ctr,since);idle=(now-since)/3600;s=self.c["settings"]
     high=cpu>=s["cpu_percent_threshold"] or ram>=s["memory_mb_threshold"]
     out.append(dict(name=e["name"],pid=p.pid,cpu_percent=round(cpu,1),memory_mb=round(ram,1),idle_io_hours=round(idle,2),listeners=sockets(p.pid),candidate=bool(high and idle>=s["idle_hours"]),systemd_service=e["systemd_service"]))
    except (psutil.Error,OSError):pass
  return out
 def restart(self,r,apply=False):
  u=r["systemd_service"];now=time.time();h=self.history.setdefault(u,[]);h[:]=[t for t in h if now-t<86400];s=self.c["settings"]
  if s["max_restarts_per_day"]<=0 or len(h)>=s["max_restarts_per_day"]:return "daily-limit"
  if h and now-h[-1]<s["restart_cooldown_seconds"]:return "cooldown"
  if not apply:return "dry-run"
  if sys.platform!="linux":return "systemd-unavailable"
  try:
   x=subprocess.run(["systemctl","restart",u],capture_output=True,text=True,timeout=90)
   if x.returncode==0:h.append(now);return "restarted"
   return "failed: "+x.stderr.strip()
  except (OSError,subprocess.TimeoutExpired) as x:return "error: "+str(x)
def main():
 a=argparse.ArgumentParser(description=__doc__);a.add_argument("--config",default="config.json");a.add_argument("--watch",action="store_true");a.add_argument("--interval",type=int);a.add_argument("--json",action="store_true");a.add_argument("--export");a.add_argument("--format",choices=["json","csv"],default="json");a.add_argument("--restart",action="store_true");a.add_argument("--apply",action="store_true");a.add_argument("--yes",action="store_true");args=a.parse_args()
 if args.apply and not args.restart:a.error("--apply requires --restart")
 c=load(args.config);w=Watch(c);signal.signal(signal.SIGINT,halt);signal.signal(signal.SIGTERM,halt);delay=max(1,args.interval or c["settings"]["interval_seconds"])
 while not STOP:
  rows=w.scan();print(json.dumps(rows,indent=2) if args.json else [f'{r["name"]} pid={r["pid"]} CPU={r["cpu_percent"]}% RAM={r["memory_mb"]}MB I/O-idle={r["idle_io_hours"]}h ports={r["listeners"]} candidate={r["candidate"]}' for r in rows])
  if args.export:
   path=Path(args.export);path.parent.mkdir(parents=True,exist_ok=True)
   if args.format=="json":path.write_text(json.dumps(rows,indent=2)+"\n")
   else:
    import csv
    keys=["name","pid","cpu_percent","memory_mb","idle_io_hours","candidate","systemd_service"]
    with path.open("w",newline="") as f:x=csv.DictWriter(f,fieldnames=keys);x.writeheader();x.writerows({k:r.get(k) for k in keys} for r in rows)
  if args.restart:
   for r in rows:
    if r["candidate"]:
     if args.apply and not args.yes and input(f'Confirm restart {r["systemd_service"]}? [y/N] ').strip().lower() not in ("y","yes"):continue
     print(r["name"],"->",w.restart(r,args.apply))
  if not args.watch:break
  for _ in range(delay):
   if STOP:break
   time.sleep(1)
if __name__=="__main__":main()
