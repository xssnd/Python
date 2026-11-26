# Local DNS Sinkhole & Ad/Malware Blocklist Updater

Cross-platform Python utility that periodically downloads threat/ad domain feeds and updates a dedicated, clearly marked block section in the system hosts file. This hosts-based approach requires no third-party libraries or always-running DNS daemon.

## Features
- Linux, macOS, and Windows hosts-file support (admin/root privileges needed to write system file).
- Aggregates multiple feeds; supports common hosts-file rows, plain domain lists, and basic `||domain^` adblock syntax.
- Domain allowlist exempts a domain and its subdomains.
- IPv4/IPv6 blocking addresses configurable (IPv6 can be disabled).
- Feed timeouts, download size caps, malformed/empty feed protection; will not write when every feed fails.
- Managed section markers preserve all other hosts-file entries.
- Atomic replacement, timestamped backup, dry-run preview, status, rollback.
- CLI interface and JSON config; Python standard library only.

> Feed sources may cause false positives. Review sources and allowlist before deploying. This tool edits hosts-file entries; it does **not** install a DNS server or configure router/client DNS. For a full DNS filtering service, use Pi-hole, AdGuard Home, or Unbound and integrate feed lists there.

## Requirements
Python 3.9+ and internet connectivity to download feeds. No pip packages.

## Installation
Clone the repository and navigate to:
```bash
cd PROJECT/local_dns_sinkhole_updater
python3 updater.py --help
cp feeds.example.json feeds.json
```
Windows (PowerShell):
```powershell
Copy-Item feeds.example.json feeds.json
python .\\updater.py --help
```

## Quick start
Preview first without modifying any file:
```bash
python3 updater.py --config feeds.json update --dry-run
```
Apply on Linux/macOS (requires root):
```bash
sudo python3 updater.py --config feeds.json update
```
On Windows, run an elevated PowerShell and execute:
```powershell
python .\\updater.py --config feeds.json update
```

## Useful commands
```bash
# Inspect current installation
python3 updater.py status

# Test with a temporary hosts file
python3 updater.py update --hosts ./test-hosts --dry-run

# Replace config feeds for this one run; repeat --feed for additional URLs
python3 updater.py update --feed https://example.net/hosts --feed https://example.org/domains.txt

# Restore latest timestamped backup
python3 updater.py rollback
```

## Config
| Field | Description |
|---|---|
| feeds | Feed URLs (hosts format, plain domain, basic adblock rules) |
| allowlist | Exempt domain names; subdomains exempt automatically |
| block_ipv4 | Hosts mapping for IPv4 (default `0.0.0.0`) |
| block_ipv6 | IPv6 mapping; set `disabled` to omit IPv6 entries |
| timeout | HTTP timeout seconds |
| max_bytes | Maximum downloaded feed size |

## Safe operation
- Run `update --dry-run` first and consider testing with a temporary `--hosts` path.
- Verify the feeds are trustworthy and review false positives.
- A backup is created before every write; rollback restores the most recent backup.
- The script replaces only the section between its markers and preserves unrelated content.
- It refuses to edit if the managed markers are unmatched or reversed.
- Hosts blocking can affect legitimate websites and apps.
- To schedule updates, use cron (Linux/macOS) or Task Scheduler (Windows). Schedule with elevated permissions only when needed; do not use root/admin for dry-run.

## Feed notes
The parser supports common domain entries and basic adblock domain rules. It is not a full Adblock Plus parser: complex filters, cosmetic rules, exceptions, wildcards, and option-based rules are ignored. Review source feed licenses and terms.

## Limitations
This is a hosts-file updater—not a DNS resolver, DNS cache, DHCP/router manager, or DNS-over-HTTPS filter. Hosts files do not support wildcard subdomains. For enterprise deployment, consider DNS filtering products and central management.

