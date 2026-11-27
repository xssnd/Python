# Dynamic Firewall Blacklist Sync

Log-driven defensive IP blocking for Linux nftables/iptables and Windows Defender Firewall. **Dry-run is the default; `--apply` is required for changes.**

## Features
- Configurable log sources, suspicious regex signatures, IPv4 extraction patterns (custom regex may be adapted for other formats).
- Threshold detection, rolling window, allowlist/CIDR exclusions.
- Ignores loopback, reserved, multicast, unspecified and private IPs by default.
- nftables timeout-set support, iptables dedicated INPUT chain, Windows named inbound firewall rules.
- One-shot scan, follow mode, candidate status, manual unblock, configurable polling.
- Python standard library only; subprocess arguments are passed without shell execution.

## Caution / backend notes
Review signatures and allowlist to prevent false positives and self-lockout. Default signatures are examples; tune for your application logs.
- nftables needs an existing `inet filter` table; it creates a set but **does not add a rule referencing the set**, so integrate the set into your firewall policy before expecting enforcement.
- iptables blocks are persistent (no automatic expiry); manually remove/unblock or prefer nftables for timeouts.
- Windows Defender rules persist; automatic expiration is not implemented there.
- `--watch` follows appended logs; restart it after log rotation/replacement.
- Run with administrative/root privileges only when applying, and test in preview first.

## Install
Python 3.9+; no pip dependencies.
```bash
cp config.example.json config.json
python3 -m py_compile dynamic_firewall_sync.py
```

## CLI
```bash
# Preview candidates only / show detected list
python3 dynamic_firewall_sync.py --config config.json --status
python3 dynamic_firewall_sync.py --config config.json

# Apply after reviewing; Linux examples
sudo python3 dynamic_firewall_sync.py --config config.json --apply
sudo python3 dynamic_firewall_sync.py --config config.json --backend nftables --apply
sudo python3 dynamic_firewall_sync.py --config config.json --backend iptables --apply

# Watch logs (preview unless --apply is given)
sudo python3 dynamic_firewall_sync.py --config config.json --watch --apply

# Use an explicit log and thresholds
python3 dynamic_firewall_sync.py --log /var/log/nginx/access.log --threshold 12 --window 180
python3 dynamic_firewall_sync.py --config config.json --allow 203.0.113.8/32

# Unblock/remove a rule
sudo python3 dynamic_firewall_sync.py --backend nftables --unblock 198.51.100.10 --apply

# Windows PowerShell (elevated)
python dynamic_firewall_sync.py --config config.json --backend windows --apply
```

## Config
`log_files`, `threshold`, `window_seconds`, `block_time`, `allowlist`, `suspicious_patterns`, `ip_regex`, backend object names. Named regex capture `ip` is recommended.
Run tests with `python3 -m unittest discover -s tests -v`.
