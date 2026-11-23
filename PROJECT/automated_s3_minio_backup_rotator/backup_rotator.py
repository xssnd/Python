#!/usr/bin/env python3
"""
Automated S3/MinIO Backup Rotator & Integrity Verifier
Create tar.gz archives, encrypt using AES-256-GCM per independently-authenticated
chunk, upload to S3-compatible storage, verify random/full chunks using Range GET,
and rotate old backups. Read-only to source directories.
"""
from __future__ import annotations
import argparse, hashlib, json, logging, os, random, struct, sys, tarfile, tempfile, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import boto3
    from botocore.exceptions import ClientError
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError as exc:
    print(f"Missing dependency: {exc}. Install with: pip install -r requirements.txt", file=sys.stderr)
    raise SystemExit(2)

MAGIC = b"S3BRG01\0"
HEADER = MAGIC + struct.pack(">I", 4 * 1024 * 1024)  # 4 MiB authenticated chunks
CHUNK_SIZE = 4 * 1024 * 1024
NONCE_SIZE = 12
TAG_SIZE = 16
LOG = logging.getLogger("backup_rotator")

def load_key(path: Path | None, env_name: str) -> bytes:
    raw = os.environ.get(env_name)
    if path:
        try: raw = path.read_text().strip()
        except OSError as e: raise RuntimeError(f"Cannot read key file: {e}") from e
    if not raw: raise RuntimeError(f"Set {env_name} or provide --key-file")
    try: key = bytes.fromhex(raw)
    except ValueError as e: raise RuntimeError("Encryption key must be hex-encoded") from e
    if len(key) != 32: raise RuntimeError("AES-256 key must be exactly 32 bytes (64 hex chars)")
    return key

def build_archive(source: Path, archive_path: Path, excludes: list[str]) -> dict[str, Any]:
    if not source.is_dir(): raise RuntimeError(f"Source directory does not exist: {source}")
    digest = hashlib.sha256()
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(source, arcname=source.name, filter=lambda info: None if any(
            Path(info.name).match(p) for p in excludes) else info)
    with archive_path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""): digest.update(block)
    return {"archive_sha256": digest.hexdigest(), "archive_bytes": archive_path.stat().st_size}

def encrypt_chunks(src: Path, dest: Path, key: bytes) -> dict[str, Any]:
    aes = AESGCM(key); chunks=[]; index=0
    with src.open("rb") as inp, dest.open("wb") as out:
        out.write(HEADER); offset=len(HEADER)
        while True:
            plain=inp.read(CHUNK_SIZE)
            if not plain: break
            nonce=os.urandom(NONCE_SIZE)
            ciphertext=aes.encrypt(nonce, plain, struct.pack(">Q", index))
            frame=nonce+ciphertext
            out.write(struct.pack(">I",len(frame))); out.write(frame)
            chunks.append({"index":index,"offset":offset,"frame_length":4+len(frame),
                          "plain_length":len(plain),"sha256":hashlib.sha256(plain).hexdigest()})
            offset+=4+len(frame); index+=1
    return {"format":"S3BRG01","chunk_size":CHUNK_SIZE,"chunks":chunks,
            "encrypted_bytes":dest.stat().st_size}

def make_s3(args):
    session=boto3.session.Session()
    return session.client("s3", endpoint_url=args.endpoint or None,
        region_name=args.region or None, aws_access_key_id=args.access_key or None,
        aws_secret_access_key=args.secret_key or None, use_ssl=not args.no_tls,
        verify=not args.insecure_tls)

def verify_chunks(s3, bucket: str, object_key: str, manifest: dict, key: bytes,
                 sample: int, full: bool) -> dict[str, Any]:
    chunks=manifest["chunks"]
    selected=list(range(len(chunks))) if full else sorted(set(
        random.sample(range(len(chunks)), min(sample, len(chunks))))) if chunks else []
    aes=AESGCM(key); verified=0
    for i in selected:
        item=chunks[i]
        start=item["offset"]; end=start+item["frame_length"]-1
        response=s3.get_object(Bucket=bucket, Key=object_key, Range=f"bytes={start}-{end}")
        raw=response["Body"].read()
        if len(raw)!=item["frame_length"]: raise RuntimeError(f"Chunk {i}: incomplete range response")
        frame_len=struct.unpack(">I",raw[:4])[0]
        if frame_len != len(raw)-4: raise RuntimeError(f"Chunk {i}: frame length mismatch")
        nonce=raw[4:4+NONCE_SIZE]; cipher=raw[4+NONCE_SIZE:]
        try: plain=aes.decrypt(nonce,cipher,struct.pack(">Q",item["index"]))
        except Exception as e: raise RuntimeError(f"Chunk {i}: AES-GCM authentication failed") from e
        if hashlib.sha256(plain).hexdigest()!=item["sha256"]:
            raise RuntimeError(f"Chunk {i}: plaintext checksum mismatch")
        verified+=1
    return {"verified_chunks":verified,"total_chunks":len(chunks),"full_verification":full,
            "verified_percent":round(verified*100/len(chunks),2) if chunks else 100.0}

