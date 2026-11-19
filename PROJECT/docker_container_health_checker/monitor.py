#!/usr/bin/env python3
"""Monitor Docker container health and safely restart unhealthy containers."""
import argparse
import json
import logging
import shutil
import signal
import subprocess
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

LOG = logging.getLogger("docker_health_checker")
STOP = False


def load_config(path):
    with open(path, encoding="utf-8") as stream:
        config = json.load(stream)
    settings = config.setdefault("settings", {})
    defaults = {
        "interval_seconds": 15,
        "auto_restart": True,
        "restart_cooldown_seconds": 120,
        "max_restart_attempts": 3,
        "retry_window_seconds": 900,
        "restart_timeout_seconds": 30,
        "log_file": "docker_health_checker.log",
    }
    for key, value in defaults.items():
        settings.setdefault(key, value)
    for key in ("interval_seconds", "max_restart_attempts", "retry_window_seconds",
                "restart_timeout_seconds"):
        if not isinstance(settings[key], int) or isinstance(settings[key], bool) or settings[key] < 1:
            raise ValueError(f"settings.{key} must be a positive integer")
    for key in ("restart_cooldown_seconds",):
        if not isinstance(settings[key], int) or isinstance(settings[key], bool) or settings[key] < 0:
            raise ValueError(f"settings.{key} must be a non-negative integer")
    if not isinstance(settings["auto_restart"], bool):
        raise ValueError("settings.auto_restart must be true or false")
    for key in ("include_containers", "exclude_containers"):
        if not isinstance(settings.get(key, []), list) or not all(
                isinstance(x, str) and x.strip() for x in settings.get(key, [])):
            raise ValueError(f"settings.{key} must be a list of container names or IDs")
    settings.setdefault("include_containers", [])
    settings.setdefault("exclude_containers", [])
    overrides = config.setdefault("containers", [])
    if not isinstance(overrides, list):
        raise ValueError("'containers' must be a list")
    for item in overrides:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
            raise ValueError("Each containers entry needs a non-empty name")
        if "auto_restart" in item and not isinstance(item["auto_restart"], bool):
            raise ValueError("containers[].auto_restart must be boolean")
    return config


