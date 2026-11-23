# Automated S3 / MinIO Backup Rotator & Integrity Verifier

A single-file CLI utility for creating compressed backups, encrypting them with AES-256-GCM, uploading to S3-compatible storage, validating selected (or all) authenticated chunks through ranged downloads, and applying retention.

## Features
- Tar + gzip archive; repeatable exclusion globs.
- AES-256-GCM authenticated encryption, with independent authentication tags per 4 MiB chunk so individual S3 Range downloads can be verified.
- Random sample verification or full post-upload verification. Checks GCM authentication and plaintext SHA-256 for each selected chunk.
- S3 and MinIO support, custom endpoint/region, TLS validation controls.
- Backup manifest sidecar with chunk offsets, sizes, SHA-256 digests, archive digest, and metadata.
- Retention policy removes older backup objects and matching manifests; retain N newest.
- JSON summary output; logging; no source-directory changes.
- Explicit key management via environment variable or key file.

## Requirements / Install
Python 3.9+ recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Encryption key
Generate a 32-byte key (64 hex characters):
```bash
openssl rand -hex 32
```
Export it securely (do not commit it):
```bash
export BACKUP_AES_KEY='PASTE_64_HEX_CHAR_KEY'
```
Or place the hex key in a protected file and use `--key-file`. Keep the key outside object storage and backups; losing it means data cannot be decrypted. Key file permissions should be restrictive (e.g. chmod 600).

## AWS S3 example
Set credentials through the standard environment variables `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (or use an IAM role):
```bash
python backup_rotator.py --source /etc --bucket my-backups --name config   --prefix servers/web01 --retention 14 --sample-chunks 5
```

## MinIO example
```bash
export AWS_ACCESS_KEY_ID='minio-user'
export AWS_SECRET_ACCESS_KEY='YOUR_SECRET'
python backup_rotator.py --source /srv/app --bucket backups --endpoint https://minio.example:9000   --region us-east-1 --name appdata --prefix prod/app --full-verify --retention 10
```

## Useful options
- `--exclude '*.cache'` (repeatable; glob matching on tar member names)
- `--sample-chunks 5` random chunks checked after upload
- `--full-verify` verifies every chunk; overrides sampling
- `--retention 0` disables cleanup (default keeps 7 backups)
- `--no-tls` disables HTTPS (avoid outside isolated testing)
- `--insecure-tls` disables certificate validation (unsafe; testing only)
- `--verbose` enables debug logs

Run help: `python backup_rotator.py --help`

## Restore / format note
The backup object uses a documented custom chunked AES-GCM framing format (`S3BRG01`) and a sidecar JSON manifest. This initial version focuses on backup, upload, and integrity verification; it does **not yet provide a restore/decrypt command**. Treat manifests as operationally important and protect them from unauthorized changes. A SHA-256 digest in the manifest is not a digital signature; use bucket versioning, restrictive IAM, Object Lock, or a signed manifest if tamper resistance is required.

## Security and operational cautions
- AES-GCM authenticates each chunk, and the manifest checksum validates decrypted chunk bytes during verification.
- Sample mode verifies only the sampled chunks; it does not prove the entire object is intact. Use `--full-verify` for complete chunk-level verification.
- Credentials should be supplied by environment, IAM, or a secure credential provider—not embedded in scripts.
- Do not use `--insecure-tls` in production. Prefer TLS and CA trust configuration.
- Test restore procedures in a separate environment before relying on backups.
