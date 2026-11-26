#!/usr/bin/env python3
"""Cross-platform hosts-file ad/malware blocklist updater (Python 3.9+, stdlib only)."""
import argparse, gzip, ipaddress, json, os, re, shutil, sys, tempfile, urllib.request
from datetime import datetime
from pathlib import Path

START = "# >>> LOCAL-DNS-SINKHOLE: BEGIN MANAGED BLOCK >>>"
END = "# <<< LOCAL-DNS-SINKHOLE: END MANAGED BLOCK <<<"
DEFAULT_FEEDS = [
    "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
    "https://raw.githubusercontent.com/AdAway/adaway.github.io/master/hosts.txt",
]
HOSTS = Path(r"C:\Windows\System32\drivers\etc\hosts") if os.name == "nt" else Path("/etc/hosts")
DOMAIN = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.I)


def valid_domain(domain):
    domain = domain.strip().lower().rstrip(".")
    if domain in {"localhost", "local", "localdomain", "broadcasthost"}:
        return False
    try:
        ipaddress.ip_address(domain)
        return False
    except ValueError:
        pass
    return bool(DOMAIN.fullmatch(domain))


def parse_feed(text):
    found = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "!", "[")) or line.startswith("@@"):
            continue
        if line.startswith("||"):
            line = line[2:].split("^", 1)[0].split("/", 1)[0]
        elif line.startswith("|"):
            line = line.lstrip("|").split("^", 1)[0].split("/", 1)[0]
        if "*" in line or "$" in line:
            continue
        fields = line.split()
        candidates = fields[1:] if len(fields) > 1 and fields[0] in {"0.0.0.0", "127.0.0.1", "::", "::1"} else fields[:1]
        for item in candidates:
            domain = item.lower().strip(".")
            if valid_domain(domain):
                found.add(domain)
    return found


def download(url, timeout, size_limit):
    req = urllib.request.Request(url, headers={"User-Agent": "LocalDNSBlockUpdater/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = response.read(size_limit + 1)
        if len(data) > size_limit:
            raise ValueError("feed size limit exceeded")
        if response.headers.get("Content-Encoding", "").lower() == "gzip" or url.endswith(".gz"):
            data = gzip.decompress(data)
            if len(data) > size_limit:
                raise ValueError("decompressed feed size limit exceeded")
    return parse_feed(data.decode("utf-8", errors="replace"))


def fetch_feeds(config, override=None):
    feeds = override if override else config.get("feeds", DEFAULT_FEEDS)
    domains = set()
    for url in feeds:
        try:
            items = download(url, int(config.get("timeout", 20)), int(config.get("max_bytes", 25000000)))
            if not items:
                print(f"[!] Empty/unsupported feed skipped: {url}")
                continue
            domains.update(items)
            print(f"[+] {len(items):,} domains: {url}")
        except Exception as exc:
            print(f"[!] Feed error ({url}): {exc}")
    if not domains:
        raise RuntimeError("All feeds failed or parsed empty; no files changed.")
    allowlist = {d.strip().lower().rstrip(".") for d in config.get("allowlist", []) if valid_domain(d)}
    return {d for d in domains if not any(d == a or d.endswith("." + a) for a in allowlist)}


def make_block(domains, config):
    ipv4 = config.get("block_ipv4", "0.0.0.0")
    ipv6 = config.get("block_ipv6", "::")
    ipaddress.ip_address(ipv4)
    if ipv6 not in ("disabled", "none", ""):
        ipaddress.ip_address(ipv6)
    rows = [START, "# Generated automatically. Configure feeds and allowlist instead of editing this block."]
    for domain in sorted(domains):
        rows.append(f"{ipv4} {domain}")
        if ipv6 not in ("disabled", "none", ""):
            rows.append(f"{ipv6} {domain}")
    rows.append(END)
    return "\n".join(rows) + "\n"


def merge_hosts(existing, block):
    start, end = existing.find(START), existing.find(END)
    if (start < 0) != (end < 0):
        raise RuntimeError("Unmatched managed-block marker; refusing to modify file.")
    if start >= 0:
        if end < start:
            raise RuntimeError("Managed-block markers reversed; refusing to modify file.")
        end += len(END)
        return existing[:start] + block.rstrip("\n") + existing[end:].lstrip("\n")
    return existing.rstrip("\n") + ("\n\n" if existing.strip() else "") + block


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, temp_name = tempfile.mkstemp(prefix="." + path.name + ".tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, mode)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def update(path, config, feeds=None, dry_run=False):
    domains = fetch_feeds(config, feeds)
    original = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    new_content = merge_hosts(original, make_block(domains, config))
    print(f"\nTotal blocked domains after allowlist: {len(domains):,}")
    if dry_run:
        print("[dry-run] No file written.")
        return
    if path.exists():
        backup = path.with_name(path.name + ".dns-sinkhole-backup-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
        shutil.copy2(path, backup)
        print("[+] Backup:", backup)
    atomic_write(path, new_content)
    print("[+] Hosts file updated:", path)


def status(path):
    if not path.exists():
        print("Hosts file missing:", path)
        return
    content = path.read_text(encoding="utf-8", errors="replace")
    start, end = content.find(START), content.find(END)
    if start < 0 or end < start:
        print("Managed block: not installed")
        return
    count = sum(1 for row in content[start:end].splitlines() if row.startswith(("0.0.0.0 ", ":: ")))
    print(f"Managed block detected; approx. entries: {count:,}\nHosts file: {path}")


def rollback(path):
    backups = sorted(path.parent.glob(path.name + ".dns-sinkhole-backup-*"))
    if not backups:
        raise RuntimeError("No backups found.")
    shutil.copy2(backups[-1], path)
    print("[+] Restored from:", backups[-1])


def main():
    parser = argparse.ArgumentParser(description="Update local hosts-file ad/malware blocking from threat-intelligence feeds.")
    parser.add_argument("--config", default=str(Path(__file__).with_name("feeds.example.json")), help="JSON config path")
    sub = parser.add_subparsers(dest="command", required=True)
    upd = sub.add_parser("update", help="Download feeds and replace the managed hosts section")
    upd.add_argument("--hosts", default=str(HOSTS), help="Hosts-file path")
    upd.add_argument("--feed", action="append", help="Override feed URLs (repeatable)")
    upd.add_argument("--dry-run", action="store_true", help="Download/parse only; do not write")
    st = sub.add_parser("status", help="Check managed-block status")
    st.add_argument("--hosts", default=str(HOSTS))
    rb = sub.add_parser("rollback", help="Restore newest hosts-file backup")
    rb.add_argument("--hosts", default=str(HOSTS)
    )
    args = parser.parse_args()
    try:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
        path = Path(args.hosts)
        if args.command == "update":
            update(path, config, args.feed, args.dry_run)
        elif args.command == "status":
            status(path)
        elif args.command == "rollback":
            rollback(path)
    except (OSError, json.JSONDecodeError, RuntimeError, ValueError) as exc:
        print("Error:", exc, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
