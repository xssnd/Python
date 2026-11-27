# Interactive TUI Service Manager

A cross-platform terminal dashboard for inventorying and controlling **systemd services on Linux** and **Windows Services**. Built with Python and Textual.

## Features

- Auto-detects Linux systemd or Windows Service Control Manager.
- Live service inventory: state, startup mode, service name, description.
- Search/filter table; refresh; keyboard shortcuts.
- Start, stop, restart with a confirmation dialog.
- Optional deny-action list for protected services.
- Export inventory to JSON or CSV.
- Headless CLI list/export/actions for automation (actions require `--yes`).
- Timeout handling, clear backend errors, and no automatic changes.
- Configurable favorite services and deny list (sample included).
- Admin/root status is not required to view inventory; mutation may require elevation.

## Supported platforms

- Linux distributions using systemd (Debian/Ubuntu, Fedora/RHEL, Arch, etc.).
- Windows 10/11 and Windows Server with PowerShell available.
- Other init systems are not currently supported.

## Install

Python 3.10+ recommended.

```bash
cd PROJECT/service_manager_tui
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
# .venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
```

## Run TUI

```bash
python service_manager.py
```

Run elevated if you plan to control services:
- Linux: `sudo python service_manager.py`
- Windows: run PowerShell/Terminal as Administrator.

Keyboard shortcuts: **S** start, **X** stop, **K** restart, **R** refresh, **E** export JSON, **Q** quit. Select a service row first. Search filters the table immediately.

## CLI mode

```bash
# Inventory
python service_manager.py --list

# Export
python service_manager.py --export json --output services.json
python service_manager.py --export csv --output services.csv

# Mutating operations: explicit service and confirmation flag required
sudo python service_manager.py --action restart --service ssh.service --yes
# Windows (Administrator PowerShell)
python service_manager.py --action stop --service Spooler --yes
```

## Configuration

Copy the sample configuration to `~/.config/service_manager_tui/config.json` on Linux/macOS or `%USERPROFILE%\\.config\\service_manager_tui\\config.json` on Windows. Use `--config path/to/config.json`.

- `favorites`: service names for personal quick-reference (currently informational; favorite pinning is planned).
- `deny_actions`: service names for which interactive actions are blocked.
- `refresh_interval_seconds`: reserved for future auto-refresh (manual refresh is currently used).

## Safety

- Inventory is read-only.
- All TUI actions display a confirmation dialog.
- Headless actions require `--yes`.
- Config deny list blocks service actions in the TUI.
- Avoid stopping core OS, network, storage, or security services unless you understand impact.
- Windows actions may need Administrator; Linux actions may need sudo.
- No remote control, privilege escalation, or service enable/disable functionality is included.

## Troubleshooting

- `Textual` missing: install dependencies with pip.
- Linux listing fails: check systemd and permissions.
- Windows listing fails: confirm PowerShell works and service query is permitted.
- Access denied when controlling a service: re-run in an elevated terminal.

## Roadmap

- Auto-refresh and configurable intervals.
- Favorites filter/pinning.
- Service details screen and dependencies.
- Service enable/disable and startup-mode editor with separate safety confirmation.
- Remote host inventory/actions over SSH/WinRM.
- Event log and operation audit history.
- Notifications and alert thresholds.
- Unit tests with mocked platform commands.
