import csv
import json
import tempfile
import unittest
from pathlib import Path

import monitor


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"pid": 1, "name": "alpha", "username": "root", "status": "running", "cpu_percent": 80, "memory_percent": 10, "memory_mb": 100, "threads": 2},
            {"pid": 2, "name": "beta", "username": "user", "status": "sleeping", "cpu_percent": 10, "memory_percent": 70, "memory_mb": 700, "threads": 4},
            {"pid": 3, "name": "gamma", "username": "user", "status": "running", "cpu_percent": 40, "memory_percent": 30, "memory_mb": 300, "threads": 3},
        ]

    def test_cpu_ranking(self):
        self.assertEqual([r["pid"] for r in monitor.rank_processes(self.records, "cpu", 2)], [1, 3])

    def test_memory_ranking(self):
        self.assertEqual([r["pid"] for r in monitor.rank_processes(self.records, "memory", 2)], [2, 3])

    def test_top_must_be_positive(self):
        with self.assertRaises(ValueError):
            monitor.rank_processes(self.records, "cpu", 0)

    def test_invalid_sort(self):
        with self.assertRaises(ValueError):
            monitor.rank_processes(self.records, "disk", 5)

    def test_bar_clamps_values(self):
        self.assertEqual(len(monitor.render_bar(150)), 18)
        self.assertEqual(len(monitor.render_bar(-1)), 18)

    def test_json_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.json"
            monitor.export_records(self.records, path, "json")
            self.assertEqual(len(json.loads(path.read_text(encoding="utf-8"))), 3)

    def test_csv_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.csv"
            monitor.export_records(self.records, path, "csv")
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]["name"], "alpha")


if __name__ == "__main__":
    unittest.main()
