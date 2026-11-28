#!/usr/bin/env python3
"""Webhook Command Bridge — authenticated, allowlisted CI/CD actions.

Only configured action IDs are accepted. Commands are argv arrays; shell=True is
never used. Configure HTTPS at a trusted reverse proxy or bind to localhost.
"""
from __future__ import annotations
import argparse
import hashlib
import hmac
import json
import logging
import os
import re
import sqlite3
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_BODY = 64 * 1024
CLOCK_SKEW = 300
ACTION_ID = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")
LOG = logging.getLogger("webhook_bridge")


def load_config(path: Path) -> dict:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cfg.get("keys"), dict) or not cfg["keys"]:
        raise ValueError("Config requires keys mapping key_id to environment variable name")
    if not isinstance(cfg.get("actions"), dict) or not cfg["actions"]:
        raise ValueError("Config requires at least one action")
    for action_id, action in cfg["actions"].items():
        if not ACTION_ID.fullmatch(action_id):
            raise ValueError(f"Invalid action id: {action_id}")
        argv = action.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
            raise ValueError(f"Action {action_id}: argv must be a non-empty list of strings")
        if action.get("cwd") and not Path(action["cwd"]).is_absolute():
            raise ValueError(f"Action {action_id}: cwd must be absolute")
        if action.get("timeout", 300) < 1 or action.get("timeout", 300) > 3600:
            raise ValueError(f"Action {action_id}: timeout must be 1..3600 seconds")
    return cfg


class ReplayStore:
    def __init__(self, db_path: str):
        self.path = db_path
        self.lock = threading.Lock()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS nonces (nonce TEXT PRIMARY PRIMARY KEY, ts INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, ts INTEGER, key_id TEXT, action TEXT, status TEXT, detail TEXT)")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def claim(self, nonce: str, ts: int) -> bool:
        with self.lock, self.connect() as db:
            db.execute("DELETE FROM nonces WHERE ts < ?", (int(time.time()) - 86400,))
            try:
                db.execute("INSERT INTO nonces(nonce, ts) VALUES (?, ?)", (nonce, ts))
                return True
            except sqlite3.IntegrityError:
                return False

    def audit(self, key_id: str, action: str, status: str, detail: str = ""):
        with self.lock, self.connect() as db:
            db.execute("INSERT INTO audit(ts,key_id,action,status,detail) VALUES(?,?,?,?,?)",
                      (int(time.time()), key_id, action, status, detail[:500]))


def make_handler(cfg: dict, store: ReplayStore):
    semaphore = threading.BoundedSemaphore(int(cfg.get("max_concurrent_actions", 3)))

    class Handler(BaseHTTPRequestHandler):
        server_version = "WebhookBridge"
        sys_version = ""

        def respond(self, code: int, payload: dict):
            data = json.dumps(payload, separators=(",", ":")).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/health":
                self.respond(200, {"status": "ok"})
            else:
                self.respond(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/webhook":
                self.respond(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.respond(400, {"error": "invalid content length"})
                return
            if length <= 0 or length > MAX_BODY:
                self.respond(413, {"error": "payload too large or empty"})
                return
            raw = self.rfile.read(length)
            key_id = self.headers.get("X-Webhook-Key", "")
            timestamp = self.headers.get("X-Webhook-Timestamp", "")
            nonce = self.headers.get("X-Webhook-Nonce", "")
            signature = self.headers.get("X-Webhook-Signature", "")
            secret_env = cfg["keys"].get(key_id)
            if not secret_env or not ACTION_ID.fullmatch(key_id):
                self.respond(401, {"error": "authentication failed"})
                return
            secret = os.environ.get(secret_env, "")
            if len(secret) < 32:
                LOG.error("Signing secret env %s is unset or too short", secret_env)
                self.respond(503, {"error": "server key configuration error"})
                return
            if not timestamp.isdigit() or abs(int(time.time()) - int(timestamp)) > CLOCK_SKEW:
                self.respond(401, {"error": "expired timestamp"})
                return
            if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", nonce):
                self.respond(400, {"error": "invalid nonce"})
                return
            expected = hmac.new(secret.encode(), timestamp.encode() + b"." + nonce.encode() + b"." + raw, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, signature.lower()):
                self.respond(401, {"error": "authentication failed"})
                return
            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                self.respond(400, {"error": "invalid JSON"})
                return
            if not isinstance(payload, dict) or set(payload) - {"action", "request_id"}:
                self.respond(400, {"error": "expected action and optional request_id"})
                return
            action_id = payload.get("action")
            if not isinstance(action_id, str) or action_id not in cfg["actions"]:
                self.respond(403, {"error": "action not allowed"})
                return
            if not store.claim(nonce, int(timestamp)):
                self.respond(409, {"error": "replayed request"})
                return
            if not semaphore.acquire(blocking=False):
                store.audit(key_id, action_id, "rejected", "concurrency limit")
                self.respond(429, {"error": "busy"})
                return
            action = cfg["actions"][action_id]
            if action.get("enabled", True) is not True:
                semaphore.release()
                store.audit(key_id, action_id, "rejected", "disabled")
                self.respond(403, {"error": "action disabled"})
                return
            request_id = str(payload.get("request_id", ""))[:128]
            store.audit(key_id, action_id, "accepted", request_id)
            self.respond(202, {"status": "accepted", "action": action_id, "request_id": request_id})
            threading.Thread(target=self.run_action, args=(action, key_id, action_id, semaphore), daemon=True).start()

        @staticmethod
        def run_action(action, key_id, action_id, semaphore):
            try:
                LOG.info("Running allowlisted action %s from key %s", action_id, key_id)
                result = subprocess.run(
                    action["argv"], cwd=action.get("cwd"),
                    env={**({"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"}), **action.get("env", {})},
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, timeout=int(action.get("timeout", 300)), check=False,
                )
                output = result.stdout[-1500:] if result.stdout else ""
                store.audit(key_id, action_id, "success" if result.returncode == 0 else "failed",
                           f"exit={result.returncode}; output={output}")
                LOG.info("Action %s finished rc=%d", action_id, result.returncode)
            except subprocess.TimeoutExpired:
                store.audit(key_id, action_id, "timeout", "execution timed out")
                LOG.error("Action %s timed out", action_id)
            except Exception:
                store.audit(key_id, action_id, "error", "execution exception")
                LOG.exception("Action %s failed", action_id)
            finally:
                semaphore.release()

        def log_message(self, fmt, *args):
            LOG.info("%s - %s", self.client_address[0], fmt % args)

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Secure allowlisted webhook-to-command bridge")
    parser.add_argument("--config", default="config.json", help="Path to JSON configuration")
    args = parser.parse_args()
    cfg = load_config(Path(args.config))
    logging.basicConfig(level=getattr(logging, cfg.get("log_level", "INFO").upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(message)s")
    store = ReplayStore(cfg.get("sqlite_path", "./bridge_state.sqlite3"))
    host = cfg.get("host", "127.0.0.1")
    port = int(cfg.get("port", 9080))
    server = ThreadingHTTPServer((host, port), make_handler(cfg, store))
    server.daemon_threads = True
    LOG.warning("Listening on %s:%d. Use HTTPS via trusted reverse proxy for remote access.", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("Shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
