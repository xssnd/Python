#!/usr/bin/env python3
"""Interactive cross-platform service manager (systemd / Windows Services).

Read-only operations are the default. Mutating actions require an explicit
confirmation in the TUI and may require administrator/root privileges.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

APP_NAME = "Service Manager TUI"
CONFIG_DEFAULT = Path.home() / ".config" / "service_manager_tui" / "config.json"
TIMEOUT = 15


def run_command(args: list[str], timeout: int = TIMEOUT) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                         check=False, encoding="utf-8", errors="replace")


def detect_backend() -> str:
    if platform.system() == "Windows":
        return "windows"
    if shutil.which("systemctl"):
        return "systemd"
    return "unsupported"


class ServiceBackend:
    def __init__(self, backend: str | None = None):
        self.backend = backend or detect_backend()

    def list_services(self) -> list[dict]:
        if self.backend == "systemd":
            return self._systemd_list()
        if self.backend == "windows":
            return self._windows_list()
        raise RuntimeError("Unsupported platform: systemd or Windows Services not detected")

    def _systemd_list(self) -> list[dict]:
        if not shutil.which("systemctl"):
            raise RuntimeError("systemctl not found; this host may not use systemd")
        cp = run_command(["systemctl", "list-units", "--type=service", "--all",
                         "--no-legend", "--no-pager"])
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr.strip() or "systemctl listing failed")
        rows = []
        for line in cp.stdout.splitlines():
            parts = line.split(None, 4)
            if len(parts) < 3:
                continue
            name = parts[0]
            if not name.endswith(".service"):
                continue
            rows.append({"name": name, "state": parts[2], "substate": parts[3] if len(parts)>3 else "",
                        "startup": "—", "description": parts[4] if len(parts)>4 else "",
                        "backend": "systemd"})
        # Enrich selected service metadata in a single properties query per service.
        for row in rows:
            props = run_command(["systemctl", "show", row["name"], "--property=UnitFileState",
                                "--property=Description", "--property=ActiveState", "--property=SubState"])
            if props.returncode == 0:
                for item in props.stdout.splitlines():
                    key, _, value = item.partition("=")
                    if key == "UnitFileState": row["startup"] = value or "unknown"
                    elif key == "Description": row["description"] = value or row["description"]
                    elif key == "ActiveState": row["state"] = value or row["state"]
                    elif key == "SubState": row["substate"] = value or row["substate"]
        return sorted(rows, key=lambda x: x["name"].lower())

    def _windows_list(self) -> list[dict]:
        ps = ("Get-Service | Select-Object Name,DisplayName,Status,StartType | "
              "ConvertTo-Json -Compress")
        cp = run_command(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps])
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr.strip() or "PowerShell service query failed")
        raw = cp.stdout.strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        return sorted([{"name": str(x.get("Name", "")),
                       "state": str(x.get("Status", "Unknown")),
                       "substate": str(x.get("Status", "")),
                       "startup": str(x.get("StartType", "Unknown")),
                       "description": str(x.get("DisplayName", "")),
                       "backend": "windows"} for x in data], key=lambda x:x["name"].lower())

    def action(self, name: str, action: str) -> tuple[bool, str]:
        if action not in {"start", "stop", "restart"}:
            return False, "Unsupported action"
        if self.backend == "systemd":
            cp = run_command(["systemctl", action, name])
        elif self.backend == "windows":
            # Service names are passed as a parameter, not interpolated into a script.
            ps = f"{action.title()}-Service -Name $args[0] -ErrorAction Stop"
            cp = run_command(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                             ps, name])
        else:
            return False, "Unsupported backend"
        if cp.returncode == 0:
            return True, cp.stdout.strip() or f"{action.title()} request completed for {name}"
        return False, cp.stderr.strip() or cp.stdout.strip() or f"{action} failed (exit {cp.returncode})"


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read config {path}: {exc}") from exc


def export_rows(rows: list[dict], output: Path, fmt: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        output.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    elif fmt == "csv":
        fields = ["name", "state", "substate", "startup", "description", "backend"]
        with output.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)


def cli_main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--backend", choices=["systemd", "windows"], help="Force backend (normally auto-detected)")
    parser.add_argument("--config", type=Path, default=CONFIG_DEFAULT)
    parser.add_argument("--list", action="store_true", help="List services without launching TUI")
    parser.add_argument("--export", choices=["json", "csv"], help="Export service inventory")
    parser.add_argument("--output", type=Path, help="Export destination (default: services.<format>)")
    parser.add_argument("--action", choices=["start", "stop", "restart"], help="Service action for headless mode")
    parser.add_argument("--service", help="Service name for --action")
    parser.add_argument("--yes", action="store_true", help="Confirm headless mutating action")
    args = parser.parse_args(argv)
    backend = ServiceBackend(args.backend)
    if args.action:
        if not args.service:
            parser.error("--action requires --service")
        if not args.yes:
            parser.error("Headless service actions require --yes")
        ok, message = backend.action(args.service, args.action)
        print(message)
        return 0 if ok else 1
    if args.list or args.export:
        try:
            rows = backend.list_services()
            if args.export:
                dest = args.output or Path(f"services.{args.export}")
                export_rows(rows, dest, args.export)
                print(f"Exported {len(rows)} services to {dest}")
            else:
                for row in rows:
                    print(f'{row["state"]:12} {row["startup"]:12} {row["name"]:40} {row["description"]}')
            return 0
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, Vertical
        from textual.widgets import Header, Footer, DataTable, Input, Button, Static
        from textual.screen import ModalScreen
    except ImportError:
        print("Textual is required for the interactive dashboard. Install: pip install -r requirements.txt", file=sys.stderr)
        return 2

    class ConfirmScreen(ModalScreen[bool]):
        def __init__(self, title: str, prompt: str):
            super().__init__()
            self.title_text, self.prompt_text = title, prompt
        def compose(self) -> ComposeResult:
            with Vertical(id="confirm"):
                yield Static(self.title_text, classes="confirm-title")
                yield Static(self.prompt_text)
                with Horizontal():
                    yield Button("Cancel", id="cancel")
                    yield Button("Confirm", id="confirm", variant="warning")
        def on_button_pressed(self, event):
            self.dismiss(event.button.id == "confirm")

    class ServiceManagerApp(App):
        TITLE = APP_NAME
        CSS = """
        Screen { padding: 1; }
        #toolbar { height: 3; }
        #search { width: 1fr; }
        #summary { height: 2; color: $text-muted; }
        DataTable { height: 1fr; }
        #help { height: 2; color: $text-muted; }
        #confirm { width: 60; height: auto; padding: 1 2; border: thick $accent; background: $surface; }
        .confirm-title { text-style: bold; color: $warning; }
        """
        BINDINGS = [("q", "quit", "Quit"), ("r", "refresh", "Refresh"),
                    ("s", "start", "Start"), ("x", "stop", "Stop"),
                    ("k", "restart", "Restart"), ("e", "export_json", "Export JSON")]

        def __init__(self):
            super().__init__()
            self.backend = backend
            self.rows = []
            self.config = load_config(args.config)
            self.favorites = set(self.config.get("favorites", []))
            self.blocklist = set(self.config.get("deny_actions", []))
            self.last_update = None
            self.message = "Ready"

        def compose(self) -> ComposeResult:
            yield Header()
            with Horizontal(id="toolbar"):
                yield Input(placeholder="Filter by service name, status or description…", id="search")
                yield Button("Refresh", id="refresh")
                yield Button("Export CSV", id="csv")
                yield Button("Export JSON", id="json")
            yield Static("Loading service inventory…", id="summary")
            yield DataTable(id="services", zebra_stripes=True, cursor_type="row")
            yield Static("Keys: S start · X stop · K restart · R refresh · E export JSON · Q quit", id="help")
            yield Footer()

        def on_mount(self):
            table = self.query_one("#services", DataTable)
            table.add_columns("Status", "Startup", "Service", "Description")
            self.refresh_data()

        def selected_service(self):
            table = self.query_one("#services", DataTable)
            if table.row_count == 0 or table.cursor_row is None:
                return None
            try:
                return table.get_row_at(table.cursor_row)[2]
            except Exception:
                return None

        def refresh_data(self):
            try:
                self.rows = self.backend.list_services()
                self.last_update = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
                self.populate_table()
                self.query_one("#summary", Static).update(
                    f"{len(self.rows)} services | backend: {self.backend.backend} | refreshed: {self.last_update} | {self.message}")
            except Exception as exc:
                self.message = f"Inventory error: {exc}"
                self.query_one("#summary", Static).update(self.message)

        def populate_table(self):
            table = self.query_one("#services", DataTable)
            table.clear()
            query = self.query_one("#search", Input).value.lower()
            for row in self.rows:
                searchable = " ".join(str(row.get(k, "")) for k in ("name","state","startup","description")).lower()
                if query and query not in searchable:
                    continue
                state = row["state"]
                table.add_row(state, row["startup"], row["name"], row["description"], key=row["name"])

        def on_input_changed(self, event: Input.Changed):
            if event.input.id == "search":
                self.populate_table()

        def action_refresh(self):
            self.refresh_data()

        def action_start(self):
            self.perform_action("start")

        def action_stop(self):
            self.perform_action("stop")

        def action_restart(self):
            self.perform_action("restart")

        def action_export_json(self):
            self.export_file("json")

        def perform_action(self, action):
            name = self.selected_service()
            if not name:
                self.message = "Select a service row first."
                self.refresh_data()
                return
            if name in self.blocklist:
                self.message = f"Action blocked by deny_actions config: {name}"
                self.refresh_data()
                return
            prompt = f"Run {action.upper()} on service '{name}'? This changes system state."
            self.push_screen(ConfirmScreen("Confirm service operation", prompt), self.after_confirm(action, name))

        def after_confirm(self, action, name):
            def callback(confirmed):
                if not confirmed:
                    self.message = "Action cancelled."
                    self.refresh_data()
                    return
                ok, msg = self.backend.action(name, action)
                self.message = ("SUCCESS: " if ok else "FAILED: ") + msg
                self.refresh_data()
            return callback

        def on_button_pressed(self, event: Button.Pressed):
            if event.button.id == "refresh":
                self.refresh_data()
            elif event.button.id == "csv":
                self.export_file("csv")
            elif event.button.id == "json":
                self.export_file("json")

        def export_file(self, fmt):
            try:
                out = Path.cwd() / f"services-{datetime.now().strftime('%Y%m%d-%H%M%S')}.{fmt}"
                export_rows(self.rows, out, fmt)
                self.message = f"Exported {len(self.rows)} rows to {out}"
            except Exception as exc:
                self.message = f"Export error: {exc}"
            self.refresh_data()

    ServiceManagerApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(cli_main())
