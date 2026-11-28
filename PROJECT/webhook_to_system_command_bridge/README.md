# Webhook-to-System-Command Bridge

A minimal Python HTTP webhook receiver for internal CI/CD automation. It authenticates requests with HMAC-SHA256, timestamps, one-time nonces, and dispatches **only configured action IDs**.

## Security design

- HMAC-SHA256 signature over `timestamp.nonce.raw_body`; compare with constant-time `compare_digest`.
- Timestamp freshness window (5 minutes) and SQLite nonce replay protection.
- Strict JSON body limit (64 KiB); no arbitrary command, shell, or command arguments accepted from webhook payload.
- Allowlisted action identifiers mapped to fixed argv arrays in administrator-owned config.
- `subprocess.run(..., shell=False)` (shell is never invoked); timeout per action.
- Concurrent-action cap, disable switch per action, audit trail in SQLite, bounded output.
- Localhost default binding. For remote CI, put behind TLS reverse proxy, firewall allowlist, and preferably VPN/private network.
- Minimal `/health` endpoint; other paths return 404.

> This bridge can execute privileged commands by design. Run as a dedicated low-privilege account and grant narrowly scoped sudo rules only for exact commands. Never expose it directly to the public internet.

## Requirements

- Python 3.9+
- Linux (systemd actions shown in example; Python server itself is portable)
- No third-party Python dependencies

## Quick start

1. Copy files:
   ```bash
   cp config.example.json config.json
   ```
2. Generate a 32-byte+ secret and store it in environment (do not put it in the config file):
   ```bash
   export WEBHOOK_BRIDGE_CI_PROD_SECRET="$(openssl rand -hex 32)"
   ```
3. Edit `config.json`: set allowlisted actions to your own scripts/services. Keep each command as an argv array. Validate paths and file ownership.
4. Start locally:
   ```bash
   python3 webhook_bridge.py --config config.json
   ```
5. Health check:
   ```bash
   curl -s http://127.0.0.1:9080/health
   ```

## Request format

Only `action` and optional `request_id` are accepted in JSON. The server does not accept command strings, shell snippets, or arbitrary parameters.

```json
{"action":"restart-nginx","request_id":"build-381"}
```

Headers:
- `X-Webhook-Key`: configured key ID (example `ci-prod`)
- `X-Webhook-Timestamp`: Unix epoch seconds
- `X-Webhook-Nonce`: random unique token (16–128 chars; letters/digits/`_`/`-`)
- `X-Webhook-Signature`: lowercase or uppercase hex HMAC-SHA256

Signature input: `timestamp + "." + nonce + "." + raw_request_body`, HMAC key is the secret string from the named environment variable.

## Example sender (Python)

```python
import hashlib, hmac, json, secrets, time, urllib.request

secret = b"REPLACE_WITH_SHARED_SECRET"
body = json.dumps({"action": "restart-nginx", "request_id": "job-42"},
                 separators=(",", ":")).encode()
timestamp = str(int(time.time()))
nonce = secrets.token_urlsafe(24)
signature = hmac.new(secret, timestamp.encode() + b"." + nonce.encode() + b"." + body,
                    hashlib.sha256).hexdigest()
req = urllib.request.Request(
    "https://bridge.internal.example/webhook", data=body, method="POST",
    headers={"Content-Type":"application/json", "X-Webhook-Key":"ci-prod",
            "X-Webhook-Timestamp":timestamp, "X-Webhook-Nonce":nonce,
            "X-Webhook-Signature":signature})
print(urllib.request.urlopen(req, timeout=10).read().decode())
```

## Configuration

- `keys`: key ID mapped to an environment-variable name. Multiple CI systems/keys can be configured.
- `actions`: action IDs mapped to exact `argv` lists, optional `cwd`, `timeout` (1–3600s), `enabled`, and limited environment overrides.
- `max_concurrent_actions`: execution concurrency limit.
- `sqlite_path`: nonce and audit database.
- `host`/`port`: listener address. Prefer localhost behind a TLS proxy.

### Sudo hardening example

If the bridge user is `webhook-bridge`, use a sudoers entry limited to the exact service operation, e.g. `/usr/bin/systemctl restart nginx`. Do not grant broad sudo or wildcard command permissions. Validate the executable path on your system (`command -v systemctl`).

## Responses

- `202`: accepted; action runs asynchronously.
- `401`: invalid key/signature/timestamp.
- `403`: action not allowlisted or disabled.
- `409`: replayed nonce.
- `413`: body too large.
- `429`: concurrency limit reached.

## Operational notes

- A 202 means accepted, not that the action succeeded; inspect logs and the SQLite audit records for completion.
- Secrets must be rotated and protected using a secret manager or root-owned environment file.
- Consider systemd hardening (`NoNewPrivileges`, `ProtectSystem`, `ProtectHome`, `PrivateTmp`, `RestrictAddressFamilies`) and reverse proxy request limits.
- Validate webhook payload/signature integration in a staging environment before production use.
