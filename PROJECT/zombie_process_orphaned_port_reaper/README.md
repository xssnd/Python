# Zombie Process & Orphaned Port Reaper

Linux monitor for allowlisted services with elevated CPU/RAM and unchanged disk-I/O counters. Listener ports are informational. Restarts are systemd-only and require --restart --apply; interactive confirmation is on unless --yes. Cooldown/daily limits are memory-only (reset when process exits). See the local package README for installation and caveats.

Files: monitor.py, config.example.json, requirements.txt, README.md.
