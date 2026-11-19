# Open Ports Checker

A read-only Python CLI that inventories listening TCP ports and locally bound UDP ports, then identifies the owning process where the operating system permits access.

## Features
- Detect TCP sockets in LISTEN state and UDP sockets bound to a local port.
- Show protocol, local address, port, state, PID, process name, username, executable, and command.
- Highlight wildcard-bound sockets (0.0.0.0 / ::) listening across available interfaces.
- Filter by protocol, one or more ports, PID, process name/command, or wildcard exposure.
- Live refresh with configurable interval and optional duration.
- Styled terminal dashboard with summary counts (Rich optional; plain-text fallback).
- Append-only CSV or JSON Lines export; machine-readable JSON Lines on stdout.
- Optional diagnostic log, verbose mode, validation, version/help, and graceful Ctrl+C/SIGTERM shutdown.
- Best-effort process metadata with placeholders when a process exits or access is denied.
- Read-only: no port probing, packet capture, firewall changes, or process termination.

## Requirements
- Python 3.10+
- psutil 5.9+
- Rich 13.7+ (optional)

## Installation
```bash
cd PROJECT/open_ports_checker
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
```

## Usage
```bash
# Show TCP listeners and UDP-bound ports
python monitor.py
# TCP only / UDP only
python monitor.py --protocol tcp
python monitor.py --protocol udp
# Full process attribution may require elevated privileges
sudo python monitor.py
# Filter by port(s), PID, or process
python monitor.py --port 22 --port 443
python monitor.py --pid 1234
python monitor.py --process nginx
# Find wildcard-bound sockets
sudo python monitor.py --exposed-only
# Live refresh
sudo python monitor.py --watch --interval 2 --duration 60
# JSON Lines stdout or append-only report
sudo python monitor.py --json
sudo python monitor.py --export reports/ports.csv --format csv
sudo python monitor.py --export reports/ports.jsonl --format json
python monitor.py --log-file logs/open_ports.log --verbose
python monitor.py --help
```

## CLI options
| Option | Description |
|---|---|
| --protocol all/tcp/udp | Protocol filter |
| -p, --port PORT | Port filter; repeatable |
| --pid PID | Filter by process ID |
| --process TEXT | Case-insensitive process/command filter |
| --exposed-only | Show wildcard-bound addresses only |
| --watch | Refresh continuously |
| --interval SECONDS | Refresh interval (default: 5) |
| --duration SECONDS | Stop after duration when watching |
| --json | JSON Lines output |
| --export PATH | Append a report |
| --format csv/json | Export format |
| --no-color | Disable styled dashboard |
| --log-file PATH | Optional diagnostic log |
| --verbose | Enable debug logging |

## Permissions and interpretation
- On Linux, use sudo for a system-wide view and process ownership for sockets belonging to other users. Without sufficient privileges, the OS may hide sockets or process metadata.
- Windows may require an elevated terminal for complete process attribution. macOS also restricts some process details.
- TCP LISTEN means a socket is waiting for incoming TCP connections. UDP has no TCP-style listening state; this tool reports UDP sockets bound to a local port as BOUND.
- A wildcard address means the socket is bound to all local interfaces, not that it is necessarily reachable from the public internet. Firewall rules, routing, NAT, and host/network policy determine reachability.
- This is a local socket inventory, not a remote port scanner. It does not test reachability from another machine.
- Process names and command lines can contain sensitive information; protect exported reports accordingly.

## Tests
Run from this directory:
```bash
python -m unittest discover -s tests -v
```

## Project structure
```text
open_ports_checker/
├── monitor.py
├── requirements.txt
├── .gitignore
├── README.md
└── tests/
    └── test_monitor.py
```
