# Thermal & Core Temp Monitor

A lightweight Python utility that reports CPU temperature sensors and watches for signs of thermal throttling.

## Features

- Reads Linux `hwmon` sensor channels and labels (often per-core or per-package, depending on motherboard/CPU driver).
- Uses `psutil.sensors_temperatures()` as an additional/fallback sensor source.
- Reads Linux kernel thermal-throttle counters when exposed by the CPU driver (`core_throttle_count` and `package_throttle_count`).
- Configurable warning/critical temperature thresholds, consecutive critical samples, alert cooldown, and log file.
- Optional Telegram and Discord notifications.
- One-shot mode for scripts and scheduled checks; graceful Ctrl+C/SIGTERM shutdown.

## Important hardware/OS notes

Temperature and throttling telemetry is hardware- and driver-dependent. This tool does **not** claim every reported channel is an individual CPU core: labels are passed through from the kernel/driver. Many systems expose only package temperature, and Windows/macOS commonly do not expose the Linux sysfs counters. On those systems the script reports available sensors and explicitly marks throttle counters unavailable.

An increasing Linux thermal-throttle counter is direct evidence that the kernel/CPU driver recorded a throttle event. A high temperature alone is only a risk indicator, not proof of throttling. Some Intel/AMD platforms do not expose these counters through sysfs; absence is not proof that throttling never occurred.

On Linux, sensor visibility may require suitable kernel drivers and permissions. Install/configure `lm-sensors` where appropriate (for example, `sudo sensors-detect`), then verify with `sensors` and `/sys/class/hwmon`.

## Requirements

- Python 3.10+
- Linux recommended for per-channel hwmon and kernel throttle counters
- `psutil` (optional at runtime for additional temperature backends)

## Installation

```bash
cd PROJECT/thermal_core_temp_monitor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
```

Windows PowerShell activation: `.venv\\Scripts\\Activate.ps1`. Sensor availability on Windows depends on platform support exposed to psutil; Linux-specific throttle counters are unavailable there.

## Configuration

Edit `config.json`:

| Setting | Default | Description |
|---|---:|---|
| `interval_seconds` | 5 | Sampling interval |
| `warning_celsius` | 80 | Warning temperature |
| `critical_celsius` | 90 | Critical temperature |
| `consecutive_samples` | 2 | Consecutive critical samples before temperature alert |
| `cooldown_seconds` | 300 | Minimum time between alerts |
| `log_file` | thermal_monitor.log | Log destination |

Set `alerts.telegram.enabled` or `alerts.discord.enabled` to true to enable notifications. Prefer environment variables for secrets:

```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

Do not commit `config.json`, tokens, or webhook URLs.

## Usage

```bash
python monitor.py
python monitor.py --once
python monitor.py --config /path/to/config.json
```

The report prints every detected sensor, its source, temperature, and available throttle counters. An alert is raised when a critical temperature persists for the configured number of samples, or when a throttle counter increases. Warning temperature is included in the alert message; it is not by itself treated as confirmed throttling.

## Troubleshooting

- **No temperatures:** check `sensors`, `/sys/class/hwmon`, kernel drivers, and permissions. Virtual machines may not expose host sensors.
- **Only package temperature appears:** this is a hardware/driver limitation; the program cannot manufacture per-core readings.
- **No throttle counters:** check whether `/sys/devices/system/cpu/cpu*/thermal_throttle/` exists. Counter availability varies by CPU vendor, kernel, and driver.
- **False alerts:** adjust thresholds for the CPU model and workload; vendor thermal limits differ.

## Safety

This is a monitoring tool, not a cooling controller. It does not change fan speeds, clock frequencies, voltage, or power limits. Treat temperature thresholds as configurable guidance and consult the CPU manufacturer's specifications for the exact thermal limits.