def upload_backup(args) -> None:
    key=load_key(args.key_file,args.key_env); s3=make_s3(args)
    prefix=args.prefix.strip("/")
    timestamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_name=f"{args.name}-{timestamp}.tar.gz.aesgcm"
    object_key=f"{prefix+'/'+backup_name if prefix else backup_name}"
    with tempfile.TemporaryDirectory(prefix="s3-backup-") as td:
        archive=Path(td)/"backup.tar.gz"; encrypted=Path(td)/"backup.enc"
        LOG.info("Creating archive from %s",args.source)
        archive_info=build_archive(args.source,archive,args.exclude)
        manifest=encrypt_chunks(archive,encrypted,key)
        manifest.update(archive_info); manifest.update({"created_utc":timestamp,"source":str(args.source),
          "object_key":object_key,"cipher":"AES-256-GCM (independent authenticated chunks)"})
        s3.upload_file(str(encrypted),args.bucket,object_key,ExtraArgs={"Metadata":{
            "backup-format":"s3brg01","created-utc":timestamp,"archive-sha256":archive_info["archive_sha256"]}})
        manifest_key=object_key+".manifest.json"
        s3.put_object(Bucket=args.bucket,Key=manifest_key,Body=json.dumps(manifest,indent=2).encode(),
                      ContentType="application/json")
        LOG.info("Uploaded %s (%s bytes)",object_key,encrypted.stat().st_size)
        result=verify_chunks(s3,args.bucket,object_key,manifest,key,args.sample_chunks,args.full_verify)
        LOG.info("Integrity check: %s",result)
        if args.retention > 0:
            rotate(s3,args.bucket,prefix,args.name,args.retention)
        print(json.dumps({"status":"success","bucket":args.bucket,"object":object_key,
             "manifest":manifest_key,"archive_sha256":archive_info["archive_sha256"],
             "verification":result},indent=2))

def rotate(s3,bucket,prefix,name,keep):
    pfx=(prefix+"/" if prefix else "")+name+"-"
    objects=[]
    paginator=s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket,Prefix=pfx):
        for obj in page.get("Contents",[]):
            if obj["Key"].endswith(".tar.gz.aesgcm"): objects.append(obj)
    objects.sort(key=lambda o:o["LastModified"],reverse=True)
    for obj in objects[keep:]:
        LOG.info("Retention: deleting %s",obj["Key"])
        s3.delete_object(Bucket=bucket,Key=obj["Key"])
        s3.delete_object(Bucket=bucket,Key=obj["Key"]+".manifest.json")

def main():
    p=argparse.ArgumentParser(description="Encrypted S3/MinIO backup, chunk integrity verifier, and retention rotator")
    p.add_argument("--source",type=Path,required=True,help="Directory to back up")
    p.add_argument("--bucket",required=True); p.add_argument("--name",default="backup",help="Object filename prefix")
    p.add_argument("--prefix",default="",help="Object key prefix")
    p.add_argument("--endpoint",help="S3 endpoint URL, e.g. https://minio.example:9000")
    p.add_argument("--region",default="us-east-1")
    p.add_argument("--access-key",default=os.getenv("AWS_ACCESS_KEY_ID"))
    p.add_argument("--secret-key",default=os.getenv("AWS_SECRET_ACCESS_KEY"))
    p.add_argument("--key-file",type=Path,help="File containing 64-char AES key hex")
    p.add_argument("--key-env",default="BACKUP_AES_KEY",help="Environment variable name for key")
    p.add_argument("--exclude",action="append",default=[],help="Tar path glob to exclude (repeatable)")
    p.add_argument("--sample-chunks",type=int,default=3,help="Random chunks to verify (default 3)")
    p.add_argument("--full-verify",action="store_true",help="Verify all encrypted chunks after upload")
    p.add_argument("--retention",type=int,default=7,help="Keep newest N backups; 0 disables rotation")
    p.add_argument("--no-tls",action="store_true",help="Disable TLS (not recommended)")
    p.add_argument("--insecure-tls",action="store_true",help="Skip TLS certificate validation (unsafe)")
    p.add_argument("--verbose",action="store_true")
    args=p.parse_args()
    if args.sample_chunks<0 or args.retention<0: p.error("sample-chunks and retention must be non-negative")
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
      format="%(asctime)s %(levelname)s %(message)s")
    try: upload_backup(args)
    except (RuntimeError,ClientError,OSError,ValueError) as e:
        LOG.error("%s",e); return 1
    return 0
if __name__=="__main__": raise SystemExit(main())
