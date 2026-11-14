# Disk Space Monitor

A lightweight Python utility that monitors the capacity of **every mounted partition/filesystem** and sends alerts when available free space falls to **10% or less**.

## Features

- Cross-platform partition discovery using `psutil` (Linux, Windows, and macOS).
- `OK`, `WARNING` (default: free space <= 10%), and `CRITICAL` (default: free space <= 5%) status levels.
- Displays mount point, device, filesystem, total capacity, used space, and available free space.
- One-shot scan mode (`--once`) or continuous monitoring.
- Optional notifications through Telegram, Discord Webhooks, and SMTP email.
- Per-mount-point notification cooldown to prevent spam, plus recovery notifications when conditions return to normal.
- JSON configuration and environment variables for credentials.
- Ignore selected mount points, optionally exclude removable drives, and emit JSON output.
- Console/file logging, graceful shutdown (Ctrl+C/SIGTERM), and unit tests.
- Unreadable filesystems are skipped without interrupting the monitoring process.

## Requirements

- Python 3.10+
- Dependency: `psutil`

## Installation

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
cp config.example.json config.json
```

Edit `config.json` to configure the monitor. You can configure one or more notification channels; without notification settings, scan results are still displayed in the terminal.

## Usage

```bash
# Run a single scan
python monitor.py --once

# Run continuous scans using the configured interval
python monitor.py

# Output JSON for integrations or automation
python monitor.py --once --json

# Specify a custom configuration file
python monitor.py --config /path/to/config.json
```

The default scan interval is 5 minutes. The minimum supported interval is 5 seconds.

## Configuration

| Key | Default | Description |
|---|---:|---|
| `warning_percent` | 10 | Send a warning when free space is <= this value |
| `critical_percent` | 5 | Mark the filesystem as critical when free space is <= this value |
| `interval_seconds` | 300 | Delay between scans |
| `cooldown_seconds` | 3600 | Delay between repeated notifications for each mount point |
| `recovery_alerts` | true | Send a notification when a partition returns to a healthy state |
| `include_removable` | true | Include removable drives |
| `ignored_mounts` | [] | List of mount points to ignore |
| `log_file` | null | Optional log file path |

### Credential environment variables

| Channel | Environment variables |
|---|---|
| Telegram | `DSM_TELEGRAM_BOT_TOKEN`, `DSM_TELEGRAM_CHAT_ID` |
| Discord | `DSM_DISCORD_WEBHOOK_URL` |
| Email | `DSM_SMTP_HOST`, `DSM_SMTP_PORT`, `DSM_SMTP_USERNAME`, `DSM_SMTP_PASSWORD`, `DSM_EMAIL_FROM`, `DSM_EMAIL_TO` |

Environment variables take precedence over values in the JSON configuration. Do not commit `config.json`, bot tokens, passwords, or webhook URLs to Git.

## Unit Tests

```bash
python -m unittest discover -s tests -v
```

The tests cover threshold boundaries, status classification, inaccessible filesystems, duplicate mount points, notification cooldowns, and recovery alerts.

## Project Structure

```text
disk_space_monitor/
├── monitor.py
├── notifiers.py
├── config.example.json
├── requirements.txt
├── .gitignore
├── README.md
└── tests/
    └── test_monitor.py
```

## Operational Notes

- Run the monitor with an account that has permission to read filesystem information.
- Use SMTP TLS/STARTTLS according to your mail server's security policy.
- Notifications require an internet connection. Notification-channel failures are logged and do not stop filesystem scans.
- Free-space percentage is calculated as available free bytes divided by total filesystem capacity.
