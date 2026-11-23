# Multi-Node Latency & Packet Loss Mesh

A lightweight, cross-platform (Linux and Windows) Python network-mesh monitor. Uses TCP connection timing and UDP echo probes (no ICMP/ping dependency), displays node online/offline state, packet loss, average/min/max latency, and jitter, with CSV/JSON export.

## Features
- TCP connect latency and UDP round-trip latency
- Packet loss percentages, min/avg/max, and jitter (population standard deviation)
- Concurrent checks for quick mesh snapshots
- Add/remove/enable/disable nodes without editing the script
- Readable terminal status table, CSV and JSON reports
- Standard library only; Python 3.9+
- Lightweight agent with UDP echo responder and TCP listener
- Explicit timeouts and configurable concurrency

## Quick start
```bash
python multi_node_latency_mesh.py init
# edit nodes.json with actual hostnames/IPs
python multi_node_latency_mesh.py list
```

## Install the agent on every monitored server
Copy this script to each Linux or Windows node and run:

```bash
python multi_node_latency_mesh.py agent --bind 0.0.0.0 --udp-port 9999 --tcp-port 2222
```

Allow inbound TCP 2222 and UDP 9999 only from your monitoring network in the host firewall. The agent's TCP listener measures connect latency; UDP listener echoes only packets bearing the LATMESH marker. Use a dedicated trusted monitoring VLAN/network.

## Manage nodes
```bash
python multi_node_latency_mesh.py add dc1 10.0.0.11 --tcp-port 2222 --udp-port 9999
python multi_node_latency_mesh.py remove dc1
python multi_node_latency_mesh.py disable dc1
python multi_node_latency_mesh.py enable dc1
python multi_node_latency_mesh.py list
```

Nodes are stored in `nodes.json`. Back it up and keep the file readable only by trusted administrators.

## Run mesh checks and reports
```bash
# TCP only
python multi_node_latency_mesh.py mesh --protocol tcp --tries 8 --timeout 1.2
# UDP only
python multi_node_latency_mesh.py mesh --protocol udp
# Both (default)
python multi_node_latency_mesh.py mesh --protocol both --format json --output reports/snapshot.json
```

Output columns include online/offline status, loss, average/min/max RTT-like latency and jitter. TCP checks require the agent TCP port reachable; UDP checks require the UDP echo agent. A node is ONLINE when at least one probe succeeds.

## Security and operational notes
- This is active network measurement. Run only against systems/networks you own or are authorized to monitor.
- The agent has no authentication in this initial version. Restrict listener ports using firewall rules to trusted monitoring hosts/network segments; do not expose them to the Internet.
- TCP latency is connection-establishment timing, not ICMP RTT. UDP echo RTT depends on network and host scheduling.
- Use a dedicated service account, managed firewall rules, and an allowlist. Consider TLS/mTLS, signed probe tokens, retention policy, alerting, and agent service supervision for production deployments.
- Results are snapshots, not a continuous time-series database.

## CLI reference
Run `python multi_node_latency_mesh.py --help`, or append `--help` to any subcommand.
