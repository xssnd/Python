# Zombie Process Cleaner

A Linux-first Python CLI for detecting, inspecting, and reporting zombie (defunct) processes. It identifies the parent process responsible for each zombie and can optionally send that parent a SIGCHLD signal after explicit confirmation.

> **Important:** A zombie has already exited. It cannot be killed with kill, SIGTERM, or SIGKILL. The parent must collect its exit status with wait() / waitpid(). This tool never attempts to kill a zombie or terminate its parent.

## Features

- Detect zombie processes through psutil and Linux process state.
- Show PID, PPID, process name, owner, start time, approximate age, and parent details.
- Group zombies by parent PID and highlight parents with multiple zombies.
- Rich colored terminal dashboard with plain-text fallback.
- One-shot scan and live watch mode with configurable refresh interval.
- Minimum zombie age filter and configurable count alert threshold.
- JSON output and JSON/CSV report export.
- Optional SIGCHLD nudge to one verified parent PID, with interactive confirmation; --yes is an explicit opt-in.
- Re-scan after signaling to check whether zombies were reaped.
- Diagnostic logging, validation, error handling, and graceful Ctrl+C/SIGTERM shutdown.
- Read-only by default; no automatic signals, process termination, or system configuration changes.

## Requirements

- Linux with /proc mounted.
- Python 3.10+.
- psutil >= 5.9.0.
- rich >= 13.0.0 for the enhanced dashboard (plain output fallback is included).

## Installation

~~~~bash
cd PROJECT/zombie_process_cleaner
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
~~~~

On Debian/Ubuntu, install python3-venv first if needed: sudo apt install python3-venv.

## Usage

~~~~bash
# Safe one-time scan
python monitor.py

# Live dashboard, refresh every 3 seconds
python monitor.py --watch --interval 3

# Show only zombies at least 60 seconds old
python monitor.py --min-age 60

# Alert when 5 or more zombies are present
python monitor.py --threshold 5

# Machine-readable output
python monitor.py --json

# Export a report
python monitor.py --export reports/zombies.json
python monitor.py --export reports/zombies.csv --format csv

# Ask a specific parent to handle SIGCHLD (interactive confirmation)
python monitor.py --signal-parent 1234

# Explicitly approve the signal in automation
python monitor.py --signal-parent 1234 --yes

# Diagnostics and help
python monitor.py --log-file logs/zombie_cleaner.log --verbose
python monitor.py --help
~~~~

Use the PPID from a fresh scan. The command refuses PID 1, the cleaner's own PID, and parent PIDs that do not currently own a detected zombie. --yes only skips confirmation; it does not bypass these checks.

## Understanding cleanup

1. A child process exits.
2. The kernel retains a small process-table entry containing its PID and exit status.
3. The parent is expected to call wait() / waitpid() to collect that status.
4. The kernel then removes the zombie entry.

Sending SIGCHLD is only a nudge. It may help a parent that has a suitable signal handler, but it is not guaranteed to make the parent reap children. If zombies remain, investigate the parent application, its child-process handling, and its logs. Fix the parent so it reliably calls wait() / waitpid() or uses a process-management library correctly.

This tool deliberately does not offer a kill-zombie feature: signaling an already-exited zombie has no effect. It also does not kill parent processes because doing so can interrupt services and cause data loss. Evaluate and perform any parent restart or termination through the service's normal operational procedure.

## Permissions and limitations

- Root may be required to see metadata for processes owned by other users; restricted entries may be skipped.
- Detection is Linux-only. Windows and macOS do not expose Linux zombie state through this tool.
- Age is based on process creation time and is an approximation.
- A zombie consumes a process-table slot, not meaningful ongoing CPU or resident memory. A large accumulation can eventually contribute to process-table/PID exhaustion.
- SIGCHLD behavior depends on the parent program. A successful signal send does not mean cleanup succeeded; the post-action scan is the verification step.

## Unit tests

Run from this directory:

~~~~bash
python -m unittest discover -s tests -v
~~~~

## Project structure

~~~~text
zombie_process_cleaner/
├── monitor.py
├── requirements.txt
├── .gitignore
├── README.md
└── tests/
    └── test_monitor.py
~~~~
