import unittest
from unittest.mock import patch

from monitor import AlertMonitor


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.monitor = AlertMonitor({
            "monitor": {
                "cpu_threshold": 80,
                "memory_threshold": 75,
                "consecutive_breaches": 2,
                "cooldown_seconds": 300,
                "recovery_notifications": True
            },
            "notifications": {}
        }, once=True)

    def test_requires_consecutive_breaches(self):
        with patch.object(self.monitor, "_notify") as notify:
            self.monitor.process_sample({"cpu": 90, "memory": 20})
            self.assertNotIn("cpu", self.monitor._active_alerts)
            self.monitor.process_sample({"cpu": 90, "memory": 20})
            self.assertIn("cpu", self.monitor._active_alerts)
            notify.assert_called_once()

    def test_recovery_clears_active_alert(self):
        with patch.object(self.monitor, "_notify") as notify:
            self.monitor.process_sample({"cpu": 90, "memory": 20})
            self.monitor.process_sample({"cpu": 90, "memory": 20})
            self.monitor.process_sample({"cpu": 20, "memory": 20})
            self.assertNotIn("cpu", self.monitor._active_alerts)
            self.assertEqual(notify.call_count, 2)
            self.assertIn("recovered", notify.call_args.args[1])

    def test_threshold_validation(self):
        with self.assertRaises(ValueError):
            AlertMonitor({"monitor": {"cpu_threshold": 101}, "notifications": {}})


if __name__ == "__main__":
    unittest.main()
