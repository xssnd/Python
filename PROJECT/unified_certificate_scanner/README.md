# Unified Certificate Expiry & SAN Scanner

A read-only Python CLI that audits TLS certificates on explicitly supplied IPv4/IPv6 CIDR ranges and selected TCP ports. It highlights expired/near-expiry certificates, missing or empty SAN extensions, IP SAN mismatches, hostname mismatches, and trust-chain failures.

## Features

- Scan one or more explicitly authorized IPv4/IPv6 CIDR subnets.
- Default ports: **443, 636 (LDAPS), and 8443**; customize the TCP port list.
- Bounded concurrent checks, per-connection timeout, and a hard host-count safety cap.
- Extract subject, issuer, serial number, validity window, remaining days, SAN DNS/IP values, and SHA-256 fingerprint.
- Detect expired, not-yet-valid, and configurable soon-to-expire certificates.
- Flag missing/empty SAN extensions and IP SAN mismatch when scanning by IP address.
- Optional expected DNS name for SNI, DNS SAN matching, and hostname verification.
- Validate the certificate chain against the host operating system trust store by default; use `--no-chain-check` to skip.
- Rich terminal table when installed, with plain-text fallback.
- JSON Lines stdout plus complete JSON or CSV report export.
- Input validation, logging, non-zero exit on configuration/dependency errors, and no third-party scanner binary.
- Read-only: it only opens TCP connections and performs TLS handshakes; it does not exploit services, authenticate, modify hosts, or change certificates.

## Requirements

- Python 3.10+
- `cryptography` (required for certificate/SAN parsing)
- `rich` (optional terminal formatting)

## Installation

```bash
cd PROJECT/unified_certificate_scanner
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
```

## Usage

Only scan address ranges you own or are explicitly authorized to assess.

```bash
# Scan the default ports 443, 636, and 8443
python monitor.py --subnet 10.20.0.0/24

# Multiple subnets and custom ports
python monitor.py --subnet 10.20.0.0/24 --subnet 10.30.1.0/28 --ports 443,8443

# Supply the expected DNS identity for SNI and hostname validation
python monitor.py --subnet 10.20.0.0/24 --expected-name app.internal.example

# Tune concurrency, timeout, and expiry warning threshold
python monitor.py --subnet 10.20.0.0/24 --workers 16 --timeout 5 --expiry-warning-days 45

# Machine-readable output
python monitor.py --subnet 10.20.0.0/24 --json
python monitor.py --subnet 10.20.0.0/24 --output reports/certificates.csv --format csv
python monitor.py --subnet 10.20.0.0/24 --output reports/certificates.json --format json

# Skip trust-chain verification (leaf certificate and SAN inspection still run)
python monitor.py --subnet 10.20.0.0/24 --no-chain-check

python monitor.py --help
```

## CLI options

| Option | Description |
|---|---|
| `--subnet CIDR` | Authorized subnet; repeatable and required |
| `--ports LIST` | Comma-separated TCP ports (default: 443,636,8443) |
| `--expected-name DNS` | Expected DNS identity and SNI name for each endpoint |
| `--timeout SECONDS` | Per-connection timeout |
| `--workers N` | Concurrent checks (1–256) |
| `--max-hosts N` | Hard cap on expanded addresses (default: 4096) |
| `--expiry-warning-days N` | Expiry warning threshold (default: 30) |
| `--no-chain-check` | Skip OS trust-chain and hostname verification |
| `--output PATH` | Save a full CSV or JSON report |
| `--format csv/json` | Report format |
| `--json` | Emit JSON Lines to stdout |
| `--no-color` | Disable Rich formatting |
| `--verbose` | Enable debug logging |

## Status interpretation

- `EXPIRED`: current UTC time is later than the certificate's not-after timestamp.
- `EXPIRING_SOON`: remaining validity is within the configured warning window.
- `NOT_YET_VALID`: current UTC time is earlier than not-before.
- `INVALID_SAN`: SAN extension is missing or contains no DNS/IP identity entries.
- `IP_SAN_MISMATCH`: the scanned IP address is not present as an iPAddress SAN. This is expected for name-based virtual hosting unless the intended DNS name is supplied.
- `HOSTNAME_MISMATCH`: explicit `--expected-name` does not match DNS/IP SAN or platform hostname verification fails.
- `UNTRUSTED_CHAIN`: the OS trust store rejected the presented chain or identity.
- `UNREACHABLE`: TCP connect or TLS handshake failed; inspect the error field.

The scanner does not treat a DNS SAN as equivalent to an IP SAN. If services use SNI/virtual hosting, provide `--expected-name` for the intended DNS identity. One expected name applies to every scanned endpoint; use separate runs for different virtual-host names.

## Safety and limitations

- CIDR expansion is bounded by `--max-hosts`; large ranges require deliberate opt-in by raising the limit.
- Only the specified TCP ports are contacted. The scanner does not perform UDP scans, service exploitation, authentication, or certificate remediation.
- Trust verification depends on the local machine's CA bundle and clock. A private PKI may appear untrusted until its CA is installed in the system trust store.
- The scanner retrieves the presented leaf certificate and does not perform full revocation checking (OCSP/CRL), CT log auditing, or intermediate-chain inventory.
- On multi-tenant TLS services, a single IP may serve multiple certificates. Run separate scans with the relevant expected DNS names.
- Reports contain internal hostnames, addresses, certificate subjects, and fingerprints; store and share them appropriately.

## Tests

```bash
python -m unittest discover -s tests -v
```

