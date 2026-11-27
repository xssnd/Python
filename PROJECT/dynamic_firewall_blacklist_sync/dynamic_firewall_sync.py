#!/usr/bin/env python3
"""Defensive log-driven dynamic firewall blacklist synchronizer."""
import argparse, collections, ipaddress, json, os, re, shlex, subprocess, sys, time
from pathlib import Path
VERSION="1.0.0"
IP_RE=[r"(?P<ip>[0-9]{1,3}(?:[.][0-9]{1,3}){3})"]
SIGS=[r" 401 ",r" 403 ",r" 404 ",r" 429 ",r" 444 ",r"failed password",r"invalid user",r"authentication failure",r"login failed",r"wp-login",r"xmlrpc.php"]
class FirewallError(RuntimeError): pass

def load_config(path):
    if not path:return {}
    try:return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as e:raise FirewallError(f"Config error: {e}")
def extract_ips(line,patterns):
    found=set()
    for pat in patterns:
        try: matches=re.finditer(pat,line,re.I)
        except re.error as e:raise FirewallError(f"Bad IP regex: {e}")
        for m in matches:
            raw=m.groupdict().get("ip") or (m.group(1) if m.groups() else m.group(0))
            try:found.add(str(ipaddress.ip_address(raw.strip("[]"))))
            except ValueError:pass
    return found
def suspicious(line,patterns):return any(re.search(p,line,re.I) for p in patterns)
def eligible(ip,allowlist,include_private=False):
    a=ipaddress.ip_address(ip)
    if a.is_loopback or a.is_multicast or a.is_unspecified or a.is_reserved:return False
    if a.is_private and not include_private:return False
    return not any(a in ipaddress.ip_network(n,strict=False) for n in allowlist)
def scan(lines,regexes,patterns,allowlist,include_private,threshold,window):
    now=time.time(); counts=collections.defaultdict(collections.deque)
    for line in lines:
        if not suspicious(line,patterns):continue
        for ip in extract_ips(line,regexes):
            if not eligible(ip,allowlist,include_private):continue
            q=counts[ip];q.append(now)
            while q and now-q[0]>window:q.popleft()
    return sorted(ip for ip,q in counts.items() if len(q)>=threshold)
def cmd(argv,dry):
    if dry:print("DRY-RUN:",shlex.join(argv));return
    p=subprocess.run(argv,text=True,capture_output=True)
    if p.returncode:raise FirewallError(f"{shlex.join(argv)} failed: {p.stderr.strip()}")
def nft(ip,action,dry,timeout,setname):
    family=["inet","filter"]
    if not dry:
        exists=subprocess.run(["nft","list","set",*family,setname],capture_output=True)
        if exists.returncode:cmd(["nft","add","set",*family,setname,"{","type","ipv4_addr",";","flags","timeout",";","timeout",timeout,";","}"],False)
    args=["nft","add" if action=="block" else "delete","element",*family,setname,"{",ip]
    if action=="block":args+=["timeout",timeout]
    args+=["}"];cmd(args,dry)
def iptables(ip,action,dry,chain):
    if not dry:
        p=subprocess.run(["iptables","-S",chain],capture_output=True)
        if p.returncode:cmd(["iptables","-N",chain],False);cmd(["iptables","-I","INPUT","1","-j",chain],False)
    if action=="block":
        exists=0 if dry else subprocess.run(["iptables","-C",chain,"-s",ip,"-j","DROP"],capture_output=True).returncode
        if dry or exists:cmd(["iptables","-I",chain,"1","-s",ip,"-j","DROP"],dry)
    else:cmd(["iptables","-D",chain,"-s",ip,"-j","DROP"],dry)
def windows(ip,action,dry,prefix):
    name=f"{prefix}-{ip}"
    ps=(f"if (-not (Get-NetFirewallRule -DisplayName '{name}' -ErrorAction SilentlyContinue)) "
        f"{{ New-NetFirewallRule -DisplayName '{name}' -Direction Inbound -Action Block -RemoteAddress '{ip}' -Profile Any }}") if action=="block" else f"Remove-NetFirewallRule -DisplayName '{name}' -ErrorAction SilentlyContinue"
    cmd(["powershell","-NoProfile","-NonInteractive","-Command",ps],dry)
