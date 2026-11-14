#!/usr/bin/env python3
"""CPU and memory usage monitor with configurable notification channels."""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

from notifiers import EmailNotifier, MultiNotifier, TelegramNotifier, DiscordNotifier


@dataclass
class Settings:
    interval_seconds: int = 10
    cpu_threshold: float = 85.0
    memory_threshold: float = 85.0
    cooldown_seconds: int = 300
    consecutive_breaches: int = 2
    recovery_notifications: bool = True
    log_file: str = "cpu_memory_alert.log"


class AlertMonitor:
    def __init__(self, config: dict[str, Any], once: bool = False) -> None:
        monitor_cfg = config.get("monitor", {})
        self.settings = Settings(
            interval_seconds=max(1, int(monitor_cfg.get("interval_seconds", 10))),
            cpu_threshold=float(monitor_cfg.get("cpu_threshold", 85)),
            memory_threshold=float(monitor_cfg.get("memory_threshold", 85)),
            cooldown_seconds=max(0, int(monitor_cfg.get("cooldown_seconds", 300))),
            consecutive_breaches=max(1, int(monitor_cfg.get("consecutive_breaches", 2))),
            recovery_notifications=bool(monitor_cfg.get("recovery_notifications", True)),
            log_file=str(monitor_cfg.get("log_file", "cpu_memory_alert.log")),
        )
        for name, value in (("cpu_threshold", self.settings.cpu_threshold),
                            ("memory_threshold", self.settings.memory_threshold)):
            if not 0 < value <= 100:
                raise ValueError(f"{name} must be greater than 0 and at most 100")
        self.notifier = MultiNotifier(self._build_notifiers(config.get("notifications", {})))
        self.once = once
        self.running = True
        self._breach_counts = {"cpu": 0, "memory": 0}
        self._active_alerts: set[str] = set()
        self._last_sent: dict[str, float] = {}

    @staticmethod
    def _build_notifiers(cfg: dict[str, Any]):
        result = []
        telegram = cfg.get("telegram", {})
        token = os.getenv("TELEGRAM_BOT_TOKEN", telegram.get("bot_token", ""))
        chat_id = os.getenv("TELEGRAM_CHAT_ID", telegram.get("chat_id", ""))
        if telegram.get("enabled") and token and chat_id:
            result.append(TelegramNotifier(token, chat_id))

        discord = cfg.get("discord", {})
        webhook = os.getenv("DISCORD_WEBHOOK_URL", discord.get("webhook_url", ""))
        if discord.get("enabled") and webhook:
            result.append(DiscordNotifier(webhook))

        email = cfg.get("email", {})
        password = os.getenv("SMTP_PASSWORD", email.get("password", ""))
        if email.get("enabled") and password:
            result.append(EmailNotifier(
                host=email.get("smtp_host", "smtp.gmail.com"),
                port=int(email.get("smtp_port", 587)),
                username=email.get("username", ""),
                password=password,
                sender=email.get("sender", email.get("username", "")),
                recipients=email.get("recipients", []),
                use_tls=bool(email.get("use_tls", True)),
            ))
        return result

    def stop(self, *_: object) -> None:
        self.running = False
        logging.info("Shutdown requested; stopping monitor...")

    def sample(self) -> dict[str, float]:
        return {
            "cpu": psutil.cpu_percent(interval=1),
            "memory": psutil.virtual_memory().percent,
        }

    def _notify(self, key: str, subject: str, message: str, force: bool = False) -> None:
        now = time.monotonic()
        last = self._last_sent.get(key, 0)
        if not force and now - last < self.settings.cooldown_seconds:
            return
        self.notifier.send(subject, message)
        self._last_sent[key] = now

    def process_sample(self, values: dict[str, float]) -> None:
        labels = {"cpu": "CPU", "memory": "Memory"}
        thresholds = {
            "cpu": self.settings.cpu_threshold,
            "memory": self.settings.memory_threshold,
        }
        for key, value in values.items():
            breached = value >= thresholds[key]
            self._breach_counts[key] = self._breach_counts[key] + 1 if breached else 0
            if breached and self._breach_counts[key] >= self.settings.consecutive_breaches:
                if key not in self._active_alerts:
                    self._active_alerts.add(key)
                    logging.warning("%s usage high: %.1f%% (limit %.1f%%)",
                                    labels[key], value, thresholds[key])
                    self._notify(
                        key,
                        f"🚨 {labels[key]} usage alert",
                        f"{labels[key]} usage is {value:.1f}% (threshold: {thresholds[key]:.1f}%).",
                    )
                else:
                    self._notify(
                        key,
                        f"🚨 {labels[key]} usage still high",
                        f"{labels[key]} usage remains at {value:.1f}% (threshold: {thresholds[key]:.1f}%).",
                    )
            elif not breached and key in self._active_alerts:
                self._active_alerts.remove(key)
                logging.info("%s usage recovered: %.1f%%", labels[key], value)
                if self.settings.recovery_notifications:
                    self._notify(
                        f"{key}_recovery",
                        f"✅ {labels[key]} usage recovered",
                        f"{labels[key]} usage is back to {value:.1f}% (threshold: {thresholds[key]:.1f}%).",
                        force=True,
                    )

    def run(self) -> None:
        logging.info("Monitoring started | CPU >= %.1f%% | RAM >= %.1f%% | interval %ss",
                     self.settings.cpu_threshold, self.settings.memory_threshold,
                     self.settings.interval_seconds)
        psutil.cpu_percent(interval=None)  # prime CPU counters
        while self.running:
            started = time.monotonic()
            try:
                values = self.sample()
                logging.info("CPU: %5.1f%% | RAM: %5.1f%%", values["cpu"], values["memory"])
                self.process_sample(values)
            except Exception:
                logging.exception("Monitoring iteration failed")
            if self.once:
                break
            elapsed = time.monotonic() - started
            self._wait(max(0, self.settings.interval_seconds - elapsed))

    def _wait(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while self.running and time.monotonic() < end:
            time.sleep(min(0.5, end - time.monotonic()))


def load_config(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Configuration root must be a JSON object")
    return data


def configure_logging(log_file: str) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file, encoding="utf-8")],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="CPU & Memory Usage Alert")
    parser.add_argument("-c", "--config", default="config.json", help="JSON config file")
    parser.add_argument("--once", action="store_true", help="Collect one sample and exit")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        monitor_cfg = config.get("monitor", {})
        configure_logging(str(monitor_cfg.get("log_file", "cpu_memory_alert.log")))
        monitor = AlertMonitor(config, once=args.once)
        signal.signal(signal.SIGINT, monitor.stop)
        signal.signal(signal.SIGTERM, monitor.stop)
        monitor.run()
        return 0
    except FileNotFoundError:
        print(f"Config file not found: {args.config}. Copy config.example.json to config.json.",
              file=sys.stderr)
        return 2
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
