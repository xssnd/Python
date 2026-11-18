import tempfile
import unittest
from pathlib import Path
import monitor

class ZombieCleanerTests(unittest.TestCase):
    def test_group_by_parent(self):
        rows = [
            {"pid": 11, "ppid": 4, "parent_name": "worker", "parent_status": "sleeping"},
            {"pid": 12, "ppid": 4, "parent_name": "worker", "parent_status": "sleeping"},
            {"pid": 13, "ppid": 8, "parent_name": "daemon", "parent_status": "running"},
        ]
        groups = monitor.group_by_parent(rows)
        self.assertEqual(groups[0]["ppid"], 4)
        self.assertEqual(groups[0]["count"], 2)
        self.assertEqual(groups[0]["zombie_pids"], [11, 12])

    def test_empty_report(self):
        report = monitor.build_report([], threshold=2)
        self.assertEqual(report["zombie_count"], 0)
        self.assertFalse(report["alert"])
        self.assertEqual(report["parent_count"], 0)

    def test_threshold_validation(self):
        with self.assertRaises(ValueError):
            monitor.build_report([], threshold=0)

    def test_export_json_and_csv(self):
        row = {"pid": 9, "ppid": 3, "name": "child", "username": "user",
               "age_seconds": 10.0, "started_at": None, "parent_name": "parent",
               "parent_status": "sleeping"}
        report = monitor.build_report([row])
        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory) / "nested" / "report.json"
            csv_path = Path(directory) / "report.csv"
            monitor.export_report(report, json_path, "json")
            monitor.export_report(report, csv_path, "csv")
            self.assertIn('"zombie_count": 1', json_path.read_text(encoding="utf-8"))
            self.assertIn("pid,ppid,name", csv_path.read_text(encoding="utf-8"))

    def test_negative_age_rejected(self):
        with self.assertRaises(ValueError):
            monitor.collect_zombies(min_age=-1)

if __name__ == "__main__":
    unittest.main()
