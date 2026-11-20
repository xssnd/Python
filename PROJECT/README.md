# Python Projects

## CPU & Memory Usage Alert

A Python utility that monitors CPU and RAM utilization and sends threshold alerts through Telegram, Discord, and/or SMTP email.

- [Project documentation and installation](cpu_memory_usage_alert/README.md)
- [Example configuration](cpu_memory_usage_alert/config.example.json)
- [Main monitor](cpu_memory_usage_alert/monitor.py)

## Thermal & Core Temp Monitor

A Linux-first CPU temperature monitor using lm-sensors, with a live CLI dashboard, overheating alerts, JSON output, and optional Telegram/Discord notifications.

- [Project documentation and installation](thermal_core_temp_monitor/README.md)
- [Example configuration](thermal_core_temp_monitor/config.example.json)
- [Main monitor](thermal_core_temp_monitor/monitor.py)

## Disk Space Monitor

A cross-platform Python utility that monitors mounted partitions and alerts when free disk space reaches 10% or less.

- [Project documentation and installation](disk_space_monitor/README.md)
- [Example configuration](disk_space_monitor/config.example.json)
- [Main monitor](disk_space_monitor/monitor.py)

## Inode Usage Monitor

A Linux-first, read-only CLI that monitors inode consumption across mounted filesystems and detects inode exhaustion independently of disk-space usage.

- [Project documentation and installation](inode_usage_monitor/README.md)
- [Dependencies](inode_usage_monitor/requirements.txt)
- [Main monitor](inode_usage_monitor/monitor.py)

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

## Network Bandwidth Tracker

A cross-platform CLI that monitors RX/TX throughput and cumulative byte counters for selected network interfaces, with a live dashboard, threshold warnings, and CSV/JSONL export.

- [Project documentation and installation](network_bandwidth_tracker/README.md)
- [Dependencies](network_bandwidth_tracker/requirements.txt)
- [Main monitor](network_bandwidth_tracker/monitor.py)

## Open Ports Checker

A read-only CLI that inventories listening TCP sockets and locally bound UDP ports, identifies owning processes where permissions allow, and highlights wildcard-bound sockets.

- [Project documentation and installation](open_ports_checker/README.md)
- [Dependencies](open_ports_checker/requirements.txt)
- [Main monitor](open_ports_checker/monitor.py)

## Docker Container Health Checker

A Docker CLI-based monitor that tracks container Healthcheck states and can safely restart running containers reported as unhealthy, with cooldowns, retry limits, dry-run mode, and JSON output.

- [Project documentation and installation](docker_container_health_checker/README.md)
- [Example configuration](docker_container_health_checker/config.example.json)
- [Main monitor](docker_container_health_checker/monitor.py)
