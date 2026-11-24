# Smart Log Anomaly Grepper

A lightweight, local-first log anomaly scanner for Linux log files and Windows Event Logs. It uses token rarity, template novelty, and character entropy to flag suspicious lines—without requiring an ELK stack, database, or third-party Python packages.

## Highlights
- **Baseline training:** learn common tokens and normalized message templates from a known-good log sample.
- **Anomaly scoring:** combines token rarity, unseen message templates, and character entropy.
- **Linux:** scan one or more text logs, including `/var/log` files; follow one file in real time.
- **Windows:** query recent System/Application events with built-in PowerShell `Get-WinEvent`.
- **Output:** readable terminal, JSON Lines, or CSV.
- **Tuning:** threshold, ignore regexes, allowlist regexes, minimum line length, and maximum line size via config.
- **Privacy-minded:** analysis is local; no log content is sent anywhere.
- **No dependencies:** Python 3.9+ standard library only.

> This is a heuristic triage tool, not a security verdict or SIEM replacement. Train a baseline from representative normal activity, review alerts, and tune false positives.

## Installation
Python 3.9 or newer. Clone/download this folder and run:

```bash
chmod +x grepper.py
python3 grepper.py --help
```

## Quick start (Linux)

Scan a file without a baseline (heuristic mode):
```bash
python3 grepper.py /var/log/auth.log
```

Train a baseline from a known-good sample:
```bash
python3 grepper.py /var/log/auth.log /var/log/syslog --train --save-model baseline.json
```

Detect against that baseline:
```bash
python3 grepper.py /var/log/auth.log --model baseline.json
```

Follow new lines (single file; alerts as new entries arrive):
```bash
python3 grepper.py /var/log/auth.log --model baseline.json --follow
```

Pipe input:
```bash
tail -n 500 /var/log/auth.log | python3 grepper.py - --model baseline.json --format json
```

## Windows Event Log
Run in PowerShell or CMD with Python installed. Queries recent warning/error/critical events (level 3 by default) from System and Application channels:
```powershell
python .\grepper.py --windows-eventlog --model baseline.json
python .\grepper.py --windows-eventlog --channels System Security --event-level 2 --max-events 250 --format json
```
Use appropriate permissions for channels such as Security. Event-log support relies on Windows PowerShell and does not install packages.

## CLI examples
```bash
# Adjust score threshold (lower is more sensitive)
python3 grepper.py /var/log/syslog --model baseline.json --threshold 4.2

# JSONL output for automation
python3 grepper.py /var/log/auth.log --model baseline.json --format json

# CSV output
python3 grepper.py /var/log/auth.log --model baseline.json --format csv

# Filter output by a minimum score as well as configured threshold
python3 grepper.py /var/log/auth.log --model baseline.json --min-score 7.0
```

## Configuration
Copy `config.example.json` to a custom JSON file and use `--config config.json`.
- `threshold`: anomaly score threshold; lower values increase sensitivity.
- `ignore_patterns`: regex patterns to ignore.
- `allow_patterns`: regex patterns to suppress known-safe matching lines.
- `min_line_length`: skip shorter lines.
- `max_line_length`: flag exceptionally long lines.

## Suggested workflow
1. Collect representative, known-normal log samples.
2. Train the baseline and protect the model file from unauthorized modification.
3. Scan current logs with the baseline and review output.
4. Tune ignore/allow rules and threshold cautiously.
5. Periodically retrain only from trusted, clean samples; compare models before replacing.

## Limitations
- Baseline/model quality strongly affects alert quality.
- Novelty can be benign (new deployment, package update, normal user activity).
- Windows Event Log queries use PowerShell and selected channels/levels; this is not a full EVTX parser.
- File permissions may restrict access to protected logs; use least privilege and avoid running as root/admin unless necessary.
- The script reads supplied logs; it does not delete, rotate, or modify them.
