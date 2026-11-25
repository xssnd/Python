# Zombie Process & Orphaned Port Reaper

Linux-oriented process watch utility for detecting allowlisted processes that cross CPU or RAM thresholds while their disk-I/O counters remain unchanged for a configured duration. It lists listener sockets as context and optionally restarts configured systemd services.

## Safety and limitations
- Read-only by default. Restart actions require both `--restart` and `--apply`; interactive confirmation is enabled unless `--yes` is set.
- Never kills arbitrary PIDs. Only configured systemd service units can be restarted.
- Cooldown and daily restart caps are in-memory and reset when the tool exits.
- psutil does not provide portable per-process network byte counters; listener presence is informational, so this cannot reliably prove a port is orphaned or a process is network-idle.
- Start with dry-run and review candidates; a quiet service may be healthy.

## Install
```bash
cd PROJECT/zombie_process_orphaned_port_reaper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
# Edit config.json: precise process matches and service names only.
```
Requires Python 3.10+, psutil, Linux/systemd for restarts. Rich is optional for enhanced output.

## CLI
```bash
python monitor.py
python monitor.py --watch --interval 30
python monitor.py --json
python monitor.py --export report.json
python monitor.py --export report.csv --format csv
python monitor.py --restart             # dry-run
python monitor.py --restart --apply     # confirm before each service restart
python monitor.py --watch --restart --apply --yes  # unattended (use cautiously)
python monitor.py --help
```

## Config
`idle_hours` is the required disk-I/O-counter inactivity period. Candidate is flagged when either configured CPU% or RAM threshold is exceeded, AND the idle duration is met. The process list maps match patterns to explicit systemd unit names. Restart cooldown and daily limit are per unit but stored only in memory.

## Caveat
Network traffic is not measured per process; ports are displayed as supplemental context only. The inactivity test is based on disk counters, not a complete network+disk inactivity detector.
