# Network Bandwidth Tracker

A lightweight Python CLI for monitoring network traffic on one or more network interfaces. It measures receive (RX) and transmit (TX) throughput from cumulative byte counters and displays live rates, totals, and short terminal trends.

## Features

- List available network interfaces and their current UP/DOWN state.
- Monitor one interface, multiple selected interfaces, or all interfaces.
- RX/TX throughput in human-readable bytes per second and Mbps.
- Cumulative received/sent byte counters.
- Live terminal dashboard with compact RX/TX trend sparklines (Rich when installed; plain terminal fallback).
- Configurable sampling interval and optional duration.
- RX/TX bandwidth threshold warnings.
- JSON Lines output for pipelines and CSV/JSONL append-only export for historical analysis.
- Optional diagnostic logging, verbose mode, version/help output, and graceful Ctrl+C/SIGTERM shutdown.
- Cross-platform counters through psutil (interface availability and permissions vary by OS).
- Read-only: it does not change interface configuration, routes, firewall rules, or network services.

## Requirements

- Python 3.10+
- psutil 5.9+
- Rich 13.7+ (for the styled dashboard; plain output remains available)

## Installation

```bash
cd PROJECT/network_bandwidth_tracker
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.venv\\Scripts\\Activate.ps1

python -m pip install -r requirements.txt
```

## Usage

```bash
# List interfaces and cumulative counters
python monitor.py --list-interfaces

# Monitor every interface (one sample after the first interval)
python monitor.py

# Continuously monitor one interface
python monitor.py --interface eth0 --watch

# Monitor Wi-Fi every 0.5 seconds
python monitor.py --interface wlan0 --watch --interval 0.5

# Monitor multiple interfaces
python monitor.py --interface eth0 --interface wlan0 --watch

# Stop automatically after 60 seconds
python monitor.py --interface eth0 --watch --interval 1 --duration 60

# Warn when either direction reaches 100 Mbps
python monitor.py --interface eth0 --watch --alert-mbps 100

# Machine-readable JSON Lines to stdout
python monitor.py --interface eth0 --watch --json

# Append historical samples
python monitor.py --interface eth0 --watch --export reports/traffic.csv --format csv
python monitor.py --interface eth0 --watch --export reports/traffic.jsonl --format json

# Plain output, diagnostics, help
python monitor.py --interface eth0 --watch --no-color
python monitor.py --log-file logs/network_tracker.log --verbose
python monitor.py --help
```

Use the actual interface names shown by `--list-interfaces`; common examples include `eth0`, `ens18`, `enp0s3`, and `wlan0`, but names vary by system.

## CLI options

| Option | Default | Description |
|---|---:|---|
| `-i, --interface` | all | Interface name; repeat to select multiple |
| `--list-interfaces` | off | List detected interfaces and exit |
| `--watch` | off | Refresh continuously |
| `--interval` | 1.0 | Sampling interval in seconds |
| `--duration` | none | Stop after N seconds |
| `--alert-mbps` | none | Warn at or above this RX or TX Mbps rate |
| `--json` | off | Emit one JSON object per sample (JSON Lines) |
| `--export` | none | Append samples to a file |
| `--format` | csv | Export format: csv or json (JSON Lines) |
| `--no-color` | off | Use plain terminal output |
| `--log-file` | none | Optional diagnostic log |
| `--verbose` | off | Enable debug logging |

## Understanding the metrics

- RX is the number of bytes received by the interface; TX is the number of bytes sent.
- Throughput is calculated as `(current_counter - previous_counter) / elapsed_seconds`.
- Mbps uses decimal network units: 1 Mbps = 1,000,000 bits per second.
- Cumulative counters are provided by the operating system and usually count traffic since boot or interface initialization. They are not per-process usage and may include protocol overhead.
- If an interface counter resets or decreases, the affected rate is safely reported as zero for that interval.
- A very short sampling interval can make rates appear bursty; 1 second is a practical default.
- VPNs, bridges, containers, loopback, and physical interfaces may report overlapping traffic. Avoid summing them as if they were independent links.
- Some operating systems expose virtual or disconnected interfaces with zero traffic. Run with suitable permissions if the OS restricts visibility.

## Unit tests

Run from this directory:

```bash
python -m unittest discover -s tests -v
```

## Project structure

```text
network_bandwidth_tracker/
├── monitor.py
├── requirements.txt
├── .gitignore
├── README.md
└── tests/
    └── test_monitor.py
```

## Operational notes

This utility is intended for lightweight host-level diagnostics. It does not capture packets, inspect payloads, identify per-process traffic, or replace SNMP/NetFlow-based network monitoring. JSON export uses newline-delimited JSON so live samples can be appended safely without rewriting an existing file.
