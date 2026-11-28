# SMB/NFS Share Permission Auditor

Read-only CLI for auditing **already-mounted** SMB/CIFS and NFS shares on Linux. It flags risky Unix permissions, world-writable files/directories, sensitive-looking files exposed to world-read, group-write on sensitive files, and optionally visible ACL entries via `getfacl`.

> This is a mounted-filesystem auditor, not a server-side ACL enumerator. Mounted CIFS/NFS permissions may be synthesized or constrained by mount options and server policies. It cannot conclusively identify Windows `Everyone` / `Authenticated Users`, SMB share-level permissions, NFS export policy, or inheritance. Run server-native audits for authoritative ACLs.

## Features

- Auto-detect mounted network filesystems (CIFS/SMB, NFS/NFS4, SSHFS) and display mount metadata.
- Scan selected mount paths or multiple mounts in one run.
- Detect exact mode `777`, world-writable objects, sensitive-looking world-readable files, and group-writable sensitive files.
- Sensitive-file heuristics for keys, secrets, credentials, environment/config, database and backup extensions.
- Optional `getfacl` checks for visible named ACL entries (Linux; installed ACL utility recommended).
- Human-readable report plus JSON/CSV exports for automation and SIEM ingestion.
- Owner UID/GID, mode, file type and size in findings.
- Skip directory names, skip hidden files, file-count limit, error/warning capture.
- Read-only, no permission changes, no network probes, no remote credential handling.
- Exit status: `1` when HIGH/CRITICAL findings occur, otherwise `0`; invalid paths and scan errors are included in the report.

## Requirements

- Python 3.9+
- Linux recommended for mount detection.
- Optional `getfacl` utility (`acl` package on Debian/Ubuntu; `acl` on many other distributions).

No third-party Python dependencies.

## Usage

List detected network mounts:

```bash
python3 auditor.py
```

Scan one or more mounted shares:

```bash
python3 auditor.py /mnt/team-share /mnt/nfs-data
```

Export JSON or CSV:

```bash
python3 auditor.py /mnt/team-share --format json --output audit.json
python3 auditor.py /mnt/team-share --format csv --output findings.csv
```

Limit scanning and skip noisy folders:

```bash
python3 auditor.py /mnt/team-share --max-files 50000 --skip-dir .git --skip-dir node_modules
python3 auditor.py /mnt/team-share --no-hidden
```

## Permission interpretation

- `777`: owner, group and others have read/write/execute. Flagged HIGH.
- World-writable: `other` has write bit. HIGH if sensitive heuristic matches; otherwise MEDIUM.
- Sensitive world-readable: HIGH.
- Sensitive group-writable: HIGH.
- Visible ACL write entries: MEDIUM/HIGH depending on sensitive-name/type heuristic.

The sensitive-file heuristic is intentionally broad and may produce false positives. Review every finding in context. Access checks are not performed and file contents are never read.

## Safe operational practices

1. Start with read-only credentials and a narrowly scoped mount.
2. Scan a small directory first and validate the results.
3. Avoid placing reports in the share being scanned; use a local protected directory.
4. Treat reports as sensitive because they contain paths and ownership metadata.
5. Confirm findings on the file server using native ACL tools.

## Limitations

- Unix mode bits are only a partial view of SMB ACLs and NFS export controls.
- `getfacl` output can vary by filesystem and ACL implementation; remote ACL visibility is not guaranteed.
- File names/extensions are heuristics; content is not inspected.
- Symlinks are not followed during traversal.
- No remediation or permission-changing mode is included by design.

## License

Use under the repository's applicable license.
