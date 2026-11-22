#!/usr/bin/env python3
"""Audit TLS certificates on explicitly supplied network ranges."""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import ipaddress
import json
import logging
import socket
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.x509.oid import ExtensionOID
except ImportError:
    x509 = hashes = ExtensionOID = None

try:
    from rich.console import Console
    from rich.table import Table
except ImportError:
    Console = Table = None

LOG = logging.getLogger("certificate_auditor")
CONSOLE = Console() if Console else None
DEFAULT_PORTS = (443, 636, 8443)
FIELDS = [
    "timestamp_utc", "target", "port", "status", "subject", "issuer",
    "serial_number", "not_before_utc", "not_after_utc", "days_remaining",
    "san_dns", "san_ip", "san_count", "san_status", "hostname_match",
    "chain_trusted", "tls_version", "cipher", "sha256_fingerprint", "error",
]


def utc_now():
    return datetime.now(timezone.utc)


def parse_networks(values):
    networks = []
    for value in values:
        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError as exc:
            raise ValueError(f"Invalid network '{value}': {exc}") from exc
    if not networks:
        raise ValueError("Provide at least one --subnet.")
    return networks


def expand_targets(networks, max_hosts):
    targets = set()
    for network in networks:
        # Avoid accidental enumeration of enormous ranges.
        if network.num_addresses > max_hosts:
            raise ValueError(
                f"{network} contains {network.num_addresses} addresses; "
                f"limit is {max_hosts}. Narrow the CIDR or raise --max-hosts deliberately."
            )
        targets.update(str(address) for address in network.hosts())
        if len(targets) > max_hosts:
            raise ValueError(f"Combined target count exceeds --max-hosts ({max_hosts}).")
    return sorted(targets, key=lambda item: (ipaddress.ip_address(item).version,
                                             int(ipaddress.ip_address(item))))


def parse_ports(values):
    ports = []
    for value in values:
        try:
            port = int(value)
        except ValueError as exc:
            raise ValueError(f"Invalid port: {value}") from exc
        if not 1 <= port <= 65535:
            raise ValueError(f"Port must be between 1 and 65535: {port}")
        if port not in ports:
            ports.append(port)
    return ports


def extract_certificate(der_bytes, target, port, timestamp, tls_version, cipher):
    if x509 is None:
        raise RuntimeError("Missing dependency: install with python -m pip install -r requirements.txt")
    cert = x509.load_der_x509_certificate(der_bytes)
    try:
        san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
        dns_names = sorted(set(san_ext.get_values_for_type(x509.DNSName)))
        ip_names = sorted(str(value) for value in san_ext.get_values_for_type(x509.IPAddress))
        uri_names = sorted(set(san_ext.get_values_for_type(x509.UniformResourceIdentifier)))
        email_names = sorted(set(san_ext.get_values_for_type(x509.RFC822Name)))
        san_present = True
    except x509.ExtensionNotFound:
        dns_names, ip_names, uri_names, email_names = [], [], [], []
        san_present = False

    now = utc_now()
    not_before = cert.not_valid_before_utc
    not_after = cert.not_valid_after_utc
    days_remaining = (not_after - now).total_seconds() / 86400
    is_expired = now > not_after
    not_yet_valid = now < not_before
    address = ipaddress.ip_address(target)
    # For IP-based scans, identity must be represented by an iPAddress SAN.
    # DNS SANs are checked when an explicit expected DNS name is supplied.
    if address:
        identity_match = str(address) in ip_names
    else:
        identity_match = False

    san_problems = []
    if not san_present:
        san_problems.append("missing SAN extension")
    if not dns_names and not ip_names:
        san_problems.append("no DNS/IP SAN entries")
    if len(dns_names) != len(set(dns_names)) or len(ip_names) != len(set(ip_names)):
        san_problems.append("duplicate SAN entries")
    san_status = "INVALID" if san_problems else "PRESENT"

    subject = cert.subject.rfc4514_string()
    issuer = cert.issuer.rfc4514_string()
    fingerprint = cert.fingerprint(hashes.SHA256()).hex(":")
    statuses = []
    if is_expired:
        statuses.append("EXPIRED")
    elif days_remaining <= 30:
        statuses.append("EXPIRING_SOON")
    if not_yet_valid:
        statuses.append("NOT_YET_VALID")
    if san_status == "INVALID":
        statuses.append("INVALID_SAN")
    if not identity_match:
        statuses.append("IP_SAN_MISMATCH")
    if not statuses:
        statuses.append("OK")

    return {
        "timestamp_utc": timestamp, "target": target, "port": port,
        "status": "|".join(statuses), "subject": subject, "issuer": issuer,
        "serial_number": format(cert.serial_number, "X"),
        "not_before_utc": not_before.isoformat(), "not_after_utc": not_after.isoformat(),
        "days_remaining": round(days_remaining, 2),
        "san_dns": ";".join(dns_names), "san_ip": ";".join(ip_names),
        "san_count": len(dns_names) + len(ip_names) + len(uri_names) + len(email_names),
        "san_status": san_status, "hostname_match": identity_match,
        "chain_trusted": "NOT_CHECKED", "tls_version": tls_version or "",
        "cipher": cipher or "", "sha256_fingerprint": fingerprint, "error": "; ".join(san_problems),
    }


