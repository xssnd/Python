import unittest

from monitor import calculate_rates, format_bytes, sparkline, build_record


class BandwidthTrackerTests(unittest.TestCase):
    def test_calculate_rx_tx_rates(self):
        previous = {"time": 10.0, "rx": 1_000, "tx": 2_000}
        current = {"time": 12.0, "rx": 5_000, "tx": 6_000}
        result = calculate_rates(previous, current)
        self.assertEqual(result["rx_bytes_per_sec"], 2_000)
        self.assertEqual(result["tx_bytes_per_sec"], 2_000)
        self.assertEqual(result["rx_mbps"], 0.016)
        self.assertEqual(result["tx_bytes_total"], 6_000)

    def test_counter_reset_does_not_create_negative_rate(self):
        previous = {"time": 1.0, "rx": 10_000, "tx": 20_000}
        current = {"time": 2.0, "rx": 100, "tx": 25_000}
        result = calculate_rates(previous, current)
        self.assertEqual(result["rx_bytes_per_sec"], 0)
        self.assertEqual(result["tx_bytes_per_sec"], 5_000)

    def test_non_positive_elapsed_time_rejected(self):
        with self.assertRaises(ValueError):
            calculate_rates({"time": 2.0, "rx": 0, "tx": 0},
                            {"time": 2.0, "rx": 1, "tx": 1})

    def test_format_bytes(self):
        self.assertEqual(format_bytes(1024), "1.00 KB")
        self.assertEqual(format_bytes(0), "0.00 B")

    def test_sparkline(self):
        self.assertEqual(sparkline([]), "—")
        self.assertEqual(sparkline([1, 1, 1]), "▁▁▁")
        self.assertEqual(len(sparkline([1, 2, 3], width=2)), 2)

    def test_build_record(self):
        record = build_record("eth0", {"rx_mbps": 1.5}, timestamp="2026-01-01T00:00:00+00:00")
        self.assertEqual(record["interface"], "eth0")
        self.assertEqual(record["rx_mbps"], 1.5)


if __name__ == "__main__":
    unittest.main()
