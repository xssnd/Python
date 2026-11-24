#!/usr/bin/env python3
"""Smart Log Anomaly Grepper — lightweight log anomaly detection without an ELK stack."""
from __future__ import annotations
import argparse, collections, csv, json, math, os, platform, re, subprocess, sys, time
from pathlib import Path
from datetime import datetime, timezone

TOKEN_RE = re.compile(r"[A-Za-z0-9_./:@+-]{2,}")
DEFAULT_CONFIG = {"threshold":5.0,"min_line_length":12,"ignore_patterns":[],"allow_patterns":[],"max_line_length":20000,"windows_channels":["System","Application"],"windows_event_level":3,"windows_max_events":500}

def load_config(path):
    if not path: return DEFAULT_CONFIG.copy()
    try:
        data=json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data,dict): raise ValueError("config must be a JSON object")
        cfg=DEFAULT_CONFIG.copy(); cfg.update(data); return cfg
    except (OSError,json.JSONDecodeError,ValueError) as e: raise SystemExit(f"Config error: {e}")

def tokens(line): return [t.lower() for t in TOKEN_RE.findall(line) if len(t)>1]
def entropy(line):
    if not line: return 0.0
    counts=collections.Counter(line); n=len(line)
    return -sum((c/n)*math.log2(c/n) for c in counts.values())

def template(line):
    s=re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b","<IP>",line)
    s=re.sub(r"\b[0-9a-fA-F]{8,}\b","<HEX>",s)
    s=re.sub(r"\b\d+\b","<N>",s)
    return re.sub(r"\s+"," ",s.strip()).lower()

def train(lines,source=""):
    tc=collections.Counter(); temps=collections.Counter(); lengths=[]
    for line in lines:
        tc.update(tokens(line)); temps[template(line)]+=1; lengths.append(len(line))
    return {"version":1,"created_utc":datetime.now(timezone.utc).isoformat(),"source":source,"lines":len(lengths),"token_counts":dict(tc),"templates":dict(temps),"avg_line_length":sum(lengths)/len(lengths) if lengths else 0}

def score_line(line,model,cfg):
    ts=tokens(line); counts=model.get("token_counts",{}); total=sum(counts.values()) or 1; vocab=len(counts) or 1
    rarity=sum(-math.log2((counts.get(t,0)+1)/(total+vocab)) for t in ts)/max(len(ts),1)
    known=model.get("templates",{}); unseen=template(line) not in known
    score=rarity+(3.0 if unseen else 0.0)+min(entropy(line)/6.0,2.0)+(1.0 if len(line)>cfg.get("max_line_length",20000) else 0.0)
    reasons=[]
    if unseen: reasons.append("new-template")
    rare=[t for t in ts if counts.get(t,0)<=1]
    if rare: reasons.append("rare-token:"+",".join(rare[:4]))
    if entropy(line)>=4.5: reasons.append("high-entropy")
    if len(line)>cfg.get("max_line_length",20000): reasons.append("oversized-line")
    return score,reasons

def skip_line(line,cfg):
    return any(re.search(p,line) for p in cfg.get("allow_patterns",[])+cfg.get("ignore_patterns",[]))

