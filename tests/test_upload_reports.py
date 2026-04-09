import os
import sys
import types
import json

def import_uploader_with_fake_boto():
    # Create a fake boto3 module if it's not installed so importing uploader works
    if "boto3" not in sys.modules:
        fake_boto = types.ModuleType("boto3")
        class Session:
            def client(self, service, region_name=None):
                raise RuntimeError("not patched")
        fake_boto.session = types.SimpleNamespace(Session=Session)
        sys.modules["boto3"] = fake_boto
    # Provide a minimal fake botocore.exceptions.ClientError for imports
    if "botocore" not in sys.modules:
        fake_botocore = types.ModuleType("botocore")
        fake_exceptions = types.ModuleType("botocore.exceptions")
        class ClientError(Exception):
            pass
        fake_exceptions.ClientError = ClientError
        sys.modules["botocore"] = fake_botocore
        sys.modules["botocore.exceptions"] = fake_exceptions
    # Now import the uploader module by file path to avoid package import issues
    import importlib.util
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "scripts" / "upload_reports_to_s3.py"
    spec = importlib.util.spec_from_file_location("upload_reports_to_s3", str(module_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sha256_file(tmp_path):
    u = import_uploader_with_fake_boto()
    p = tmp_path / "sample.txt"
    p.write_text("hello world")
    digest = u.sha256_file(str(p))
    assert len(digest) == 64


def test_metadata_written(tmp_path, monkeypatch):
    # Create small fake file
    p = tmp_path / "report.zip"
    p.write_text("dummy")

    # Import uploader with fake boto module available
    u = import_uploader_with_fake_boto()

    # Monkeypatch boto3.session.Session to return stub client
    class StubS3:
        def upload_file(self, file_path, bucket, _key):
            assert file_path == str(p)
            assert bucket == "my-bucket"

    def fake_session():
        class S:
            def client(self, *args, **kwargs):
                return StubS3()

        return S()

    import boto3
    monkeypatch.setattr(boto3.session, "Session", fake_session)

    # invoke upload script main via direct call
    u_main = u.main

    # call main with args
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
