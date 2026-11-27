# Hardware Inventory & Serial Number Harvester

Cross-platform inventory utility for **Linux and Windows**. Collects system identity, motherboard serial/model, BIOS details, CPU, RAM capacity, storage device metadata, and SMART health where supported. Stores snapshots in SQLite and can export CSV or JSON.

> Serial numbers are sensitive asset identifiers. Use `--redact-serials` when sharing output, restrict access to databases, and encrypt backups. The tool is read-only and does not modify firmware, disks, or configuration.

## Features

- Linux and Windows collector, using native sources (Linux DMI/sysfs/lsblk and Windows CIM via PowerShell).
- Motherboard manufacturer, product/model and serial (permissions/platform dependent).
- BIOS/UEFI vendor, version and release date.
- CPU model and physical/logical core counts where available.
- Total installed RAM.
- Storage inventory: model, serial, size, rotational flag and transport; SMART health summary via `smartctl` on Linux if installed.
- SQLite history snapshots with timestamp, host and OS fields; indexed host/time.
- CSV export (spreadsheet-friendly inventory snapshots) and JSON output for automation.
- Periodic collection with `--watch`.
- Serial privacy mode; quiet output; custom database/export paths.
- Graceful fallback when tools, privileges, or hardware fields are unavailable.
- Read-only collection; never attempts to run SMART self-tests or repair operations.

## Requirements

- Python 3.9+
- Optional: `psutil` (improves CPU/RAM detection on Windows and some systems).
- Linux: `lsblk`; optional `smartctl` from smartmontools. Motherboard serial may require root or passwordless sudo for dmidecode fallback.
- Windows: PowerShell with CIM access (normally built-in).

## Installation

```bash
git clone https://github.com/xssnd/Python.git
cd Python/PROJECT/hardware_inventory_serial_harvester
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
git clone https://github.com/xssnd/Python.git
cd Python\PROJECT\hardware_inventory_serial_harvester
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Usage

Basic collection (stores snapshot in default SQLite database):

```bash
python inventory.py
```

Specify database and CSV export:

```bash
python inventory.py --db ./inventory.sqlite3 --csv ./inventory.csv
```

JSON output (useful for automation):

```bash
python inventory.py --json --redact-serials
```

Periodic snapshots every 5 minutes (minimum interval 30 seconds):

```bash
python inventory.py --watch 300 --db ./fleet_inventory.sqlite3
```

Show output without database writes:

```bash
python inventory.py --no-db --quiet --json
```

### CLI options

| Option | Description |
|---|---|
| `--db PATH` | SQLite database path |
| `--csv PATH` | Export this scan as CSV |
| `--redact-serials` | Redact motherboard and disk serials |
| `--json` | Print JSON record |
| `--quiet` | Suppress terminal table |
| `--watch SECONDS` | Repeat scans (minimum 30 seconds) |
| `--no-db` | Do not write SQLite |

Default database: `~/.local/share/hardware_inventory/inventory.sqlite3` (Windows uses the user's home folder as well).

## Data model

Each snapshot contains a timestamp, hostname, OS and architecture, manufacturer/model, motherboard identifiers, BIOS information, CPU details, RAM in bytes, a JSON array of disk metadata, and source/privacy metadata. Each collection is a separate row so changes can be tracked over time.

## SMART limitations

SMART information is best-effort. On Linux, install smartmontools and run with appropriate device access. Some NVMe, USB bridges, RAID controllers, virtual machines, and Windows storage stacks may not expose SMART details. Health text is a summary only—not a full diagnostic and not a guarantee of disk reliability.

## Fleet collection guidance

Run this locally on each endpoint, or distribute through your configuration-management/remote execution system. This release does **not** implement an agent, central server, network discovery, remote credential handling, or automatic fleet aggregation. For central reporting, send CSV/SQLite snapshots to a secured collector and merge them using hostname plus timestamp.

## Security and privacy

- Serial numbers are identifiers and should be treated as confidential.
- Prefer `--redact-serials` for tickets, demos, or public issue reports.
- Protect SQLite and CSV files with restrictive filesystem permissions and encrypted backups.
- Use authorized asset-inventory collection only.

## Troubleshooting

- Missing serials: permissions, BIOS vendor, hypervisor, or platform may hide identifiers.
- Missing SMART status: install `smartmontools`, check device access, and confirm the disk controller exposes SMART.
- Windows fields blank: verify PowerShell/CIM access and run from a supported Windows host.
- No output for unsupported platforms: collector gracefully leaves unavailable fields blank.

## License

Use according to the repository's license.
