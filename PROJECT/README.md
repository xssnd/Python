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

## Webhook-to-System-Command Bridge

A minimal internal CI/CD webhook server that verifies HMAC-SHA256 signatures, timestamp freshness, and one-time nonces before dispatching allowlisted actions. Payloads cannot specify arbitrary commands or shell text.

- [Project documentation and security setup](webhook_to_system_command_bridge/README.md)
- [Example configuration](webhook_to_system_command_bridge/config.example.json)
- [Server](webhook_to_system_command_bridge/webhook_bridge.py)

## SMB/NFS Share Permission Auditor

A read-only mounted-share scanner that flags world-writable permissions, exact 777 modes, sensitive-looking world-readable files, group-writable sensitive files, and visible ACL entries (when `getfacl` is available). Includes text, JSON, and CSV reports.


- [Documentation](smb_nfs_share_permission_auditor/README.md)
- [Auditor script](smb_nfs_share_permission_auditor/auditor.py)