def scan_endpoint(target, port, timeout, expected_name=None, verify_chain=True):
    timestamp = utc_now().isoformat(timespec="seconds")
    result = {"timestamp_utc": timestamp, "target": target, "port": port,
              "status": "UNREACHABLE", "subject": "", "issuer": "", "serial_number": "",
              "not_before_utc": "", "not_after_utc": "", "days_remaining": "",
              "san_dns": "", "san_ip": "", "san_count": 0, "san_status": "UNKNOWN",
              "hostname_match": "NOT_CHECKED", "chain_trusted": "NOT_CHECKED",
              "tls_version": "", "cipher": "", "sha256_fingerprint": "", "error": ""}
    try:
        with socket.create_connection((target, port), timeout=timeout) as raw:
            # Retrieve the presented leaf certificate without suppressing network errors.
            retrieval = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            retrieval.check_hostname = False
            retrieval.verify_mode = ssl.CERT_NONE
            with retrieval.wrap_socket(raw, server_hostname=expected_name or None) as tls:
                der = tls.getpeercert(binary_form=True)
                version = tls.version()
                cipher_info = tls.cipher()
            cert_result = extract_certificate(der, target, port, timestamp, version,
                                               cipher_info[0] if cipher_info else "")
        if verify_chain:
            name = expected_name or target
            try:
                with socket.create_connection((target, port), timeout=timeout) as raw:
                    context = ssl.create_default_context()
                    with context.wrap_socket(raw, server_hostname=name):
                        cert_result["chain_trusted"] = True
                        cert_result["hostname_match"] = True
            except (ssl.SSLCertVerificationError, ssl.CertificateError) as exc:
                cert_result["chain_trusted"] = False
                cert_result["error"] = (cert_result["error"] + "; " if cert_result["error"] else "") + str(exc)
                if "hostname" in str(exc).lower() or "ip address" in str(exc).lower():
                    cert_result["hostname_match"] = False
            except OSError as exc:
                cert_result["chain_trusted"] = False
                cert_result["error"] = (cert_result["error"] + "; " if cert_result["error"] else "") + str(exc)
        if expected_name:
            cert = x509.load_der_x509_certificate(der)
            try:
                san = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
                names = san.get_values_for_type(x509.DNSName)
                ips = [str(v) for v in san.get_values_for_type(x509.IPAddress)]
                cert_result["hostname_match"] = expected_name.casefold() in [n.casefold() for n in names] or expected_name in ips
            except x509.ExtensionNotFound:
                cert_result["hostname_match"] = False
        result.update(cert_result)
        if result["chain_trusted"] is False and "UNTRUSTED_CHAIN" not in result["status"]:
            result["status"] += "|UNTRUSTED_CHAIN"
        if result["hostname_match"] is False and expected_name:
            result["status"] += "|HOSTNAME_MISMATCH"
    except (OSError, ssl.SSLError, TimeoutError, ValueError) as exc:
        result["error"] = str(exc)
    except Exception as exc:
        LOG.debug("Unexpected error for %s:%s: %s", target, port, exc, exc_info=True)
        result["error"] = f"scan error: {exc}"
    return result


