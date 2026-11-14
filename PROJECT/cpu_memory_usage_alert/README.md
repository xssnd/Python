# CPU & Memory Usage Alert

A lightweight Python service that monitors CPU and RAM usage and sends alerts to Telegram, Discord, and/or Email (SMTP). It supports configurable thresholds, consecutive-sample protection, cooldowns, recovery notifications, and file logging.

## Features

- CPU and virtual memory monitoring using `psutil`.
- Independent CPU and RAM thresholds (percentage).
- Require consecutive breached samples to reduce false positives.
- Telegram Bot API, Discord webhook, and SMTP email notifications.
- Multiple notification channels can be enabled simultaneously.
- Per-alert cooldown and optional recovery messages.
- JSON configuration with environment-variable overrides for secrets.
- Graceful shutdown on SIGINT/SIGTERM.
- One-shot mode for quick checks; logs to console and file.

## Requirements

- Python 3.9+
- Linux, macOS, or Windows
- Network access for enabled notification channels

## Installation

```bash
cd PROJECT/cpu_memory_usage_alert
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

Edit `config.json`. Example:

```json
"monitor": {
  "interval_seconds": 10,
  "cpu_threshold": 85,
  "memory_threshold": 85,
  "cooldown_seconds": 300,
  "consecutive_breaches": 2,
  "recovery_notifications": true
}
```

## Configure notifications

Enable one or more channels in `config.json`. Keep credentials out of version control; environment variables override values in the file:

| Channel | Environment variables |
|---|---|
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| Discord | `DISCORD_WEBHOOK_URL` |
| Email | `SMTP_PASSWORD` |

Telegram: create a bot with BotFather, obtain its token, and provide the destination chat ID. Discord: create an incoming webhook for the target channel. Email: configure an SMTP host, port, username, sender, recipient list, and password/app password. Use provider-specific app passwords where required.

Example (Linux/macOS):

```bash
export TELEGRAM_BOT_TOKEN="your-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
export SMTP_PASSWORD="your-smtp-app-password"
```

Do not commit `config.json`, tokens, passwords, or webhook URLs.

## Usage

Run continuously:

```bash
python monitor.py --config config.json
```

Collect one sample and exit:

```bash
python monitor.py --config config.json --once
```

Press Ctrl+C to stop. The monitor writes `cpu_memory_alert.log` (or the configured log path).

## Alert behavior

- An alert starts after the configured number of consecutive samples at or above its threshold.
- While the condition remains active, reminders are limited by `cooldown_seconds`.
- When usage drops below the threshold, the alert is cleared and (if enabled) a recovery notification is sent.
- If no notification channel is enabled, alerts are still recorded in the log.
- Notification failures are logged and do not terminate metric collection.

## Run at startup (systemd example)

Create `/etc/systemd/system/cpu-memory-alert.service` and adjust the paths and service user:

```ini
[Unit]
Description=CPU and Memory Usage Alert
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=monitor
WorkingDirectory=/opt/cpu_memory_usage_alert
ExecStart=/opt/cpu_memory_usage_alert/.venv/bin/python /opt/cpu_memory_usage_alert/monitor.py --config /opt/cpu_memory_usage_alert/config.json
Restart=on-failure
RestartSec=5
EnvironmentFile=-/etc/cpu-memory-alert.env

[Install]
WantedBy=multi-user.target
```

Protect the environment file:

```bash
sudo chmod 600 /etc/cpu-memory-alert.env
sudo systemctl daemon-reload
sudo systemctl enable --now cpu-memory-alert
sudo systemctl status cpu-memory-alert
```

## Troubleshooting

- Confirm the virtual environment is active and `psutil` is installed.
- Verify notification credentials and outbound network access.
- Check the log file for delivery errors.
- For Gmail or other providers, use an SMTP app password if regular account passwords are blocked.
- Use `--once` to validate configuration and metric collection.

## Security notes

- Prefer environment variables or a root-readable environment file for secrets.
- Restrict permissions on configuration and log files.
- Use HTTPS Discord webhooks and TLS-enabled SMTP.
- Never publish bot tokens, webhook URLs, or SMTP credentials.

## License

Use according to the license of the parent repository.
