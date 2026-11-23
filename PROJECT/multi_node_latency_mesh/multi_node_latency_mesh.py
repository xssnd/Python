#!/usr/bin/env python3
"""
Multi-Node Latency & Packet Loss Mesh
Standard-library-only TCP/UDP probe agent and mesh controller for Linux/Windows.
"""
from __future__ import annotations
import argparse, concurrent.futures, csv, json, os, socket, statistics, sys, time
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.0.0"
DEFAULT_CONFIG = Path("nodes.json")
UDP_MAGIC = b"LATMESH/1 "

def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

def load_nodes(path):
    try:
        data=json.loads(Path(path).read_text(encoding="utf-8"))
        nodes=data.get("nodes", [])
        if not isinstance(nodes,list): raise ValueError("'nodes' must be an array")
        seen=set()
        for n in nodes:
            if not all(k in n for k in ("name","host")): raise ValueError("Each node needs name and host")
            if n["name"] in seen: raise ValueError(f"Duplicate node name: {n['name']}")
            seen.add(n["name"])
            n.setdefault("tcp_port", 22); n.setdefault("udp_port", 9999); n.setdefault("enabled", True)
        return nodes
    except FileNotFoundError:
        raise SystemExit(f"Config not found: {path}. Use 'init' to create one.")
    except (json.JSONDecodeError, ValueError) as e:
        raise SystemExit(f"Invalid config: {e}")

def save_nodes(path,nodes):
    Path(path).write_text(json.dumps({"nodes":nodes},indent=2)+"\n",encoding="utf-8")

def tcp_probe(host,port,timeout):
    start=time.perf_counter()
    try:
        with socket.create_connection((host,int(port)),timeout=timeout):
            return (time.perf_counter()-start)*1000, None
    except (OSError, ValueError) as e:
        return None, str(e)

def udp_probe(host,port,timeout):
    token=UDP_MAGIC+os.urandom(12).hex().encode()
    start=time.perf_counter()
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
            s.settimeout(timeout); s.sendto(token,(host,int(port)))
            data,_=s.recvfrom(4096)
            if data != token: return None,"Invalid UDP echo"
            return (time.perf_counter()-start)*1000,None
    except (OSError, ValueError) as e:
        return None,str(e)

def agent(host,udp_port,tcp_port):
    stop=False
    class UDPServer:
        def run(self):
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
                s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                s.bind((host,udp_port)); print(f"UDP echo listening on {host}:{udp_port}",flush=True)
                while True:
                    try:
                        data,addr=s.recvfrom(4096)
                        if data.startswith(UDP_MAGIC): s.sendto(data,addr)
                    except KeyboardInterrupt: break
    class TCPServer:
        def run(self):
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind((host,tcp_port)); s.listen(32)
                print(f"TCP accept listener on {host}:{tcp_port}",flush=True)
                while True:
                    try:
                        conn,addr=s.accept()
                        conn.close()
                    except KeyboardInterrupt: break
    import threading
    threads=[threading.Thread(target=UDPServer().run,daemon=True),threading.Thread(target=TCPServer().run,daemon=True)]
    for t in threads:t.start()
    print("Agent running. Ctrl-C to stop.",flush=True)
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: print("\nAgent stopped.")

def probe_node(n,protocol,tries,timeout):
    samples=[]; errors=0
    for _ in range(tries):
        if protocol in ("tcp","both"):
            ms,err=tcp_probe(n["host"],n["tcp_port"],timeout)
            if ms is not None:samples.append(ms)
            else:errors+=1
        if protocol in ("udp","both"):
            ms,err=udp_probe(n["host"],n["udp_port"],timeout)
            if ms is not None:samples.append(ms)
            else:errors+=1
    total=tries*(2 if protocol=="both" else 1)
    return {"name":n["name"],"host":n["host"],"protocol":protocol,"sent":total,
            "received":len(samples),"loss_pct":round(100*errors/total,1),
            "avg_ms":round(statistics.mean(samples),2) if samples else None,
            "min_ms":round(min(samples),2) if samples else None,
            "max_ms":round(max(samples),2) if samples else None,
            "jitter_ms":round(statistics.pstdev(samples),2) if len(samples)>1 else 0.0,
            "status":"ONLINE" if samples else "OFFLINE","error":None if samples else "No successful probes"}

def run_mesh(nodes,protocol,tries,timeout,workers):
    enabled=[n for n in nodes if n.get("enabled",True)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(probe_node,n,protocol,tries,timeout) for n in enabled]
        results=[f.result() for f in futures]
    return results

