import json
import platform
import unittest
from unittest.mock import patch, MagicMock
from service_manager import ServiceBackend, detect_backend, load_config, export_rows
from pathlib import Path
import tempfile


class ServiceBackendTests(unittest.TestCase):
    def test_backend_detection_windows(self):
        with patch("service_manager.platform.system", return_value="Windows"):
            self.assertEqual(detect_backend(), "windows")

    def test_backend_detection_linux_systemd(self):
        with patch("service_manager.platform.system", return_value="Linux"), \
             patch("service_manager.shutil.which", return_value="/usr/bin/systemctl"):
            self.assertEqual(detect_backend(), "systemd")

    def test_action_validation(self):
        backend = ServiceBackend("unsupported")
        ok, msg = backend.action("demo", "enable")
        self.assertFalse(ok)
        self.assertEqual(msg, "Unsupported action")

    def test_export_json(self):
        rows = [{"name": "demo", "state": "running", "substate": "running",
                 "startup": "enabled", "description": "Example", "backend": "systemd"}]
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "out.json"
            export_rows(rows, dest, "json")
            self.assertEqual(json.loads(dest.read_text()), rows)


if __name__ == "__main__":
    unittest.main()
