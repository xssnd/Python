# Docker Container Health Checker

A Python CLI utility that monitors Docker container healthcheck states and can automatically restart containers reported as `unhealthy`.

## Features

- Discover all Docker containers, including stopped containers, using the Docker CLI.
- Read container state, Docker Health status, image, ID, restart count, and latest healthcheck log entry.
- Automatically restart running containers in the `unhealthy` state.
- Restart cooldown, rolling retry window, and maximum restart attempts to reduce restart loops.
- Per-container auto-restart overrides and include/exclude filters.
- Dry-run mode, one-shot checks, continuous monitoring, and graceful shutdown.
- Rich terminal dashboard with a plain-text fallback.
- JSON output for automation and logging to console/file.
- No Docker SDK dependency; communicates through the installed Docker CLI.

## Requirements

- Python 3.9+
- Docker Engine or Docker Desktop, with the Docker CLI available in `PATH`.
- Permission to access the Docker daemon (for example, membership in the `docker` group on Linux, or an appropriately configured Docker context).
- Optional: Rich for the enhanced terminal UI.

## Installation

```bash
cd PROJECT/docker_container_health_checker
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
cp config.example.json config.json
```

Edit `config.json` before enabling automatic restarts. The example includes a restart-enabled API and an alert/monitor-only database.

## Usage

```bash
# One-time inventory and health check
python monitor.py --config config.json --once

# Continuous monitoring (uses config interval)
python monitor.py --config config.json

# Preview restart decisions without changing containers
python monitor.py --config config.json --dry-run

# Machine-readable output
python monitor.py --config config.json --once --json

# Plain terminal output
python monitor.py --config config.json --plain
```

## Configuration

| Setting | Default | Description |
|---|---:|---|
| interval_seconds | 15 | Poll interval |
| auto_restart | true | Restart eligible unhealthy containers |
| restart_cooldown_seconds | 120 | Minimum time between restart attempts per container |
| max_restart_attempts | 3 | Maximum attempts in the rolling retry window |
| retry_window_seconds | 900 | Rolling window used for the restart limit |
| restart_timeout_seconds | 30 | Docker restart grace period |
| include_containers | [] | Optional allowlist of container names or IDs; empty means all |
| exclude_containers | [] | Container names or IDs to ignore |
| log_file | docker_health_checker.log | Log destination; set to an empty string to disable file logging |

Use the `containers` array to override `auto_restart` for a specific container by exact name:

```json
{
  "containers": [
    {"name": "web", "auto_restart": true},
    {"name": "database", "auto_restart": false}
  ]
}
```

## Docker healthcheck requirement

Docker reports `healthy`, `unhealthy`, or `starting` only when an image/container defines a HEALTHCHECK. Containers without one are shown as `no-healthcheck` and are never restarted by this tool. Add a healthcheck to your Dockerfile or Compose service, for example:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \\
  CMD curl -fsS http://127.0.0.1:8080/health || exit 1
```

For Docker Compose, configure the service's `healthcheck:` section and recreate the container so the healthcheck is applied.

## Safety and operational notes

- Restarting containers is a disruptive action. Start with `--dry-run`, then explicitly enable `auto_restart` only for services that are safe to restart automatically.
- The tool restarts only containers that are both running and explicitly reported as `unhealthy`; it does not restart stopped, exited, starting, or no-healthcheck containers.
- Restart limits and cooldowns are in-memory and reset when the checker process restarts. Use an external supervisor and persistent monitoring if restart history must survive host reboots.
- Docker restart success means the daemon accepted/completed the restart operation; it does not guarantee the application is healthy. The next poll checks health again.
- Access to the Docker daemon is highly privileged and can effectively grant host-level control. Protect the Docker socket and configuration.
- The tool does not change Docker restart policies, images, networks, volumes, or firewall rules.

## Troubleshooting

- Run `docker info` and `docker ps` as the same user that runs this checker.
- If every container shows `no-healthcheck`, define a Docker HEALTHCHECK.
- Use `--dry-run` to confirm the restart decision before enabling it.
- Inspect `docker inspect CONTAINER` and the container logs when a healthcheck fails.
- Check the configured log file for Docker daemon or permission errors.

## Tests

```bash
python -m unittest discover -s tests -v
```

## License

Use according to the license of the parent repository.
