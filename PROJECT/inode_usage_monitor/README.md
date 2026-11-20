# Inode Usage Monitor

A Linux-first, read-only Python CLI that monitors inode consumption across mounted filesystems. It catches inode exhaustion even when a filesystem still has free disk space.

## Features

- Reads per-filesystem inode counters with `os.statvfs()` and discovers mounts from `/proc/self/mountinfo` (no external commands required).
- Displays total, used, free, and user-available inodes plus usage percentage and a terminal progress bar.
- Configurable `OK`, `WARNING`, and `CRITICAL` thresholds (defaults: 80% and 90% used).
- One-shot scans or a continuously refreshing dashboard with graceful Ctrl+C/SIGTERM shutdown.
- Filter to selected mount points, exclude mount points, and optionally include pseudo filesystems.
- JSON stdout for monitoring integrations and JSON/CSV report export.
- Optional diagnostic logging, verbose mode, `--help`, and version output.
- Exit code `1` when any filesystem is CRITICAL in one-shot mode; `0` otherwise; `2` for invalid input or runtime errors.
- Read-only by design: never creates, deletes, or modifies files on monitored filesystems.
- Standard-library only; no pip dependencies.

## Requirements

- Linux (uses `/proc/self/mountinfo`)
- Python 3.10+
- Permission to read mount metadata and call `statvfs` on target mount points

## Installation

```bash
git clone https://github.com/xssnd/Python.git
cd Python/PROJECT/inode_usage_monitor
python3 --version
```

No virtual environment or package installation is required. Optionally create one:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Usage

```bash
# One scan
python3 monitor.py

# Set warning/critical thresholds
python3 monitor.py --warning 75 --critical 90

# Monitor continuously, refresh every 15 seconds
python3 monitor.py --watch --interval 15

# Inspect selected mounts
python3 monitor.py --mount / --mount /var

# Exclude noisy or temporary mounts
python3 monitor.py --ignore-mount /run --ignore-mount /tmp

# Include pseudo filesystems (proc, sysfs, etc.)
python3 monitor.py --include-pseudo

# JSON output for scripts / monitoring agents
python3 monitor.py --json

# Export a report
python3 monitor.py --export reports/inode-report.json
python3 monitor.py --export reports/inode-report.csv --format csv

# Diagnostics and help
python3 monitor.py --log-file logs/inode-monitor.log --verbose
python3 monitor.py --help
```

## CLI options

| Option | Default | Description |
|---|---:|---|
| `--once` | off | Perform one scan and exit (also default without `--watch`) |
| `--watch` | off | Refresh continuously until interrupted |
| `--interval` | 30 | Refresh interval in seconds; must be positive |
| `--warning` | 80 | Warning threshold for inode usage (%) |
| `--critical` | 90 | Critical threshold for inode usage (%) |
| `--mount` | all | Restrict scan to a mount point; repeatable |
| `--ignore-mount` | none | Exclude a mount point; repeatable |
| `--include-pseudo` | off | Include pseudo filesystems such as proc and sysfs |
| `--json` | off | Emit JSON to stdout |
| `--export` | none | Write a JSON or CSV report |
| `--format` | json | Export format: `json` or `csv` |
| `--log-file` | none | Optional diagnostic log path |
| `--verbose` | off | Enable debug logging |
| `--no-color` | off | Disable terminal colors |

## Understanding inode metrics

- **Total** is the filesystem inode capacity (`f_files`).
- **Used** is calculated as `total - free` (`f_ffree`).
- **Free** is the filesystem free-inode counter.
- **Available** is `f_favail`, the number of free inodes available to unprivileged users; it may differ from free inodes due to filesystem reservations.
- Usage percentage is calculated from used/total. A filesystem may run out of inodes while byte capacity remains available. Filesystems without a finite inode count are skipped.
- Bind mounts are shown as separate mount points because they can represent distinct operational paths to the same filesystem.

## Automation

Run `python3 monitor.py --json` from cron or a monitoring agent. In one-shot mode, exit code `1` indicates at least one CRITICAL filesystem and `0` indicates no critical filesystem. JSON mode is intended for structured ingestion; the process exit code remains the same.

## Unit tests

```bash
python3 -m unittest discover -s tests -v
```

## Project structure

```text
inode_usage_monitor/
├── monitor.py
├── requirements.txt
├── README.md
└── tests/
    └── test_monitor.py
```

## Operational notes

- This utility reports inode pressure; it does not identify or delete files consuming inodes. Investigate carefully before removing anything.
- Inode counters and semantics vary by filesystem. Filesystems without a finite inode count may not provide meaningful results.
- The tool is Linux-specific; Windows and macOS are not supported.
