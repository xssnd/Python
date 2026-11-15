# Uptime Logger

A lightweight Python utility that records local host uptime and remote server/service availability to CSV for reliability analysis. It supports HTTP/HTTPS and TCP checks, transition alerts, and sample-based availability reports.

## Features

- Periodic CSV logging with UTC timestamps and a stable spreadsheet-friendly schema.
- Local machine uptime measurement (time since boot).
- Multiple HTTP/HTTPS endpoints and TCP services such as SSH, MySQL, PostgreSQL, and custom ports.
- Configurable expected HTTP status, connection timeout, and sampling interval.
- Records UP/DOWN state, response time, HTTP status, error details, and host uptime.
- Telegram, Discord webhook, and SMTP email alerts for outages and recovery.
- Alert cooldown to prevent notification flooding.
- Per-target availability summary, JSON console output, one-shot mode, and graceful shutdown.
- User-defined targets; no hard-coded service list.

> Availability is sample-based. A failure shorter than the polling interval can be missed. Use a suitably short interval for SLA analysis.

## Requirements

- Python 3.10+
- psutil

## Installation

    python -m venv .venv
    # Linux/macOS
    source .venv/bin/activate
    # Windows PowerShell
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    cp config.example.json config.json

Edit config.json and remove or replace example targets.

## Configuration

HTTP/HTTPS target example:

    {"name":"Website","type":"http","url":"https://example.com","expected_status":200}

TCP target example:

    {"name":"MySQL","type":"tcp","host":"127.0.0.1","port":3306}

| Setting | Default | Description |
|---|---:|---|
| interval_seconds | 60 | Seconds between check cycles |
| timeout_seconds | 5 | Per-target connection timeout |
| csv_file | data/uptime.csv | CSV output path |
| include_local_host | true | Record local machine uptime |
| cooldown_seconds | 3600 | Minimum interval between repeated DOWN alerts |
| recovery_alerts | true | Notify when a target recovers |

Notification secrets can be provided through environment variables:

- UL_TELEGRAM_BOT_TOKEN and UL_TELEGRAM_CHAT_ID
- UL_DISCORD_WEBHOOK_URL
- UL_SMTP_HOST, UL_SMTP_PORT, UL_SMTP_USERNAME, UL_SMTP_PASSWORD
- UL_EMAIL_FROM and UL_EMAIL_TO

Keep credentials out of version control. SMTP uses STARTTLS.

## Usage

Run continuously:

    python monitor.py

Run one check cycle:

    python monitor.py --once

Print JSON records:

    python monitor.py --once --json

Use another configuration:

    python monitor.py --config /path/to/config.json

Show availability summary from the CSV:

    python monitor.py --summary

Run unit tests:

    python -m unittest discover -s tests -v

## CSV schema

| Column | Meaning |
|---|---|
| timestamp_utc | Sample timestamp in UTC |
| target | Target name or localhost |
| check_type | host, http, or tcp |
| status | UP or DOWN |
| response_time_ms | Probe duration in milliseconds |
| http_status | HTTP response code, when applicable |
| error | Failure or unexpected-status details |
| host_uptime_seconds | Local time since boot, for host row |

## Notes and limitations

- Local boot-time uptime is available on platforms supported by psutil.
- HTTP checks validate the configured status code only; they do not inspect page content.
- TCP checks validate port reachability only, not application authentication or query execution.
- Targets are checked sequentially; large target lists increase cycle duration.
- CSV files are append-only. Apply external rotation and retention policies for long-running deployments.
- Run under systemd or another service manager on Linux to keep collection active after logout and across reboots.

## License

Use and modify according to the parent repository license.
