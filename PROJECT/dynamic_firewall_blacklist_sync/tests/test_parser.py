import unittest
from dynamic_firewall_sync import extract_ips, suspicious, eligible
class ParserTests(unittest.TestCase):
 def test_ipv4(self):self.assertEqual(extract_ips("client 203.0.113.4", [r"(?P<ip>[0-9]{1,3}(?:[.][0-9]{1,3}){3})"]),{"203.0.113.4"})
 def test_invalid_ip(self):self.assertEqual(extract_ips("999.999.999.999",[r"(?P<ip>[0-9]{1,3}(?:[.][0-9]{1,3}){3})"]),set())
 def test_signature(self):self.assertTrue(suspicious("FAILED PASSWORD",["failed password"]))
 def test_allowlist_and_public(self):
  self.assertFalse(eligible("10.2.3.4",["10.0.0.0/8"],True))
  self.assertTrue(eligible("8.8.8.8",[],True))
if __name__=="__main__":unittest.main()
