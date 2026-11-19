import unittest
import monitor

class AddressTests(unittest.TestCase):
    def test_wildcard_addresses(self):
        self.assertTrue(monitor.is_wildcard_address("0.0.0.0"))
        self.assertTrue(monitor.is_wildcard_address("::"))
        self.assertFalse(monitor.is_wildcard_address("127.0.0.1"))
    def test_address_parts_tuple(self):
        self.assertEqual(monitor.address_parts(("127.0.0.1", 8080)), ("127.0.0.1", 8080))
    def test_address_parts_empty(self):
        self.assertEqual(monitor.address_parts(None), ("", 0))

class FilterTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"protocol":"tcp","port":22,"pid":10,"process":"sshd","command":"/usr/sbin/sshd","exposure":"ALL INTERFACES"},
            {"protocol":"udp","port":53,"pid":20,"process":"named","command":"named -f","exposure":"SPECIFIC ADDRESS"},
        ]
    def args(self, **overrides):
        values = dict(protocol="all", port=None, pid=None, process=None, exposed_only=False)
        values.update(overrides)
        return type("Args", (), values)()
    def test_protocol_filter(self):
        self.assertEqual(len(monitor.filter_records(self.records, self.args(protocol="tcp"))), 1)
    def test_port_filter(self):
        self.assertEqual(monitor.filter_records(self.records, self.args(port=[53])), [self.records[1]])
    def test_pid_filter(self):
        self.assertEqual(monitor.filter_records(self.records, self.args(pid=10)), [self.records[0]])
    def test_process_filter_case_insensitive(self):
        self.assertEqual(monitor.filter_records(self.records, self.args(process="SSH")), [self.records[0]])
    def test_exposed_filter(self):
        self.assertEqual(monitor.filter_records(self.records, self.args(exposed_only=True)), [self.records[0]])

class ValidationTests(unittest.TestCase):
    def test_invalid_port_rejected(self):
        args = type("Args", (), dict(interval=1, duration=None, port=[70000], pid=None))()
        with self.assertRaises(ValueError):
            monitor.validate_args(args)
    def test_invalid_interval_rejected(self):
        args = type("Args", (), dict(interval=0, duration=None, port=None, pid=None))()
        with self.assertRaises(ValueError):
            monitor.validate_args(args)

if __name__ == "__main__":
    unittest.main()
