# Database Connection Pool Exhaustion Monitor

A cross-platform Python CLI that watches established client TCP connections to PostgreSQL, MySQL, and Microsoft SQL Server and (when optional database drivers and credentials are supplied) queries live connection usage against the database connection limit. Warns before exhaustion and supports JSON, CSV history, periodic monitoring, and webhooks.

## Features

- **OS-level socket count:** uses Linux `ss`, `netstat` on Windows/Unix, or optional `psutil` fallback. Counts established TCP connections to a selected endpoint.
- **Database-aware metrics (optional):** reports live connection/session count and configured limit for PostgreSQL, MySQL, and MSSQL using read-only queries.
- **Threshold alerts:** configurable warning/critical percentages; alerts only when status transitions to a new warning state.
- **Monitoring mode:** polling interval and duration; use duration `0` for continuous monitoring.
- **Outputs:** terminal dashboard or JSON, append-only CSV log, optional HTTP webhook POST.
- **Config file + CLI overrides:** JSON config supported; command-line values take precedence.
- **Credential hygiene:** password can be supplied via `DBMON_PASSWORD` environment variable; avoid passing secrets in command-line args.
- **Graceful degraded mode:** OS socket count still available if DB driver, credentials, or privileges are unavailable.
- **Cross-platform:** Linux, macOS, and Windows; some socket ownership or counts may require elevated privileges.

> OS socket counts are a client-side indicator and are not a direct measure of database server-wide connections or a specific connection pool's configured capacity. DB queries provide the server-level context. The monitor does not inspect pool internals (for example, application pool size) unless those are instrumented separately.

## Requirements

- Python 3.10+
- OS tools: `ss` (preferred on Linux) or `netstat`; optional `psutil`
- Optional DB drivers:
  - PostgreSQL: `psycopg[binary]`
  - MySQL: `mysql-connector-python`
  - MSSQL: `pymssql`

Install dependencies for the database engine you monitor:

```bash
python -m pip install -r requirements.txt
# Or just one driver:
python -m pip install "psycopg[binary]"
python -m pip install mysql-connector-python
python -m pip install pymssql
```

## Quick start

### OS socket-only check (no DB driver/credentials required)

```bash
python monitor.py --host 10.0.0.20 --db-type postgresql
```

### Database metrics

Set credentials through environment variables and run the query:

```bash
export DBMON_USER="monitor_user"
export DBMON_PASSWORD="your-secret"
python monitor.py --db-type postgresql --host 10.0.0.20 --database postgres
```

Use read-only/least-privilege accounts. PostgreSQL visibility depends on grants; MySQL needs permission to read status variables; MSSQL queries may require permissions to see session metadata.

### Live monitoring + CSV history

```bash
python monitor.py --host 127.0.0.1 --db-type postgresql --watch --interval 15 --csv ./logs/db-connections.csv
```

Continuous monitoring runs until Ctrl+C unless `--duration` is set.

### JSON output

```bash
python monitor.py --host db.example.net --db-type mysql --json
```

### Webhook alerts

```bash
python monitor.py --host 10.0.0.20 --db-type mysql --watch --webhook https://hooks.example.invalid/monitor
```

Webhook receives a JSON payload when the status enters WARNING or CRITICAL. Keep webhook URLs secret and use HTTPS.

## Configuration

Copy `config.example.json` to `config.json`, then edit:

```json
{
  "db_type": "postgresql",
  "host": "127.0.0.1",
  "port": 5432,
  "database": "postgres",
  "username": "monitor_user",
  "warning": 75,
  "critical": 90,
  "interval": 30,
  "duration": 0,
  "csv": "logs/db-connections.csv"
}
```

CLI arguments override configuration values. Password may be provided as `DBMON_PASSWORD`.

## Thresholds & exit codes

- `OK`: below warning threshold.
- `WARNING`: at/above warning percentage.
- `CRITICAL`: at/above critical percentage.
- `UNKNOWN`: database metrics unavailable; socket count is still displayed when detectable.

Exit code: `0` OK or completed monitoring duration; `1` UNKNOWN/error; `2` WARNING/CRITICAL for single check; `130` interrupted.

## Database-specific notes

- PostgreSQL uses `pg_stat_activity` and `pg_settings.max_connections`.
- MySQL uses `Threads_connected` and `max_connections`.
- MSSQL uses `sys.dm_exec_sessions`, `sys.configurations`, and `@@MAX_CONNECTIONS`. Depending on version and permissions, values may represent different session or server limits.

The OS socket count is for connections from the monitored machine to the target address/port, while DB statistics are server-side and may include other clients. Treat them as complementary measurements.

## Safety / limitations

- Read-only queries only; no database settings or services are changed.
- Socket parsing is best-effort and can miss sockets when OS output format differs or access is restricted.
- Database maximums and session counts have engine-specific semantics; verify thresholds for your workload.
- This tool is a monitoring aid, not a substitute for app-side pool metrics (pool active/idle/waiting, acquisition latency, timeout count). For accurate pool exhaustion analysis, instrument application pool telemetry.

## License

See repository license.