def docker_command(args, timeout=20):
    if not shutil.which("docker"):
        raise RuntimeError("Docker CLI not found. Install Docker and ensure it is in PATH.")
    try:
        result = subprocess.run(["docker"] + args, capture_output=True, text=True,
                                timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Docker command timed out: docker {' '.join(args)}") from exc
    except OSError as exc:
        raise RuntimeError(f"Unable to execute Docker CLI: {exc}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or "unknown Docker error").strip()
        raise RuntimeError(detail)
    return result.stdout


def fetch_containers():
    raw = docker_command(["ps", "-aq"])
    ids = [line.strip() for line in raw.splitlines() if line.strip()]
    if not ids:
        return []
    data = json.loads(docker_command(["inspect"] + ids, timeout=60))
    result = []
    for item in data:
        state = item.get("State") or {}
        health = state.get("Health") or {}
        config = item.get("Config") or {}
        result.append({
            "id": item.get("Id", "")[:12],
            "full_id": item.get("Id", ""),
            "name": (item.get("Name") or "").lstrip("/"),
            "image": config.get("Image", ""),
            "status": state.get("Status", "unknown"),
            "health": health.get("Status", "no-healthcheck"),
            "healthcheck": config.get("Healthcheck") is not None,
            "restarts": item.get("RestartCount", 0),
            "started_at": state.get("StartedAt", ""),
            "health_log": (health.get("Log") or [])[-1:] ,
        })
    return result


def filter_containers(containers, settings):
    include = set(settings.get("include_containers", []))
    exclude = set(settings.get("exclude_containers", []))
    selected = []
    for item in containers:
        names = {item["name"], item["id"], item["full_id"]}
        if include and not names.intersection(include):
            continue
        if names.intersection(exclude):
            continue
        selected.append(item)
    return selected


class HealthChecker:
    def __init__(self, config, dry_run=False):
        self.config = config
        self.settings = config["settings"]
        self.dry_run = dry_run
        self.attempts = defaultdict(deque)
        self.last_restart = {}
        self.overrides = {x["name"]: x for x in config.get("containers", [])}

    def restart_allowed(self, item, now):
        name = item["name"]
        history = self.attempts[name]
        window = self.settings["retry_window_seconds"]
        while history and now - history[0] > window:
            history.popleft()
        if len(history) >= self.settings["max_restart_attempts"]:
            return False, "restart limit reached"
        cooldown = self.settings["restart_cooldown_seconds"]
        if now - self.last_restart.get(name, 0) < cooldown:
            return False, f"cooldown ({int(cooldown - (now - self.last_restart[name]))}s remaining)"
        return True, "allowed"

    def check(self, containers, now=None):
        now = time.time() if now is None else now
        rows = []
        for item in containers:
            status = item["health"]
            action = "none"
            detail = ""
            override = self.overrides.get(item["name"], {})
            auto_restart = override.get("auto_restart", self.settings["auto_restart"])
            if status == "unhealthy" and item["status"] == "running":
                if not auto_restart:
                    action = "alert-only"
                else:
                    allowed, detail = self.restart_allowed(item, now)
                    if not allowed:
                        action = "blocked"
                    elif self.dry_run:
                        action = "dry-run"
                        detail = "would restart"
                    else:
                        try:
                            docker_command(["restart", "--time",
                                            str(self.settings["restart_timeout_seconds"]),
                                            item["full_id"]], timeout=self.settings["restart_timeout_seconds"] + 15)
                            self.attempts[item["name"]].append(now)
                            self.last_restart[item["name"]] = now
                            action = "restart-requested"
                            detail = "health will be verified on the next poll"
                            LOG.warning("Restart requested for unhealthy container %s", item["name"])
                        except RuntimeError as exc:
                            self.attempts[item["name"]].append(now)
                            self.last_restart[item["name"]] = now
                            action = "restart-failed"
                            detail = str(exc)
                            LOG.error("Restart failed for %s: %s", item["name"], exc)
            elif status == "unhealthy":
                action, detail = "not-running", "container is not running"
            elif status == "starting":
                action = "warming-up"
            elif status == "no-healthcheck":
                action = "not-configured"
            rows.append({**item, "action": action, "detail": detail})
        return rows


def render(rows, plain=False):
    counts = defaultdict(int)
    for row in rows:
        counts[row["health"]] += 1
    if not plain:
        try:
            from rich.console import Console
            from rich.table import Table
            from rich.panel import Panel
            console = Console()
            table = Table(title="Docker Container Health", expand=True)
            for heading in ("CONTAINER", "ID", "STATE", "HEALTH", "RESTARTS", "ACTION"):
                table.add_column(heading, overflow="fold")
            for row in rows:
                health = row["health"]
                style = "red" if health == "unhealthy" else "green" if health == "healthy" else "yellow"
                table.add_row(row["name"], row["id"], row["status"],
                              f"[{style}]{health}[/{style}]", str(row["restarts"]),
                              row["action"] + (": " + row["detail"] if row["detail"] else ""))
            console.print(table)
            console.print(Panel(
                f"Total: {len(rows)}  |  Healthy: {counts['healthy']}  |  "
                f"Unhealthy: {counts['unhealthy']}  |  Starting: {counts['starting']}  |  "
                f"No healthcheck: {counts['no-healthcheck']}",
                title="Summary"))
            return
        except ImportError:
            pass
    print(f"{'CONTAINER':24} {'STATE':12} {'HEALTH':16} {'RESTARTS':8} ACTION")
    print("-" * 100)
    for row in rows:
        action = row["action"] + (": " + row["detail"] if row["detail"] else "")
        print(f"{row['name'][:24]:24} {row['status'][:12]:12} {row['health'][:16]:16} "
              f"{row['restarts']:<8} {action}")
    print(f"Total: {len(rows)} | Healthy: {counts['healthy']} | "
          f"Unhealthy: {counts['unhealthy']} | Starting: {counts['starting']} | "
          f"No healthcheck: {counts['no-healthcheck']}")


def main():
    parser = argparse.ArgumentParser(description="Monitor Docker healthchecks and restart unhealthy containers.")
    parser.add_argument("--config", default="config.json", help="Path to JSON configuration")
    parser.add_argument("--once", action="store_true", help="Run one health check and exit")
    parser.add_argument("--dry-run", action="store_true", help="Show restart actions without restarting containers")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--plain", action="store_true", help="Disable Rich terminal UI")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    handlers = [logging.StreamHandler(sys.stderr)]
    if config["settings"].get("log_file"):
        handlers.append(logging.FileHandler(config["settings"]["log_file"], encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=handlers, force=True)

    checker = HealthChecker(config, dry_run=args.dry_run)
    def stop_handler(_signum, _frame):
        global STOP
        STOP = True
    signal.signal(signal.SIGINT, stop_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop_handler)

    while not STOP:
        try:
            containers = filter_containers(fetch_containers(), config["settings"])
            rows = checker.check(containers)
            if args.json:
                print(json.dumps(rows, indent=2))
            else:
                render(rows, plain=args.plain)
            if any(row["health"] == "unhealthy" for row in rows):
                LOG.warning("One or more containers are unhealthy")
        except (RuntimeError, json.JSONDecodeError) as exc:
            LOG.error("Health check failed: %s", exc)
            if args.once:
                return 1
        if args.once:
            break
        deadline = time.monotonic() + config["settings"]["interval_seconds"]
        while not STOP and time.monotonic() < deadline:
            time.sleep(min(1, max(0, deadline - time.monotonic())))
    LOG.info("Docker Container Health Checker stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