def render(records, no_color=False):
    if CONSOLE and not no_color:
        table = Table(title="UNIFIED CERTIFICATE EXPIRY & SAN SCANNER", header_style="bold cyan")
        for name in ("TARGET", "PORT", "STATUS", "DAYS LEFT", "SAN", "CHAIN"):
            table.add_column(name, overflow="fold")
        for row in records:
            table.add_row(row["target"], str(row["port"]), row["status"],
                          str(row["days_remaining"] or "-"), row["san_status"],
                          str(row["chain_trusted"]))
        CONSOLE.print(table)
        return
    print(f"{'TARGET':<40} {'PORT':>5} {'DAYS':>8} {'SAN':<9} {'CHAIN':<7} STATUS")
    print("-" * 120)
    for row in records:
        print(f"{row['target']:<40.40} {row['port']:>5} {str(row['days_remaining'] or '-'):>8} "
              f"{row['san_status']:<9} {str(row['chain_trusted']):<7} {row['status']}")


def export_records(path, fmt, records):
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        target.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Read-only TLS certificate expiry and SAN audit for explicitly authorized subnets.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=("Examples:\n"
                "  python monitor.py --subnet 10.20.0.0/24\n"
                "  python monitor.py --subnet 10.20.1.0/24 --ports 443,636,8443 --workers 32\n"
                "  python monitor.py --subnet 192.0.2.0/28 --expected-name internal.example --json\n"
                "  python monitor.py --subnet 10.20.0.0/24 --output reports/tls.csv --format csv"))
    parser.add_argument("--subnet", action="append", required=True, help="authorized CIDR; repeatable")
    parser.add_argument("--ports", default="443,636,8443", help="comma-separated TCP TLS ports")
    parser.add_argument("--expected-name", help="DNS name expected on each scanned endpoint (for SNI/name validation)")
    parser.add_argument("--timeout", type=float, default=3.0, help="connect/TLS timeout per endpoint")
    parser.add_argument("--workers", type=int, default=32, help="maximum concurrent endpoint checks")
    parser.add_argument("--max-hosts", type=int, default=4096, help="hard cap on expanded target addresses")
    parser.add_argument("--expiry-warning-days", type=int, default=30, help="expiry warning threshold")
    parser.add_argument("--no-chain-check", action="store_true", help="skip OS trust-chain and hostname verification")
    parser.add_argument("--output", help="write complete report to PATH")
    parser.add_argument("--format", choices=("csv", "json"), default="csv")
    parser.add_argument("--json", action="store_true", help="print JSON Lines to stdout")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--version", action="version", version="Unified Certificate Scanner 1.0.0")
    return parser


def validate_args(args):
    if args.timeout <= 0:
        raise ValueError("--timeout must be greater than 0")
    if not 1 <= args.workers <= 256:
        raise ValueError("--workers must be between 1 and 256")
    if args.max_hosts < 1:
        raise ValueError("--max-hosts must be positive")
    if args.expiry_warning_days < 0:
        raise ValueError("--expiry-warning-days cannot be negative")
    if args.expected_name and (len(args.expected_name) > 253 or "/" in args.expected_name):
        raise ValueError("--expected-name must be a DNS name, not a URL or path")


def run(args):
    validate_args(args)
    if x509 is None:
        raise RuntimeError("Missing dependency: install with python -m pip install -r requirements.txt")
    networks = parse_networks(args.subnet)
    targets = expand_targets(networks, args.max_hosts)
    ports = parse_ports(args.ports.split(","))
    jobs = [(host, port) for host in targets for port in ports]
    LOG.info("Scanning %d addresses x %d ports (%d endpoint checks)", len(targets), len(ports), len(jobs))
    started = time.monotonic()
    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(scan_endpoint, host, port, args.timeout, args.expected_name,
                               not args.no_chain_check) for host, port in jobs]
        for future in concurrent.futures.as_completed(futures):
            records.append(future.result())
    records.sort(key=lambda row: (ipaddress.ip_address(row["target"]).version,
                                  int(ipaddress.ip_address(row["target"])), row["port"]))
    if args.json:
        for record in records:
            print(json.dumps(record, ensure_ascii=False))
    else:
        render(records, args.no_color)
        counts = {}
        for row in records:
            for status in row["status"].split("|"):
                counts[status] = counts.get(status, 0) + 1
        print(f"\nTargets: {len(targets)} | Checks: {len(records)} | "
              f"Elapsed: {time.monotonic()-started:.1f}s | "
              f"Expired: {counts.get('EXPIRED', 0)} | Expiring soon: {counts.get('EXPIRING_SOON', 0)} | "
              f"Invalid SAN: {counts.get('INVALID_SAN', 0)}")
    if args.output:
        export_records(args.output, args.format, records)
        LOG.info("Report written to %s", Path(args.output).expanduser())
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")
    try:
        return run(args)
    except (ValueError, RuntimeError, OSError) as exc:
        LOG.error("%s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
