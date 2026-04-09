"""Upload report files (zip/tar.gz) to S3 and write a small metadata file with the S3 URL.

Usage:
  python3 scripts/upload_reports_to_s3.py /path/to/report.zip my-bucket reports/2026/

Configuration via environment or .env:
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
  S3_BUCKET (optional - can pass bucket as arg)

This script avoids embedding any secrets in the repo. It uses `boto3` and expects
AWS credentials to be provided via environment or an IAM role.
"""
import sys
import os
import hashlib
from datetime import datetime
try:
    import boto3
    from botocore.exceptions import ClientError
except Exception:
    boto3 = None
    ClientError = Exception


def sha256_file(path, chunk_size=8192):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def upload_file(s3_client, file_path, bucket, key):
    try:
        s3_client.upload_file(file_path, bucket, key)
        return True
    except ClientError as e:
        print(f"Upload failed: {e}")
        return False


def main():
    if len(sys.argv) < 3:
        print("Usage: upload_reports_to_s3.py <file_path> <bucket> [s3_prefix]")
        sys.exit(2)

    file_path = sys.argv[1]
    bucket = sys.argv[2]
    prefix = sys.argv[3] if len(sys.argv) > 3 else "reports/"

    if not os.path.isfile(file_path):
        print(f"File not found: {file_path}")
        sys.exit(3)

    if boto3 is None:
        print("boto3 is not installed. Install boto3 to upload to S3.")
        sys.exit(5)

    region = os.getenv("AWS_REGION")
    session = boto3.session.Session()
    s3 = session.client("s3", region_name=region)

    base = os.path.basename(file_path)
    digest = sha256_file(file_path)[:12]
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    key = f"{prefix}{timestamp}_{digest}_{base}"

    print(f"Uploading {file_path} -> s3://{bucket}/{key}")
    ok = upload_file(s3, file_path, bucket, key)
    if not ok:
        sys.exit(4)

    s3_url = f"s3://{bucket}/{key}"
    meta = {
        "original_filename": base,
        "s3_url": s3_url,
        "sha256": digest,
        "uploaded_at": timestamp,
    }

    meta_path = f"{file_path}.upload.json"
    import json

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(f"Wrote metadata to {meta_path}")
    print(s3_url)


if __name__ == "__main__":
    main()
