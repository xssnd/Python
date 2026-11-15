#!/usr/bin/env python3
"""Record local host uptime and remote availability checks to CSV."""
from __future__ import annotations
import argparse, csv, json, logging, os, signal, socket, sys, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import psutil
from notifiers import build_notifiers

LOG=logging.getLogger("uptime_logger")
FIELDS=["timestamp_utc","target","check_type","status","response_time_ms","http_status","error","host_uptime_seconds"]

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def check_local_host(boot_time_fn=psutil.boot_time, now_fn=time.time):
    return {"target":"localhost","check_type":"host","status":"UP","response_time_ms":"","http_status":"","error":"",
            "host_uptime_seconds":max(0,int(now_fn()-boot_time_fn()))}

def check_tcp(target, timeout):
    started=time.perf_counter()
    try:
        with socket.create_connection((str(target["host"]),int(target["port"])),timeout=timeout): pass
        return {"status":"UP","response_time_ms":round((time.perf_counter()-started)*1000,2),"http_status":"","error":""}
    except OSError as exc:
        return {"status":"DOWN","response_time_ms":round((time.perf_counter()-started)*1000,2),"http_status":"","error":str(exc)}

def check_http(target, timeout):
    started=time.perf_counter(); expected=int(target.get("expected_status",200))
    try:
        with urlopen(Request(str(target["url"]),headers={"User-Agent":"UptimeLogger/1.0"}),timeout=timeout) as response: code=response.status
        error="" if code==expected else f"Expected HTTP {expected}, received {code}"
    except HTTPError as exc:
        code=exc.code; error="" if code==expected else f"HTTP {code}: {exc.reason}"
    except (URLError,TimeoutError,OSError,ValueError) as exc:
        return {"status":"DOWN","response_time_ms":round((time.perf_counter()-started)*1000,2),"http_status":"","error":str(exc)}
    return {"status":"UP" if code==expected else "DOWN","response_time_ms":round((time.perf_counter()-started)*1000,2),"http_status":code,"error":error}

def check_target(target,timeout):
    kind=str(target.get("type","")).lower()
    if kind=="tcp": result=check_tcp(target,timeout)
    elif kind=="http": result=check_http(target,timeout)
    else: raise ValueError(f"Unsupported check type for {target.get('name','unnamed')}: {kind}")
    return {"target":str(target["name"]),"check_type":kind,**result,"host_uptime_seconds":""}

def append_csv(path,rows):
    path=Path(path).expanduser(); path.parent.mkdir(parents=True,exist_ok=True)
    header=not path.exists() or path.stat().st_size==0
    with path.open("a",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=FIELDS,extrasaction="ignore")
        if header: writer.writeheader()
        writer.writerows(rows)

