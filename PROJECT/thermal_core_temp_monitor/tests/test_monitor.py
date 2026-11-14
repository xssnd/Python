import tempfile
import unittest
from pathlib import Path

from monitor import load_config, format_report, Temperature, ThrottleCounter


class MonitorTests(unittest.TestCase):
    def test_default_config(self):
        config = load_config(Path("/path/that/does/not/exist/thermal.json"))
        self.assertEqual(config["interval_seconds"], 5)
        self.assertEqual(config["critical_celsius"], 90)

    def test_invalid_threshold_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"warning_celsius": 95, "critical_celsius": 90}')
            with self.assertRaises(ValueError):
                load_config(path)

    def test_report_contains_sensor_and_counter(self):
        report = format_report(
            [Temperature("coretemp", "Package id 0", 72.5, "hwmon")],
            [ThrottleCounter("cpu0:core_throttle_count", 3, "/sys/example")]
        )
        self.assertIn("72.5 °C", report)
        self.assertIn("core_throttle_count: 3", report)


if __name__ == "__main__":
    unittest.main()