def render(results):
    print(f"\nMESH STATUS  {now_iso()}   Nodes: {len(results)}")
    print("-"*98)
    print(f"{'NODE':24} {'HOST':28} {'STATE':9} {'LOSS':8} {'AVG ms':9} {'MIN':8} {'MAX':8} {'JITTER':8}")
    print("-"*98)
    for r in results:
        def fmt(v):return "-" if v is None else f"{v:.2f}"
        print(f"{r['name'][:24]:24} {r['host'][:28]:28} {r['status']:9} {r['loss_pct']:>5.1f}%   {fmt(r['avg_ms']):9} {fmt(r['min_ms']):8} {fmt(r['max_ms']):8} {fmt(r['jitter_ms']):8}")
    online=sum(x["status"]=="ONLINE" for x in results)
    print("-"*98); print(f"ONLINE: {online}  OFFLINE: {len(results)-online}")

def export_results(results,fmt,outfile):
    if not outfile: return
    p=Path(outfile); p.parent.mkdir(parents=True,exist_ok=True)
    if fmt=="json": p.write_text(json.dumps({"timestamp":now_iso(),"results":results},indent=2)+"\n",encoding="utf-8")
    else:
        fields=list(results[0].keys()) if results else ["timestamp","name","host","protocol","sent","received","loss_pct","avg_ms","min_ms","max_ms","jitter_ms","status","error"]
        with p.open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(results)
    print(f"Saved {fmt.upper()} report: {p}")

def main():
    p=argparse.ArgumentParser(description="TCP/UDP mesh latency and packet-loss monitor")
    sub=p.add_subparsers(dest="cmd",required=True)
    i=sub.add_parser("init",help="Create sample nodes.json"); i.add_argument("--config",default=str(DEFAULT_CONFIG))
    a=sub.add_parser("agent",help="Run UDP echo/TCP listener agent"); a.add_argument("--bind",default="0.0.0.0"); a.add_argument("--udp-port",type=int,default=9999); a.add_argument("--tcp-port",type=int,default=2222)
    m=sub.add_parser("mesh",help="Probe all configured nodes"); m.add_argument("--config",default=str(DEFAULT_CONFIG)); m.add_argument("--protocol",choices=["tcp","udp","both"],default="both"); m.add_argument("--tries",type=int,default=5); m.add_argument("--timeout",type=float,default=1.5); m.add_argument("--workers",type=int,default=20); m.add_argument("--format",choices=["csv","json"],default="csv"); m.add_argument("--output",default="reports/mesh_latest.csv")
    ls=sub.add_parser("list",help="List configured nodes"); ls.add_argument("--config",default=str(DEFAULT_CONFIG))
    add=sub.add_parser("add",help="Add/update node"); add.add_argument("name"); add.add_argument("host"); add.add_argument("--tcp-port",type=int,default=2222); add.add_argument("--udp-port",type=int,default=9999); add.add_argument("--config",default=str(DEFAULT_CONFIG))
    rm=sub.add_parser("remove",help="Remove node by name"); rm.add_argument("name"); rm.add_argument("--config",default=str(DEFAULT_CONFIG))
    en=sub.add_parser("enable",help="Enable node"); en.add_argument("name"); en.add_argument("--config",default=str(DEFAULT_CONFIG))
    dis=sub.add_parser("disable",help="Disable node"); dis.add_argument("name"); dis.add_argument("--config",default=str(DEFAULT_CONFIG)
)
    args=p.parse_args()
    if args.cmd=="init":
        path=Path(args.config)
        if path.exists(): raise SystemExit(f"Refusing to overwrite {path}")
        save_nodes(path,[{"name":"server-a","host":"192.0.2.10","tcp_port":2222,"udp_port":9999,"enabled":True},{"name":"server-b","host":"192.0.2.11","tcp_port":2222,"udp_port":9999,"enabled":True}])
        print(f"Created {path}. Edit hosts/ports to match your environment."); return
    if args.cmd=="agent": agent(args.bind,args.udp_port,args.tcp_port); return
    nodes=load_nodes(args.config)
    if args.cmd=="list":
        for n in nodes: print(f"{'[enabled]' if n['enabled'] else '[disabled]'} {n['name']:20} {n['host']} TCP:{n['tcp_port']} UDP:{n['udp_port']}")
        return
    if args.cmd in ("add","remove","enable","disable"):
        if args.cmd=="add":
            if any(n["name"]==args.name for n in nodes): raise SystemExit("Node name already exists; use a unique name.")
            nodes.append({"name":args.name,"host":args.host,"tcp_port":args.tcp_port,"udp_port":args.udp_port,"enabled":True})
        elif args.cmd=="remove":
            new=[n for n in nodes if n["name"]!=args.name]
            if len(new)==len(nodes): raise SystemExit("Node not found.")
            nodes=new
        else:
            found=False
            for n in nodes:
                if n["name"]==args.name: n["enabled"]=args.cmd=="enable"; found=True
            if not found: raise SystemExit("Node not found.")
        save_nodes(args.config,nodes); print("Node inventory updated."); return
    if args.tries<1 or args.timeout<=0 or args.workers<1: raise SystemExit("tries/workers must be >=1 and timeout > 0")
    results=run_mesh(nodes,args.protocol,args.tries,args.timeout,args.workers)
    render(results); export_results(results,args.format,args.output)

if __name__=="__main__": main()