def summarize_csv(path):
    totals={}
    with Path(path).expanduser().open(newline="",encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name=row.get("target","")
            if name:
                bucket=totals.setdefault(name,[0,0]); bucket[1]+=1
                if row.get("status")=="UP": bucket[0]+=1
    return [{"target":name,"samples":v[1],"up":v[0],"down":v[1]-v[0],
             "availability_percent":round(v[0]/v[1]*100,3) if v[1] else 0.0} for name,v in sorted(totals.items())]

class StateTracker:
    def __init__(self,notifiers=None,cooldown_seconds=3600,recovery_alerts=True):
        self.notifiers=list(notifiers or []); self.cooldown=max(0,int(cooldown_seconds))
        self.recovery_alerts=recovery_alerts; self.previous={}; self.last_alert={}
    def process(self,row,now=None):
        name,status=row["target"],row["status"]; now=time.time() if now is None else now
        previous=self.previous.get(name); self.previous[name]=status; message=None
        if status=="DOWN" and (previous!="DOWN" or now-self.last_alert.get(name,0)>=self.cooldown):
            message=f"DOWN: {name} is unreachable. {row.get('error','')}".strip(); self.last_alert[name]=now
        elif status=="UP" and previous=="DOWN" and self.recovery_alerts: message=f"RECOVERY: {name} is reachable again."
        if message:
            for notifier in self.notifiers:
                try: notifier.send(message)
                except Exception: LOG.exception("Notification delivery failed via %s",type(notifier).__name__)

def load_config(path):
    config={"interval_seconds":60,"timeout_seconds":5,"csv_file":"data/uptime.csv","include_local_host":True,
            "cooldown_seconds":3600,"recovery_alerts":True,"targets":[],"notifications":{"telegram":{},"discord":{},"email":{}}}
    if path:
        with open(path,encoding="utf-8") as handle: config.update(json.load(handle))
    env={"telegram":{"bot_token":"UL_TELEGRAM_BOT_TOKEN","chat_id":"UL_TELEGRAM_CHAT_ID"},
         "discord":{"webhook_url":"UL_DISCORD_WEBHOOK_URL"},
         "email":{"smtp_host":"UL_SMTP_HOST","smtp_port":"UL_SMTP_PORT","username":"UL_SMTP_USERNAME",
                  "password":"UL_SMTP_PASSWORD","sender":"UL_EMAIL_FROM","recipient":"UL_EMAIL_TO"}}
    for channel,fields in env.items():
        dest=config.setdefault("notifications",{}).setdefault(channel,{})
        for key,var in fields.items():
            if os.getenv(var): dest[key]=os.environ[var]
    return config

def validate_config(config):
    if int(config.get("interval_seconds",60))<1: raise ValueError("interval_seconds must be at least 1")
    if float(config.get("timeout_seconds",5))<=0: raise ValueError("timeout_seconds must be greater than 0")
    names=set()
    for t in config.get("targets",[]):
        name=str(t.get("name","")).strip(); kind=str(t.get("type","")).lower()
        if not name or name=="localhost": raise ValueError("Remote targets need a name other than localhost")
        if name in names: raise ValueError(f"Duplicate target name: {name}")
        names.add(name)
        if kind=="tcp" and (not t.get("host") or not 1<=int(t.get("port",0))<=65535): raise ValueError(f"TCP target {name} needs a host and valid port")
        if kind=="http" and not str(t.get("url","")).startswith(("http://","https://")): raise ValueError(f"HTTP target {name} needs an HTTP(S) URL")
        if kind not in {"tcp","http"}: raise ValueError(f"Unsupported check type for {name}: {kind}")

def collect(config):
    timestamp=utc_now(); rows=[]
    if config.get("include_local_host",True): rows.append({"timestamp_utc":timestamp,**check_local_host()})
    for target in config.get("targets",[]):
        try: row=check_target(target,float(config.get("timeout_seconds",5)))
        except Exception as exc:
            LOG.exception("Check failed for target %s",target.get("name","unknown"))
            row={"target":target.get("name","unknown"),"check_type":target.get("type",""),"status":"DOWN",
                 "response_time_ms":"","http_status":"","error":str(exc),"host_uptime_seconds":""}
        rows.append({"timestamp_utc":timestamp,**row})
    return rows

def configure_logging(log_file=None):
    handlers=[logging.StreamHandler()]
    if log_file:
        path=Path(log_file).expanduser(); path.parent.mkdir(parents=True,exist_ok=True)
        handlers.append(logging.FileHandler(path,encoding="utf-8"))
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s",handlers=handlers,force=True)

def run(config,once=False,json_output=False):
    validate_config(config); interval=int(config.get("interval_seconds",60))
    tracker=StateTracker(build_notifiers(config.get("notifications",{})),config.get("cooldown_seconds",3600),config.get("recovery_alerts",True))
    stop=False
    def request_stop(_signum,_frame):
        nonlocal stop; stop=True
    for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,request_stop)
    while not stop:
        rows=collect(config); append_csv(config.get("csv_file","data/uptime.csv"),rows)
        for row in rows:
            tracker.process(row)
            if json_output: print(json.dumps(row))
            else:
                suffix=f" ({row['response_time_ms']} ms)" if row["response_time_ms"]!="" else ""
                LOG.info("%-24s %-4s%s",row["target"],row["status"],suffix)
        if once: break
        deadline=time.monotonic()+interval
        while not stop and time.monotonic()<deadline: time.sleep(min(1,max(0,deadline-time.monotonic())))
    return 0

def main(argv=None):
    parser=argparse.ArgumentParser(description="Record local and remote server uptime to CSV.")
    parser.add_argument("-c","--config",default="config.json"); parser.add_argument("--once",action="store_true")
    parser.add_argument("--json",action="store_true"); parser.add_argument("--summary",action="store_true")
    parser.add_argument("--version",action="version",version="Uptime Logger 1.0.0")
    args=parser.parse_args(argv); config=load_config(args.config if Path(args.config).is_file() else None); configure_logging()
    try:
        if args.summary:
            for item in summarize_csv(config.get("csv_file","data/uptime.csv")):
                print(f"{item['target']}: {item['availability_percent']:.3f}% ({item['up']} UP / {item['down']} DOWN; {item['samples']} samples)")
            return 0
        return run(config,args.once,args.json)
    except (ValueError,OSError,json.JSONDecodeError) as exc:
        LOG.error("%s",exc); return 2

if __name__=="__main__": sys.exit(main())
