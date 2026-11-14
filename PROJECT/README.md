# Python Projects

## CPU & Memory Usage Alert

A Python utility that monitors CPU and RAM utilization and sends threshold alerts through Telegram, Discord, and/or SMTP email.

- [Project documentation and installation](cpu_memory_usage_alert/README.md)
- [Example configuration](cpu_memory_usage_alert/config.example.json)
- [Main monitor](cpu_memory_usage_alert/monitor.py)

## Thermal & Core Temp Monitor

A Python utility that reports available CPU temperature channels and detects Linux thermal-throttling events through kernel counters when supported by the hardware and driver.

- [Project documentation and installation](thermal_core_temp_monitor/README.md)
- [Example configuration](thermal_core_temp_monitor/config.example.json)
- [Main monitor](thermal_core_temp_monitor/monitor.py)

## Disk Space Monitor

A cross-platform Python utility that monitors mounted partitions and alerts when free disk space reaches 10% or less.

- [Project documentation and installation](disk_space_monitor/README.md)
- [Example configuration](disk_space_monitor/config.example.json)
- [Main monitor](disk_space_monitor/monitor.py)
