import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import monitor


class InodeMonitorTests(unittest.TestCase):
    def stats(self, total=1000, free=150, available=140):
        return SimpleNamespace(f_files=total, f_ffree=free, f_favail=available)

    def test_decode_mount_escapes(self):
        self.assertEqual(monitor.decode_mount_field(r"/mnt/my\040disk"), "/mnt/my disk")

    def test_read_mountinfo(self):
        content = "36 25 8:1 / / rw,relatime - ext4 /dev/sda1 rw\n"
        with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            self.assertEqual(monitor.read_mounts(Path(handle.name)), [("/dev/sda1", "/", "ext4")])

    def test_inspect_calculates_inode_metrics(self):
        rows = monitor.inspect_mounts([("/dev/sda1", "/", "ext4")], lambda _: self.stats())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].used_inodes, 850)
        self.assertEqual(rows[0].available_inodes, 140)
        self.assertEqual(rows[0].used_percent, 85.0)

    def test_duplicate_and_ignored_mounts(self):
        mounts = [("dev", "/", "ext4"), ("dev", "/", "ext4"), ("tmp", "/tmp", "tmpfs")]
        rows = monitor.inspect_mounts(mounts, lambda _: self.stats(), ignored_mounts=["/tmp"])
        self.assertEqual([row.mountpoint for row in rows], ["/"])

    def test_skip_filesystem_without_inode_counter(self):
        rows = monitor.inspect_mounts([("dev", "/", "ext4")], lambda _: self.stats(total=0))
        self.assertEqual(rows, [])

    def test_unreadable_mount_is_skipped(self):
        def fail(_):
            raise PermissionError("denied")
        self.assertEqual(monitor.inspect_mounts([("dev", "/secret", "ext4")], fail), [])

    def test_thresholds(self):
        self.assertEqual(monitor.classify(79.9), "OK")
        self.assertEqual(monitor.classify(80), "WARNING")
        self.assertEqual(monitor.classify(90), "CRITICAL")
        with self.assertRaises(ValueError):
            monitor.evaluate([], 95, 90)

    def test_export_csv_and_json(self):
        row = monitor.inspect_mounts([("dev", "/", "ext4")], lambda _: self.stats())[0]
        with tempfile.TemporaryDirectory() as directory:
            for fmt, name in (("csv", "report.csv"), ("json", "report.json")):
                target = Path(directory) / name
                monitor.export_records([row], str(target), fmt)
                self.assertTrue(target.is_file())
                self.assertGreater(target.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
