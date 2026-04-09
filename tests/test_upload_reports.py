import os
import json
from scripts.upload_reports_to_s3 import sha256_file


def test_sha256_file(tmp_path):
    p = tmp_path / "sample.txt"
    p.write_text("hello world")
    digest = sha256_file(str(p))
    assert len(digest) == 64


def test_metadata_written(tmp_path, monkeypatch):
    # Create small fake file
    p = tmp_path / "report.zip"
    p.write_text("dummy")

    # Monkeypatch boto3 client to a stub that 'uploads'
    class StubS3:
        def upload_file(self, file_path, bucket, _key):
            assert file_path == str(p)
            assert bucket == "my-bucket"

    def fake_session():
        class S:
            def client(self, _service, _region_name=None):
                return StubS3()

        return S()

    monkeypatch.setattr("boto3.session.Session", fake_session)

    # invoke upload script main via subprocess-like call
    from scripts import upload_reports_to_s3 as u
    u_main = u.main

    # call main with args
    import sys
    old_argv = sys.argv
    sys.argv = ["upload_reports_to_s3.py", str(p), "my-bucket", "samples/"]
    try:
        u_main()
    finally:
        sys.argv = old_argv

    meta_path = f"{p}.upload.json"
    assert os.path.exists(meta_path)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["original_filename"] == "report.zip"
