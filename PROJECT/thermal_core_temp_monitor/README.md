# Thermal & Core Temp Monitor

A Linux-first CPU temperature monitor that reads **`sensors` from lm-sensors**, supplements readings from sysfs hwmon/psutil, displays a live terminal dashboard, and warns about overheating.

## Features

- Live, color-aware terminal dashboard with sensor bars and NORMAL / WARNING / CRITICAL states.
- Reads `sensors` output and supplements it with Linux `/sys/class/hwmon` and optional psutil readings.
- Reports package/core labels exactly as exposed by the hardware and driver; it never invents per-core data.
- Configurable warning/critical thresholds, sample interval, consecutive critical samples, and alert cooldown.
- Telegram and Discord alerts; credentials can be supplied through environment variables.
- JSON output for scripts/monitoring pipelines.
- One-shot mode, CLI threshold overrides, custom sensors executable, log file, graceful Ctrl+C/SIGTERM.
- Reports Linux thermal-throttle counters when exposed by the CPU driver.

## Requirements

- Python 3.10+
- Linux recommended
- `lm-sensors` (recommended; command: `sensors`)
- Optional Python dependency: `psutil`

### Install lm-sensors

Debian / Ubuntu:
```bash
sudo apt update && sudo apt install -y lm-sensors
sudo sensors-detect
sensors
```

RHEL / Rocky / AlmaLinux:
```bash
sudo dnf install -y lm_sensors
sudo sensors-detect
sensors
```

Arch Linux:
```bash
sudo pacman -S lm_sensors
sudo sensors-detect
sensors
```

Sensor availability depends on the motherboard, CPU, kernel driver, and permissions. Virtual machines may not expose host sensors.

## Installation

```bash
cd PROJECT/thermal_core_temp_monitor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
```

## CLI

```bash
python monitor.py                         # live dashboard
python monitor.py --once                  # one sample
python monitor.py --interval 2            # sample every 2 seconds
python monitor.py --warning 75 --critical 88
python monitor.py --json --once           # machine-readable output
python monitor.py --no-color
python monitor.py --sensors-command /usr/bin/sensors
python monitor.py --config /etc/temperature-monitor.json
python monitor.py --help
```

Exit status: `0` when a one-shot sample contains readings, `1` when no sensor data is available, and `2` for invalid configuration/CLI values.

## Configuration

Edit `config.json`:

| Key | Default | Meaning |
|---|---:|---|
| `interval_seconds` | 5 | Sampling interval (1–3600 seconds) |
| `warning_celsius` | 80 | Warning threshold |
| `critical_celsius` | 90 | Critical threshold; must exceed warning |
| `consecutive_samples` | 2 | Critical samples required before alert |
| `cooldown_seconds` | 300 | Minimum seconds between alerts |
| `log_file` | temperature_monitor.log | Log file (relative to project directory unless absolute) |

Set notification providers under `alerts`. Prefer environment variables for secrets:
```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

Never commit `config.json`, tokens, or webhook URLs.

## Interpreting readings and alerts

- WARNING is raised when the hottest sensor reaches the warning threshold.
- A remote overheating alert is sent after the critical threshold is reached for the configured consecutive sample count.
- An increase in an exposed kernel thermal-throttle counter triggers an alert immediately (subject to cooldown).
- A high temperature is a risk indicator, not proof of throttling. Counter availability varies by CPU vendor, kernel, and driver.
- Temperature limits differ by CPU model. Choose thresholds using the manufacturer's specifications; the defaults are examples, not universal safety limits.

## Troubleshooting

- **`sensors` not found:** install `lm-sensors`, activate your virtual environment if needed, and ensure the executable is on PATH.
- **No readings:** run `sensors` manually, check `/sys/class/hwmon`, kernel modules, and permissions.
- **Only package temperature:** some platforms do not expose individual core sensors.
- **No throttle counters:** this is normal on drivers that do not publish the Linux sysfs counters.

## Safety

Read-only monitoring only. The program does not alter fan speeds, voltage, clocks, power limits, or shutdown settings. Do not rely on a single generic temperature threshold as a substitute for hardware-specific thermal guidance.
