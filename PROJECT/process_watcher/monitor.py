#!/usr/bin/env python3
"""Configurable critical-process watcher with bounded automatic restarts."""
import argparse
import json
import logging
import os
import signal
import smtplib
import subprocess
import sys
import time
import urllib.request
from email.message import EmailMessage
from pathlib import Path

import psutil

LOG = logging.getLogger("process_watcher")
STOP = False


def load_config(path):
    with open(path, encoding="utf-8") as stream:
        config = json.load(stream)
    settings = config.setdefault("settings", {})
    settings["interval_seconds"] = max(2, int(settings.get("interval_seconds", 10)))
    settings["restart_cooldown_seconds"] = max(0, int(settings.get("restart_cooldown_seconds", 60)))
    settings["max_restart_attempts"] = max(1, int(settings.get("max_restart_attempts", 3)))
    settings["retry_window_seconds"] = max(1, int(settings.get("retry_window_seconds", 300)))
    if not isinstance(config.get("processes", []), list):
        raise ValueError("'processes' must be a list")
    for item in config.get("processes", []):
        if not item.get("name") or not isinstance(item.get("match"), list) or not item["match"]:
            raise ValueError("Every process needs a name and a non-empty match list")
        command = item.get("restart_command", [])
        if not isinstance(command, list) or not all(isinstance(arg, str) for arg in command):
            raise ValueError("restart_command must be a list of strings")
    return config


def process_is_running(match):
    names = {value.lower() for value in match}
    for proc in psutil.process_iter(["name", "exe", "cmdline"]):
        try:
            info = proc.info
            candidates = {str(info.get("name") or "").lower(),
                          Path(str(info.get("exe") or "")).name.lower()}
            command_line = " ".join(info.get("cmdline") or []).lower()
            if names.intersection(candidates) or any(value.lower() in command_line for value in match):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
            continue
    return False


def notify(config, subject, message):
    channels = config.get("notifications", {})
    telegram = channels.get("telegram", {})
    token = os.getenv("PW_TELEGRAM_BOT_TOKEN", telegram.get("bot_token", ""))
    chat = os.getenv("PW_TELEGRAM_CHAT_ID", telegram.get("chat_id", ""))
    if token and chat:
        try:
            payload = json.dumps({"chat_id": chat, "text": subject + "\n" + message}).encode()
            request = urllib.request.Request(
                "https://api.telegram.org/bot" + token + "/sendMessage", data=payload,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request, timeout=10):
                pass
        except Exception:
            LOG.exception("Telegram notification failed")

    discord = channels.get("discord", {})
    webhook = os.getenv("PW_DISCORD_WEBHOOK_URL", discord.get("webhook_url", ""))
    if webhook:
        try:
            payload = json.dumps({"content": "**" + subject + "**\n" + message}).encode()
            request = urllib.request.Request(webhook, data=payload,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request, timeout=10):
                pass
        except Exception:
            LOG.exception("Discord notification failed")

    email = channels.get("email", {})
    host = os.getenv("PW_SMTP_HOST", email.get("host", ""))
    recipient = os.getenv("PW_EMAIL_TO", email.get("to", ""))
    if host and recipient:
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = os.getenv("PW_EMAIL_FROM", email.get("from", email.get("username", "")))
            msg["To"] = recipient
            msg.set_content(message)
            port = int(os.getenv("PW_SMTP_PORT", email.get("port", 587)))
            username = os.getenv("PW_SMTP_USERNAME", email.get("username", ""))
            password = os.getenv("PW_SMTP_PASSWORD", email.get("password", ""))
            with smtplib.SMTP(host, port, timeout=15) as smtp:
                smtp.starttls()
                if username:
                    smtp.login(username, password)
                smtp.send_message(msg)
        except Exception:
            LOG.exception("Email notification failed")


class Watcher:
    def __init__(self, config):
        self.config = config
        self.settings = config["settings"]
        self.state = {item["name"]: {"attempts": [], "last_restart": 0.0, "was_running": None}
                      for item in config.get("processes", [])}

    def check(self, item, now=None):
        now = time.time() if now is None else now
        name = item["name"]
        state = self.state[name]
        if process_is_running(item["match"]):
            if state["was_running"] is False:
                LOG.info("%s recovered", name)
                if self.settings.get("recovery_notifications", True):
                    notify(self.config, "RECOVERED: " + name, "The process is running again.")
            state["was_running"] = True
            return "running"

        LOG.warning("%s is not running", name)
        if state["was_running"] is not False:
            notify(self.config, "DOWN: " + name, "Critical process was not found.")
        state["was_running"] = False
        command = item.get("restart_command", [])
        if not command:
            LOG.error("%s has no restart command; alert-only mode", name)
            return "down-no-command"

        cooldown = self.settings["restart_cooldown_seconds"]
        if now - state["last_restart"] < cooldown:
            return "cooldown"
        window = self.settings["retry_window_seconds"]
        state["attempts"] = [stamp for stamp in state["attempts"] if now - stamp <= window]
        if len(state["attempts"]) >= self.settings["max_restart_attempts"]:
            LOG.error("%s reached restart limit", name)
            return "restart-limit"

        timeout = max(1, int(item.get("restart_timeout_seconds", 30)))
        LOG.warning("Executing restart command for %s: %s", name, command)
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False, shell=False)
            state["last_restart"] = now
            state["attempts"].append(now)
            if result.returncode == 0:
                LOG.info("Restart command for %s completed; verifying next poll", name)
                notify(self.config, "RESTART COMMAND OK: " + name,
                       "Command completed. Process recovery will be checked on the next poll.")
                return "restart-command-ok"
            detail = (result.stderr or result.stdout or "No command output").strip()[-1000:]
            LOG.error("Restart failed for %s (exit %s): %s", name, result.returncode, detail)
            notify(self.config, "RESTART FAILED: " + name, detail)
            return "restart-failed"
        except (OSError, subprocess.TimeoutExpired) as exc:
            state["last_restart"] = now
            state["attempts"].append(now)
            LOG.exception("Restart command error for %s", name)
            notify(self.config, "RESTART ERROR: " + name, str(exc))
            return "restart-error"


def main():
    parser = argparse.ArgumentParser(description="Watch critical processes and restart them when configured.")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--once", action="store_true", help="Check once and exit")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("Configuration error: " + str(exc), file=sys.stderr)
        return 2

    handlers = [logging.StreamHandler()]
    if config["settings"].get("log_file"):
        handlers.append(logging.FileHandler(config["settings"]["log_file"], encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=handlers, force=True)
    watcher = Watcher(config)

    def stop_handler(_signum, _frame):
        global STOP
        STOP = True

    signal.signal(signal.SIGINT, stop_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop_handler)

    if args.once:
        for item in config.get("processes", []):
            watcher.check(item)
        return 0

    LOG.info("Process Watcher started: %d process(es)", len(config.get("processes", [])))
    while not STOP:
        for item in config.get("processes", []):
            if STOP:
                break
            watcher.check(item)
        deadline = time.monotonic() + config["settings"]["interval_seconds"]
        while not STOP and time.monotonic() < deadline:
            time.sleep(min(1, max(0, deadline - time.monotonic())))
    LOG.info("Process Watcher stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
