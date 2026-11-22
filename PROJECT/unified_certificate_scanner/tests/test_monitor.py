import ipaddress
import unittest
from argparse import Namespace

from monitor import expand_targets, parse_networks, parse_ports, validate_args


class ScannerTests(unittest.TestCase):
    def test_parse_networks_normalizes_host_bits(self):
        self.assertEqual(str(parse_networks(["192.0.2.7/30"])[0]), "192.0.2.4/30")

    def test_expand_ipv4_skips_network_and_broadcast(self):
        self.assertEqual(expand_targets(parse_networks(["192.0.2.0/30"]), 4),
                         ["192.0.2.1", "192.0.2.2"])

    def test_expand_ipv6_small_network(self):
        self.assertEqual(expand_targets(parse_networks(["2001:db8::/126"]), 4),
                         ["2001:db8::1", "2001:db8::2"])

    def test_host_limit_rejects_large_range(self):
        with self.assertRaises(ValueError):
            expand_targets(parse_networks(["10.0.0.0/8"]), 4096)

    def test_ports_validate_and_deduplicate(self):
        self.assertEqual(parse_ports(["443", "636", "443"]), [443, 636])

    def test_invalid_port_rejected(self):
        with self.assertRaises(ValueError):
            parse_ports(["65536"])

    def test_invalid_network_rejected(self):
        with self.assertRaises(ValueError):
            parse_networks(["not-a-cidr"])

    def test_cli_limits(self):
        args = Namespace(timeout=1, workers=257, max_hosts=10,
                          expiry_warning_days=30, expected_name=None)
        with self.assertRaises(ValueError):
            validate_args(args)


if __name__ == "__main__":
    unittest.main()
