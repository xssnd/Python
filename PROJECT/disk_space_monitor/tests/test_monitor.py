import unittest
from types import SimpleNamespace

from monitor import AlertManager, DiskStatus, classify, discover_disks, evaluate_disks


def disk(free_percent, mount="/"):
    total = 1000
    free = int(total * free_percent / 100)
    return DiskStatus("dev", mount, "ext4", total, total-free, free,
                      free_percent, 100-free_percent, "OK")


class FakeNotifier:
    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)


class MonitorTests(unittest.TestCase):
    def test_threshold_boundaries(self):
        self.assertEqual(classify(50), "OK")
        self.assertEqual(classify(10), "WARNING")
        self.assertEqual(classify(5), "CRITICAL")
        self.assertEqual(classify(0), "CRITICAL")

    def test_evaluate_disks(self):
        result = evaluate_disks([disk(9), disk(4), disk(20)], 10, 5)
        self.assertEqual([d.level for d in result], ["WARNING", "CRITICAL", "OK"])

    def test_discover_skips_unreadable_and_duplicate_mounts(self):
        parts = [
            SimpleNamespace(device="/dev/a", mountpoint="/data", fstype="ext4", opts="rw"),
            SimpleNamespace(device="/dev/b", mountpoint="/data", fstype="ext4", opts="rw"),
            SimpleNamespace(device="proc", mountpoint="/proc", fstype="proc", opts="rw"),
        ]
        def usage(path):
            if path == "/proc":
                raise OSError("not available")
            return SimpleNamespace(total=100, used=70, free=30)
        result = discover_disks(parts, usage)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].mountpoint, "/data")
        self.assertEqual(result[0].free_percent, 30.0)

    def test_alert_and_cooldown_and_recovery(self):
        notifier = FakeNotifier()
        manager = AlertManager([notifier], cooldown_seconds=60)
        manager.process([disk(8)], now=100)
        manager.process([disk(7)], now=120)
        self.assertEqual(len(notifier.messages), 1)
        manager.process([disk(7)], now=161)
        self.assertEqual(len(notifier.messages), 2)
        manager.process([disk(30)], now=162)
        self.assertIn("RECOVERY", notifier.messages[-1])


if __name__ == "__main__":
    unittest.main()
