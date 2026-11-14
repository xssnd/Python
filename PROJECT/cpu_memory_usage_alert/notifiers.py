"""Notification backends. Missing or failed channels never stop metric collection."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from urllib.error import URLError
from urllib.request import Request, urlopen


class BaseNotifier:
    def send(self, subject: str, message: str) -> bool:
        raise NotImplementedError


class TelegramNotifier(BaseNotifier):
    def __init__(self, token: str, chat_id: str) -> None:
        self.token, self.chat_id = token, str(chat_id)

    def send(self, subject: str, message: str) -> bool:
        import json
        import urllib.parse
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = urllib.parse.urlencode({
            "chat_id": self.chat_id, "text": f"{subject}\n{message}"
        }).encode()
        try:
            with urlopen(Request(url, data=payload), timeout=15) as response:
                return 200 <= response.status < 300
        except (URLError, TimeoutError, OSError) as exc:
            logging.error("Telegram notification failed: %s", exc)
            return False


class DiscordNotifier(BaseNotifier):
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(self, subject: str, message: str) -> bool:
        import json
        payload = json.dumps({"content": f"**{subject}**\n{message}"}).encode()
        try:
            with urlopen(Request(self.webhook_url, data=payload,
                                 headers={"Content-Type": "application/json"}),
                         timeout=15) as response:
                return 200 <= response.status < 300
        except (URLError, TimeoutError, OSError) as exc:
            logging.error("Discord notification failed: %s", exc)
            return False


class EmailNotifier(BaseNotifier):
    def __init__(self, host: str, port: int, username: str, password: str,
                 sender: str, recipients: list[str], use_tls: bool = True) -> None:
        self.host, self.port = host, port
        self.username, self.password = username, password
        self.sender, self.recipients = sender, recipients
        self.use_tls = use_tls

    def send(self, subject: str, message: str) -> bool:
        if not self.recipients:
            logging.error("Email notification skipped: recipients list is empty")
            return False
        email = EmailMessage()
        email["Subject"], email["From"] = subject, self.sender
        email["To"] = ", ".join(self.recipients)
        email.set_content(message)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as server:
                if self.use_tls:
                    server.starttls()
                if self.username:
                    server.login(self.username, self.password)
                server.send_message(email)
            return True
        except (smtplib.SMTPException, OSError) as exc:
            logging.error("Email notification failed: %s", exc)
            return False


class MultiNotifier:
    def __init__(self, notifiers: list[BaseNotifier]) -> None:
        self.notifiers = notifiers

    def send(self, subject: str, message: str) -> None:
        if not self.notifiers:
            logging.warning("No notification channel enabled; alert logged only")
            return
        for notifier in self.notifiers:
            try:
                notifier.send(subject, message)
            except Exception:
                logging.exception("Unexpected notifier error")
