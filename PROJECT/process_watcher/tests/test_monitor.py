import unittest
from unittest.mock import patch

from monitor import Watcher


def make_config():
    return {
        "settings": {"interval_seconds": 10, "restart_cooldown_seconds": 60,
                     "max_restart_attempts": 2, "retry_window_seconds": 300,
                     "recovery_notifications": True},
        "processes": [{"name": "demo", "match": ["demo"],
                       "restart_command": ["echo", "restart"]}]
    }


class WatcherTests(unittest.TestCase):
    @patch("monitor.notify")
    @patch("monitor.process_is_running", return_value=False)
    @patch("monitor.subprocess.run")
    def test_restart_command_is_run_without_shell(self, run, _running, _notify):
        run.return_value.returncode = 0
        run.return_value.stdout = ""
        run.return_value.stderr = ""
        config = make_config()
        watcher = Watcher(config)
        self.assertEqual(watcher.check(config["processes"][0], now=1000), "restart-command-ok")
        self.assertFalse(run.call_args.kwargs["shell"])

    @patch("monitor.notify")
    @patch("monitor.process_is_running", return_value=False)
    @patch("monitor.subprocess.run")
    def test_cooldown_prevents_repeat_restart(self, run, _running, _notify):
        run.return_value.returncode = 0
        run.return_value.stdout = ""
        run.return_value.stderr = ""
        config = make_config()
        watcher = Watcher(config)
        item = config["processes"][0]
        watcher.check(item, now=1000)
        self.assertEqual(watcher.check(item, now=1010), "cooldown")
        self.assertEqual(run.call_count, 1)

    @patch("monitor.notify")
    @patch("monitor.process_is_running", return_value=False)
    @patch("monitor.subprocess.run")
    def test_restart_attempt_limit(self, run, _running, _notify):
        run.return_value.returncode = 0
        run.return_value.stdout = ""
        run.return_value.stderr = ""
        config = make_config()
        watcher = Watcher(config)
        item = config["processes"][0]
        watcher.check(item, now=1000)
        watcher.check(item, now=1061)
        self.assertEqual(watcher.check(item, now=1122), "restart-limit")
        self.assertEqual(run.call_count, 2)

    @patch("monitor.notify")
    @patch("monitor.process_is_running", return_value=False)
    def test_missing_restart_command_is_alert_only(self, _running, _notify):
        config = make_config()
        config["processes"][0]["restart_command"] = []
        self.assertEqual(Watcher(config).check(config["processes"][0], now=1000), "down-no-command")


if __name__ == "__main__":
    unittest.main()
