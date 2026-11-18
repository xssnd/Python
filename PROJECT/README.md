# Python Projects

## CPU & Memory Usage Alert

A Python utility that monitors CPU and RAM utilization and sends threshold alerts through Telegram, Discord, and/or SMTP email.

- [Project documentation and installation](cpu_memory_usage_alert/README.md)
- [Example configuration](cpu_memory_usage_alert/config.example.json)
- [Main monitor](cpu_memory_usage_alert/monitor.py)

## Thermal & Core Temp Monitor

A Linux-first CPU temperature monitor using `lm-sensors`, with a live CLI dashboard, overheating alerts, JSON output, and optional Telegram/Discord notifications.

- [Project documentation and installation](thermal_core_temp_monitor/README.md)
- [Example configuration](thermal_core_temp_monitor/config.example.json)
- [Main monitor](thermal_core_temp_monitor/monitor.py)

## Disk Space Monitor

A cross-platform Python utility that monitors mounted partitions and alerts when free disk space reaches 10% or less.

- [Project documentation and installation](disk_space_monitor/README.md)
- [Example configuration](disk_space_monitor/config.example.json)
- [Main monitor](disk_space_monitor/monitor.py)

## Process Watcher

A configurable Python process supervisor that detects stopped critical processes and runs user-defined restart commands with retry limits, cooldowns, and notifications.

- [Project documentation and installation](process_watcher/README.md)
- [Example configuration](process_watcher/config.example.json)
- [Main watcher](process_watcher/monitor.py)

## Top Resource Consumers

A read-only, cross-platform CLI that ranks processes by CPU and RAM usage, with live monitoring and JSON/CSV export.

- [Project documentation and installation](top_resource_consumers/README.md)
- [Dependencies](top_resource_consumers/requirements.txt)
- [Main monitor](top_resource_consumers/monitor.py)

## Uptime Logger

A Python utility that records local host uptime and remote HTTP/TCP availability to CSV, calculates sample-based availability, and sends outage/recovery notifications.

- [Project documentation and installation](uptime_logger/README.md)
- [Example configuration](uptime_logger/config.example.json)
- [Main monitor](uptime_logger/monitor.py)

## Zombie Process Cleaner

A Linux-first utility that detects zombie processes, identifies their parent processes, and optionally sends a confirmed SIGCHLD signal. Read-only by default, with live monitoring and JSON/CSV reports.

- [Project documentation and installation](zombie_process_cleaner/README.md)
- [Dependencies](zombie_process_cleaner/requirements.txt)
- [Main monitor](zombie_process_cleaner/monitor.py)
