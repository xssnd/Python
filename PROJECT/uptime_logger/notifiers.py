"""Optional Telegram, Discord webhook and SMTP notification adapters."""
import json, smtplib
from email.message import EmailMessage
from urllib.request import Request,urlopen

class TelegramNotifier:
    def __init__(self,bot_token,chat_id):
        self.url=f"https://api.telegram.org/bot{bot_token}/sendMessage"; self.chat_id=chat_id
    def send(self,message):
        data=json.dumps({"chat_id":self.chat_id,"text":message}).encode()
        with urlopen(Request(self.url,data=data,headers={"Content-Type":"application/json"}),timeout=10): pass

class DiscordNotifier:
    def __init__(self,webhook_url): self.webhook_url=webhook_url
    def send(self,message):
        data=json.dumps({"content":message[:1900]}).encode()
        with urlopen(Request(self.webhook_url,data=data,headers={"Content-Type":"application/json"}),timeout=10): pass

class EmailNotifier:
    def __init__(self,settings): self.settings=settings
    def send(self,message):
        s=self.settings; email=EmailMessage()
        email["Subject"]="Uptime Logger alert"; email["From"]=s["sender"]; email["To"]=s["recipient"]; email.set_content(message)
        with smtplib.SMTP(s["smtp_host"],int(s.get("smtp_port",587)),timeout=10) as server:
            server.starttls()
            if s.get("username"): server.login(s["username"],s.get("password",""))
            server.send_message(email)

def build_notifiers(config):
    result=[]; t=config.get("telegram",{}); d=config.get("discord",{}); e=config.get("email",{})
    if t.get("bot_token") and t.get("chat_id"): result.append(TelegramNotifier(t["bot_token"],t["chat_id"]))
    if d.get("webhook_url"): result.append(DiscordNotifier(d["webhook_url"]))
    if all(e.get(k) for k in ("smtp_host","sender","recipient")): result.append(EmailNotifier(e))
    return result
