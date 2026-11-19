"""Unit tests for Docker Container Health Checker."""
import unittest
from unittest.mock import patch

import monitor


class ConfigTests(unittest.TestCase):
    def test_invalid_interval_is_rejected(self):
        with patch("builtins.open", unittest.mock.mock_open(read_data='{"settings":{"interval_seconds":0}}')):
            with self.assertRaises(ValueError):
                monitor.load_config("unused")

    def test_defaults_are_applied(self):
        with patch("builtins.open", unittest.mock.mock_open(read_data='{"containers":[]}')):
            config = monitor.load_config("unused")
        self.assertTrue(config["settings"]["auto_restart"])
        self.assertEqual(config["settings"]["interval_seconds"], 15)


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.items = [
            {"name": "api", "id": "abc123", "full_id": "abc123full"},
            {"name": "db", "id": "def456", "full_id": "def456full"},
        ]

    def test_include_filter(self):
        settings = {"include_containers": ["api"], "exclude_containers": []}
        self.assertEqual([x["name"] for x in monitor.filter_containers(self.items, settings)], ["api"])

    def test_exclude_filter(self):
        settings = {"include_containers": [], "exclude_containers": ["def456"]}
        self.assertEqual([x["name"] for x in monitor.filter_containers(self.items, settings)], ["api"])


class RestartPolicyTests(unittest.TestCase):
    def setUp(self):
        self.config = {"settings": {
            "auto_restart": True, "restart_cooldown_seconds": 60,
            "max_restart_attempts": 2, "retry_window_seconds": 300,
            "restart_timeout_seconds": 10,
        }, "containers": []}
        self.checker = monitor.HealthChecker(self.config, dry_run=True)
        self.container = {"name": "api", "id": "abc", "full_id": "abcfull",
                          "status": "running", "health": "unhealthy"}

    def test_dry_run_never_calls_docker_restart(self):
        with patch("monitor.docker_command") as command:
            result = self.checker.check([self.container], now=1000)
        command.assert_not_called()
        self.assertEqual(result[0]["action"], "dry-run")

    def test_no_healthcheck_is_not_restarted(self):
        item = {**self.container, "health": "no-healthcheck"}
        with patch("monitor.docker_command") as command:
            result = self.checker.check([item], now=1000)
        command.assert_not_called()
        self.assertEqual(result[0]["action"], "not-configured")

    def test_restart_limit(self):
        self.checker.attempts["api"].extend([800, 900])
        result = self.checker.check([self.container], now=1000)
        self.assertEqual(result[0]["action"], "blocked")
        self.assertEqual(result[0]["detail"], "restart limit reached")


if __name__ == "__main__":
    unittest.main()
