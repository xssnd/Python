# Python Projects

## Automated S3 / MinIO Backup Rotator & Integrity Verifier

Compresses target directories, encrypts with AES-256-GCM authenticated chunks, uploads to S3-compatible storage, verifies random or all chunks via ranged downloads, and rotates old backups.

- [Documentation and installation](automated_s3_minio_backup_rotator/README.md)
- [Dependencies](automated_s3_minio_backup_rotator/requirements.txt)
- [CLI script](automated_s3_minio_backup_rotator/backup_rotator.py)

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

## Unified Certificate Expiry & SAN Scanner

A read-only TLS certificate auditor for explicitly authorized IPv4/IPv6 subnets. Checks expiry, SAN presence/identity, and trust-chain validation on ports 443, 636, and 8443 by default.

- [Project documentation and installation](unified_certificate_scanner/README.md)
- [Dependencies](unified_certificate_scanner/requirements.txt)
- [Main scanner](unified_certificate_scanner/monitor.py)

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
## Smart Log Anomaly Grepper

A lightweight, local-first log anomaly detector using token rarity, normalized template novelty, and character entropy for Linux text logs and Windows Event Logs.

- [Documentation and installation](smart_log_anomaly_grepper/README.md)
- [Example configuration](smart_log_anomaly_grepper/config.example.json)
- [CLI script](smart_log_anomaly_grepper/grepper.py)

## Zombie Process & Orphaned Port Reaper

Monitor configured processes for high CPU/RAM combined with disk-I/O inactivity; report listener ports and optionally restart allowlisted systemd units.

- [Documentation and usage](zombie_process_orphaned_port_reaper/README.md)
- [Example configuration](zombie_process_orphaned_port_reaper/config.example.json)
- [Dependencies](zombie_process_orphaned_port_reaper/requirements.txt)
- [Main monitor](zombie_process_orphaned_port_reaper/monitor.py)

## Local DNS Sinkhole & Ad/Malware Blocklist Updater

Cross-platform hosts-file updater that aggregates threat-intelligence/ad domain feeds, supports an allowlist, preserves unrelated hosts entries, and creates timestamped backups.

- [Documentation and usage](local_dns_sinkhole_updater/README.md)
- [Example feeds/config](local_dns_sinkhole_updater/feeds.example.json)
- [Updater CLI](local_dns_sinkhole_updater/updater.py)\n\n## Database Connection Pool Exhaustion Monitor

A cross-platform monitor for established TCP connections to PostgreSQL, MySQL, and Microsoft SQL Server, with optional server-side connection counts and configured limits.

- [Documentation and installation](database_connection_pool_exhaustion_monitor/README.md)
- [Example configuration](database_connection_pool_exhaustion_monitor/config.example.json)
- [Optional dependencies](database_connection_pool_exhaustion_monitor/requirements.txt)
- [Main monitor](database_connection_pool_exhaustion_monitor/monitor.py)


## Dynamic Firewall Blacklist Sync

A log-driven IP blocking tool with threshold/window detection, allowlists, dry-run by default, and Linux nftables/iptables plus Windows Defender Firewall backends.

- [Documentation and usage](dynamic_firewall_blacklist_sync/README.md)
- [Example configuration](dynamic_firewall_blacklist_sync/config.example.json)
- [CLI script](dynamic_firewall_blacklist_sync/dynamic_firewall_sync.py)
- [Parser tests](dynamic_firewall_blacklist_sync/tests/test_parser.py)

## Hardware Inventory & Serial Number Harvester

Cross-platform hardware inventory collector for Linux and Windows, including motherboard serial, BIOS/UEFI details, CPU/RAM, disk metadata, optional SMART health, SQLite history, CSV export, JSON output, and periodic scans.

- [Documentation and installation](hardware_inventory_serial_harvester/README.md)
- [Dependencies](hardware_inventory_serial_harvester/requirements.txt)
- [Collector CLI](hardware_inventory_serial_harvester/inventory.py)