def emit(rows,fmt):
    if fmt=="json":
        for r in rows: print(json.dumps(r,ensure_ascii=False))
    elif fmt=="csv":
        w=csv.DictWriter(sys.stdout,fieldnames=["timestamp","source","score","reasons","line"]); w.writeheader()
        for r in rows: w.writerow({**r,"reasons":";".join(r["reasons"])})
    else:
        for r in rows:
            print(f"\033[31m[ANOMALY {r['score"]:.2f}]\033[0m {r['source']} | {r['line']}")
            if r["reasons"]: print("  reasons: "+", ".join(r["reasons"]))

def read_file(path):
    if path=="-":
        for l in sys.stdin: yield l.rstrip("\n")
    else:
        with open(path,encoding="utf-8",errors="replace") as f:
            for l in f: yield l.rstrip("\n")

def windows_events(channels,level,limit):
    if platform.system()!="Windows": raise RuntimeError("Windows Event Log is available on Windows only.")
    for ch in channels:
        ps=f"Get-WinEvent -FilterHashtable @{{LogName='{ch}'; Level={level}} -MaxEvents {limit} -ErrorAction SilentlyContinue | Select-Object TimeCreated,Id,ProviderName,LevelDisplayName,Message | ConvertTo-Json -Depth 3"
        p=subprocess.run(["powershell","-NoProfile","-Command",ps],capture_output=True,text=True,timeout=60)
        if p.returncode: continue
        try: events=json.loads(p.stdout or "[]")
        except json.JSONDecodeError: continue
        if isinstance(events,dict): events=[events]
        for e in events: yield f"{e.get('TimeCreated')} [{ch}] EventID={e.get('Id')} Provider={e.get('ProviderName')} Level={e.get('LevelDisplayName')} {e.get('Message','')}"

def process(lines,source,cfg,args):
    model={}
    if args.model:
        try: model=json.loads(Path(args.model).read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError) as e: raise SystemExit(f"Cannot load baseline model: {e}")
    rows=[]
    for line in lines:
        if not line.strip() or len(line)<cfg.get("min_line_length",12) or skip_line(line,cfg): continue
        score,reasons=score_line(line,model,cfg)
        if score>=cfg.get("threshold",5.0) and score>=args.min_score:
            rows.append({"timestamp":datetime.now(timezone.utc).isoformat(),"source":source,"score":round(score,3),"reasons":reasons,"line":line})
    emit(rows,args.format)

def main():
    ap=argparse.ArgumentParser(description="Entropy + token rarity anomaly grepper for Linux logs and Windows Event Logs")
    ap.add_argument("files",nargs="*",help="Log paths or '-' for stdin")
    ap.add_argument("--config"); ap.add_argument("--model")
    ap.add_argument("--train",action="store_true",help="Train baseline from input")
    ap.add_argument("--save-model",default="log_baseline.json")
    ap.add_argument("--threshold",type=float); ap.add_argument("--format",choices=["text","json","csv"],default="text")
    ap.add_argument("--follow",action="store_true",help="Tail one file continuously")
    ap.add_argument("--windows-eventlog",action="store_true",help="Scan recent Windows Event Log")
    ap.add_argument("--channels",nargs="+"); ap.add_argument("--event-level",type=int); ap.add_argument("--max-events",type=int)
    ap.add_argument("--min-score",type=float,default=0.0)
    args=ap.parse_args(); cfg=load_config(args.config)
    if args.threshold is not None: cfg["threshold"]=args.threshold
    if args.event_level is not None: cfg["windows_event_level"]=args.event_level
    if args.max_events is not None: cfg["windows_max_events"]=args.max_events
    if args.windows_eventlog:
        lines=list(windows_events(args.channels or cfg["windows_channels"],cfg["windows_event_level"],cfg["windows_max_events"])); src="Windows Event Log"
    else:
        if not args.files: ap.error("Specify file(s), '-' for stdin, or --windows-eventlog.")
        if args.follow and (len(args.files)!=1 or args.files[0]=="-"): ap.error("--follow requires exactly one file path.")
        lines=[]
        for f in args.files: lines.extend(read_file(f))
        src=",".join(args.files)
        if args.follow:
            path=args.files[0]
            with open(path,encoding="utf-8",errors="replace") as fh:
                fh.seek(0,os.SEEK_END); print(f"Following {path}; Ctrl-C to stop.",file=sys.stderr)
                while True:
                    line=fh.readline()
                    if not line: time.sleep(.25); continue
                    process([line.rstrip("\n")],path,cfg,args)
    if args.train:
        m=train(lines,src); Path(args.save_model).write_text(json.dumps(m,indent=2),encoding="utf-8")
        print(f"Baseline saved: {args.save_model} | lines={m['lines']} | tokens={len(m['token_counts'])} | templates={len(m['templates'])}")
    elif not args.follow: process(lines,src,cfg,args)

if __name__=="__main__":
    try: main()
    except KeyboardInterrupt: print("\nStopped.",file=sys.stderr)
    except (OSError,RuntimeError,subprocess.TimeoutExpired) as e: print(f"Error: {e}",file=sys.stderr); sys.exit(2)
