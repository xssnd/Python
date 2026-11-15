import csv, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import monitor

class UptimeLoggerTests(unittest.TestCase):
    def test_local_uptime(self):
        row=monitor.check_local_host(lambda:1000,lambda:1600)
        self.assertEqual(row["host_uptime_seconds"],600); self.assertEqual(row["status"],"UP")
    def test_tcp_success(self):
        with patch("monitor.socket.create_connection") as connect: row=monitor.check_tcp({"host":"localhost","port":80},1)
        self.assertEqual(row["status"],"UP"); connect.assert_called_once()
    def test_tcp_failure(self):
        with patch("monitor.socket.create_connection",side_effect=OSError("refused")): row=monitor.check_tcp({"host":"localhost","port":80},1)
        self.assertEqual(row["status"],"DOWN"); self.assertIn("refused",row["error"])
    def test_csv_appends_single_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"uptime.csv"; row={"timestamp_utc":"now","target":"web","check_type":"http","status":"UP","response_time_ms":1,"http_status":200,"error":"","host_uptime_seconds":""}
            monitor.append_csv(path,[row]); monitor.append_csv(path,[row])
            with path.open(newline="",encoding="utf-8") as f: records=list(csv.DictReader(f))
            self.assertEqual(len(records),2)
    def test_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"uptime.csv"; rows=[]
            for status in ("UP","UP","DOWN","UP"):
                rows.append({"timestamp_utc":"now","target":"api","check_type":"http","status":status,"response_time_ms":"","http_status":"","error":"","host_uptime_seconds":""})
            monitor.append_csv(path,rows); result=monitor.summarize_csv(path)[0]
            self.assertEqual(result["availability_percent"],75.0); self.assertEqual(result["down"],1)
    def test_invalid_port(self):
        with self.assertRaises(ValueError):
            monitor.validate_config({"interval_seconds":60,"timeout_seconds":5,"targets":[{"name":"bad","type":"tcp","host":"localhost","port":70000}]})
    def test_duplicate_names(self):
        t={"name":"web","type":"http","url":"https://example.com"}
        with self.assertRaises(ValueError): monitor.validate_config({"interval_seconds":60,"timeout_seconds":5,"targets":[t,t]})

if __name__=="__main__": unittest.main()
