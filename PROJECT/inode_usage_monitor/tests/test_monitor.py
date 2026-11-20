import unittest
import monitor


class MountEscapeTests(unittest.TestCase):
    def test_decode_mount_escapes(self):
        self.assertEqual(monitor.decode_mount_field(r"/mnt/my\040disk"), "/mnt/my disk")


if __name__ == "__main__":
    unittest.main()
