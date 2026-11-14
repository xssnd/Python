"""Optional notification transports for Disk Space Monitor."""
from __future__ import annotations

import json
import smtplib
import urllib.parse
import urllib.request
from email.message import EmailMessage


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token, self.chat_id = bot_token, chat_id

    def send(self, message: str) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = urllib.parse.urlencode({"chat_id": self.chat_id, "text": message}).encode()
        request = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status >= 300:
                raise RuntimeError(f"Telegram returned HTTP {response.status}")


class DiscordNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, message: str) -> None:
        payload = json.dumps({"content": message[:1900]}).encode()
        request = urllib.request.Request(
            self.webhook_url, data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status >= 300:
                raise RuntimeError(f"Discord returned HTTP {response.status}")


class EmailNotifier:
    def __init__(self, settings: dict):
        self.settings = settings

    def send(self, message: str) -> None:
        cfg = self.settings
        mail = EmailMessage()
        mail["Subject"] = "Disk Space Monitor Alert"
        mail["From"] = cfg["sender"]
        mail["To"] = cfg["recipient"]
        mail.set_content(message)
        with smtplib.SMTP(cfg["smtp_host"], int(cfg.get("smtp_port", 587)), timeout=20) as smtp:
            smtp.ehlo()
            if cfg.get("starttls", True):
                smtp.starttls()
                smtp.ehlo()
            if cfg.get("username"):
                smtp.login(cfg["username"], cfg.get("password", ""))
            smtp.send_message(mail)


def build_notifiers(settings: dict) -> list:
    result = []
    telegram = settings.get("telegram", {})
    if telegram.get("bot_token") and telegram.get("chat_id"):
        result.append(TelegramNotifier(telegram["bot_token"], telegram["chat_id"]))
    discord = settings.get("discord", {})
    if discord.get("webhook_url"):
        result.append(DiscordNotifier(discord["webhook_url"]))
    email = settings.get("email", {})
    required = ("smtp_host", "sender", "recipient")
    if all(email.get(key) for key in required):
        result.append(EmailNotifier(email))
    return result