def dispatch(ip,b,a,d,t,c):
    if b=="nftables":nft(ip,a,d,t,c.get("nft_set","dynamic_blacklist"))
    elif b=="iptables":iptables(ip,a,d,c.get("iptables_chain","DYNAMIC_BLACKLIST"))
    elif b=="windows":windows(ip,a,d,c.get("windows_rule_prefix","DynamicBlacklist"))
    else:raise FirewallError("Unknown backend")
def main():
    p=argparse.ArgumentParser(description="Log-driven IP blacklist sync; preview by default.")
    p.add_argument("--config",type=Path);p.add_argument("--log",action="append")
    p.add_argument("--backend",choices=["auto","nftables","iptables","windows"],default="auto")
    p.add_argument("--threshold",type=int);p.add_argument("--window",type=int);p.add_argument("--block-time")
    p.add_argument("--allow",action="append",default=[]);p.add_argument("--include-private",action="store_true")
    p.add_argument("--apply",action="store_true");p.add_argument("--watch",action="store_true")
    p.add_argument("--poll",type=float,default=2);p.add_argument("--unblock",action="append",metavar="IP")
    p.add_argument("--status",action="store_true");p.add_argument("--version",action="version",version=f"%(prog)s {VERSION}")
    a=p.parse_args();c=load_config(a.config);logs=a.log or c.get("log_files",[])
    if not logs and not a.unblock:p.error("Set --log or log_files in config")
    regexes=c.get("ip_regex",IP_RE);patterns=c.get("suspicious_patterns",SIGS)
    allow=c.get("allowlist",[])+(a.allow or []);th=a.threshold or c.get("threshold",8);win=a.window or c.get("window_seconds",300)
    timeout=a.block_time or c.get("block_time","1h")
    if th<1 or win<1 or a.poll<=0:p.error("threshold/window/poll must be positive")
    if not re.fullmatch(r"[0-9]+[smhd]",timeout):p.error("block-time: examples 30s, 15m, 2h, 1d")
    backend=a.backend if a.backend!="auto" else ("windows" if os.name=="nt" else "nftables");dry=not a.apply
    if a.unblock:ips=[str(ipaddress.ip_address(x)) for x in a.unblock];action="unblock"
    else:
        action="block"
        if a.watch:
            offsets={x:0 for x in logs};pending=collections.defaultdict(collections.deque)
            print(f"Watching {len(logs)} log(s), threshold={th}, window={win}s. Ctrl-C to stop.")
            try:
                while True:
                    for path in logs:
                        try:
                            with open(path,"r",errors="replace") as f:f.seek(offsets[path]);lines=f.readlines();offsets[path]=f.tell()
                            for line in lines:
                                if suspicious(line,patterns):
                                    for ip in extract_ips(line,regexes):
                                        if eligible(ip,allow,a.include_private):pending[ip].append(time.time())
                        except OSError as e:print(f"WARN {path}: {e}",file=sys.stderr)
                    now=time.time()
                    for ip,q in list(pending.items()):
                        while q and now-q[0]>win:q.popleft()
                    for ip,q in list(pending.items()):
                        if len(q)>=th:dispatch(ip,backend,action,dry,timeout,c);pending.pop(ip,None)
                    time.sleep(a.poll)
            except KeyboardInterrupt:print("Watcher stopped.");return
        lines=[]
        for path in logs:
            try:lines+=Path(path).read_text(errors="replace").splitlines()
            except OSError as e:print(f"WARN {path}: {e}",file=sys.stderr)
        ips=scan(lines,regexes,patterns,allow,a.include_private,th,win)
    if a.status:print("Candidates:",", ".join(ips) if ips else "none")
    else:
        print(f"{action.title()} {len(ips)} IP(s) via {backend} ({'DRY-RUN' if dry else 'APPLY'})")
        for ip in ips:dispatch(ip,backend,action,dry,timeout,c)
if __name__=="__main__":
    try:main()
    except FirewallError as e:print(f"ERROR: {e}",file=sys.stderr);sys.exit(2)
