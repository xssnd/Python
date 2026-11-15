# Process Watcher

A configurable Python process supervisor for Linux, Windows, and macOS. It detects missing critical processes and executes explicitly configured restart commands, with retry limits, cooldowns, notifications, and logging.

## Features

- Monitor multiple processes by executable name or command-line substring.
- User-defined process list and restart commands in JSON.
- Optional automatic restart using argument arrays (no shell execution).
- Per-process restart timeout, cooldown, maximum attempts, and retry window to prevent restart loops.
- Telegram, Discord webhook, and SMTP email notifications.
- Down, restart result, and recovery notifications.
- Environment-variable overrides for notification secrets.
- One-shot check, continuous mode, console/file logging, and graceful shutdown.
- Cross-platform process detection; restart commands depend on the host OS/service manager.

## Requirements

- Python 3.9+
- psutil
- Permission to inspect target processes and execute configured restart commands.

## Installation

```bash
cd PROJECT/process_watcher
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp config.example.json config.json
```

Edit config.json and select the processes to monitor. The sample uses Linux systemd commands for Nginx and MySQL; change them for your OS and service manager.

## Configuration

Each entry in the processes array contains:

| Key | Required | Description |
|---|---|---|
| name | Yes | Friendly process/service name |
| match | Yes | Executable names and/or command-line substrings |
| restart_command | No | Argument list executed when absent; empty means alert-only |
| restart_timeout_seconds | No | Maximum command runtime (default 30 seconds) |

Example custom process:

```json
{
  "name": "My API",
  "match": ["gunicorn"],
  "restart_command": ["sudo", "-n", "systemctl", "restart", "my-api"]
}
```

Settings include interval_seconds (10), restart_cooldown_seconds (60), max_restart_attempts (3), retry_window_seconds (300), recovery_notifications (true), and optional log_file.

## Notifications

Configure channels in JSON or use environment variables:

| Channel | Environment variables |
|---|---|
| Telegram | PW_TELEGRAM_BOT_TOKEN, PW_TELEGRAM_CHAT_ID |
| Discord | PW_DISCORD_WEBHOOK_URL |
| Email | PW_SMTP_HOST, PW_SMTP_PORT, PW_SMTP_USERNAME, PW_SMTP_PASSWORD, PW_EMAIL_FROM, PW_EMAIL_TO |

Leave channels empty for console/file logging only. Never commit credentials or config.json.

## Usage

```bash
# Continuous monitoring
python monitor.py --config config.json

# Single check
python monitor.py --config config.json --once

# Unit tests
python -m unittest discover -s tests -v
```

## Linux permissions and systemd

The sample restart commands use sudo -n, which never prompts for a password. Configure a narrowly scoped sudoers rule with visudo, for example:

```sudoers
monitor ALL=(root) NOPASSWD: /usr/bin/systemctl restart nginx, /usr/bin/systemctl restart mysql
```

Verify the actual systemctl path with command -v systemctl. Do not grant unrestricted sudo access. Run the watcher as an unprivileged dedicated user.

Example service file at /etc/systemd/system/process-watcher.service:

```ini
[Unit]
Description=Python Process Watcher
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=monitor
WorkingDirectory=/opt/process_watcher
ExecStart=/opt/process_watcher/.venv/bin/python /opt/process_watcher/monitor.py --config /opt/process_watcher/config.json
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable it with: sudo systemctl daemon-reload && sudo systemctl enable --now process-watcher.

## Safety and operational notes

- Restart commands are argument lists and run with shell=False. Shell pipelines and shell metacharacters are not interpreted.
- A configured command runs with the watcher's OS permissions. Only configure commands you trust.
- Process-name matching can produce false positives when multiple instances or similarly named processes exist. Prefer a distinctive command-line substring when needed.
- Process detection may be incomplete without sufficient OS permissions.
- A successful restart command does not prove service health; process presence is checked on the next polling cycle.
- On Windows, configure and test an appropriate PowerShell Restart-Service command under the same account that runs the watcher.
- Use the native service manager for production services.

## Troubleshooting

- Run with --once to validate process matching.
- Confirm executable names match what the OS reports.
- Test restart commands manually as the watcher account.
- Check sudoers permissions; sudo -n must not prompt interactively.
- Notification delivery errors are logged and do not stop monitoring.

## License

Use according to the license of the parent repository.
