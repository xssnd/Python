# Top Resource Consumers

A lightweight, read-only Python CLI that identifies the processes using the most CPU or physical memory. It works on Linux, Windows, and macOS through psutil.

## Features

- Top N CPU consumers, memory consumers, or both (default: top 5).
- Live dashboard with configurable refresh interval and system-wide CPU/RAM meters.
- Process PID, name, username, state, CPU percentage, RAM percentage, resident memory (MB), and thread count.
- Case-insensitive process-name filtering and username filtering.
- Inspect a single process by PID.
- JSON output for scripts and integrations; CSV or JSON file export.
- Handles short-lived processes, permission restrictions, and processes that exit during collection.
- Optional diagnostic logging, clear CLI help, version output, and graceful Ctrl+C/SIGTERM shutdown.
- Cross-platform process inspection via psutil.
- Read-only operation: never terminates processes, changes priorities, or modifies system settings.

## Requirements

- Python 3.10+
- psutil 5.9+

## Installation

```bash
cd PROJECT/top_resource_consumers
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt
```

## Usage

```bash
# Show the top 5 CPU consumers (default)
python monitor.py

# Top 10 memory consumers
python monitor.py --sort memory --top 10

# Show CPU and memory rankings
python monitor.py --sort both --top 5

# Live dashboard, refresh every 2 seconds
python monitor.py --watch --interval 2

# Filter process names or users
python monitor.py --filter python
python monitor.py --user root

# Inspect one PID
python monitor.py --pid 1234

# Machine-readable output
python monitor.py --json
python monitor.py --sort both --json

# Export the selected ranking
python monitor.py --sort memory --export reports/top-memory.csv --format csv
python monitor.py --sort both --export reports/top-processes.json --format json

# Diagnostic log and help
python monitor.py --log-file logs/resource_consumers.log --verbose
python monitor.py --help
```

Press Ctrl+C to stop live monitoring.

## CLI options

| Option | Default | Description |
|---|---:|---|
| `--sort` | cpu | cpu, memory, or both |
| `--top` | 5 | Number of processes in each ranking |
| `--watch` | off | Continuously refresh the dashboard |
| `--interval` | 2.0 | Refresh interval in seconds |
| `--filter` | none | Process-name substring filter |
| `--user` | none | Username filter |
| `--pid` | none | Inspect a specific process |
| `--json` | off | Print JSON to stdout |
| `--export` | none | Export selected records to a path |
| `--format` | json | Export format: json or csv |
| `--log-file` | none | Optional diagnostic log |
| `--verbose` | off | Enable debug logging |

## Understanding CPU and memory values

- CPU percentage is measured by psutil over a short sampling window. On multi-core systems a process may exceed 100% when it uses more than one logical CPU.
- RAM percentage is the process resident memory as a percentage of total physical memory; RAM MB is its resident set size (RSS).
- Processes that disappear during sampling or deny access may be skipped. Run with suitable privileges if you need visibility into protected system processes.
- A zero CPU value can occur for newly started processes or very short sampling windows.

## Unit tests

Run from this directory:

```bash
python -m unittest discover -s tests -v
```

## Project structure

```text
top_resource_consumers/
├── monitor.py
├── requirements.txt
├── .gitignore
├── README.md
└── tests/
    └── test_monitor.py
```

## Operational notes

The tool is intended for interactive diagnostics and lightweight snapshots, not as a replacement for a full metrics/observability stack. CPU sampling briefly waits for each process, so very large process tables may take longer to scan. JSON is written to stdout; diagnostic logs go to stderr.
