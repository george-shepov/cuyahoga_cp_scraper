#!/usr/bin/env python3
"""
Brockler Law – live-publish save API.
POST /save  { "html": "<full html string>", "token": "<REVIEW_PASSWORD>" }
  → backs up current index.html to index_YYYYMMDD_HHMMSS.html
  → writes new index.html in place
Runs behind Nginx on 127.0.0.1:8765.
"""

import os
import json
import logging
import hashlib
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# ── Config ──────────────────────────────────────────────────────────────────
DEFAULT_SITE_ROOT = "/var/www/foxxiie.com/brocklerlaw"
SITE_ROOTS = {
    "foxxiie.com": "/var/www/foxxiie.com/brocklerlaw",
    "www.foxxiie.com": "/var/www/foxxiie.com/brocklerlaw",
    "prosecutordefense.com": "/var/www/prosecutordefense.com/brocklerlaw",
    "www.prosecutordefense.com": "/var/www/prosecutordefense.com/brocklerlaw",
    "procecutordefense.com": "/var/www/prosecutordefense.com/brocklerlaw",
    "www.procecutordefense.com": "/var/www/prosecutordefense.com/brocklerlaw",
}
# Optional environment token. If absent, fall back to checking the same password
# hash already embedded in the admin UI so the service can still run safely.
API_TOKEN = os.environ.get("BROCKLER_API_TOKEN", "")
API_TOKEN_HASH = os.environ.get(
    "BROCKLER_API_TOKEN_HASH",
    "afebf43cf94f084bf1dea949a5a1441eb51956602f2fb4caa82bae7fa45e53bb",
)
MAX_BYTES   = 2 * 1024 * 1024   # 2 MB sanity cap
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8765

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("save_api")


def site_root_for_host(host_header: str) -> str:
    host = (host_header or "").split(":", 1)[0].strip().lower()
    return SITE_ROOTS.get(host, DEFAULT_SITE_ROOT)


def token_is_valid(token: str) -> bool:
    if API_TOKEN and token == API_TOKEN:
        return True
    if API_TOKEN_HASH:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return token_hash == API_TOKEN_HASH
    return False


class SaveHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log.info("%s - " + fmt, self.address_string(), *args)

    def send_json(self, status, body: dict):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        # preflight (same-origin requests won't need this, but just in case)
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        if self.path.rstrip("/") != "/save":
            self.send_json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BYTES:
            self.send_json(413, {"error": "payload too large"})
            return

        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self.send_json(400, {"error": "invalid JSON"})
            return

        token = payload.get("token", "")
        if not isinstance(token, str) or not token_is_valid(token):
            self.send_json(403, {"error": "unauthorized"})
            return

        html = payload.get("html", "")
        if not isinstance(html, str) or len(html.strip()) < 100:
            self.send_json(400, {"error": "html missing or too short"})
            return

        site_root = site_root_for_host(self.headers.get("Host", ""))
        index_file = os.path.join(site_root, "index.html")

        # ── Backup existing index.html ───────────────────────────────────
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(site_root, f"index_{ts}.html")
        try:
            os.makedirs(site_root, exist_ok=True)
            if os.path.exists(index_file):
                with open(index_file, "rb") as src:
                    content = src.read()
                with open(backup_path, "wb") as dst:
                    dst.write(content)
                log.info("Backed up → %s", backup_path)
            else:
                log.info("No existing index.html to back up")
        except OSError as exc:
            log.error("Backup failed: %s", exc)
            self.send_json(500, {"error": "backup failed"})
            return

        # ── Write new index.html ─────────────────────────────────────────
        tmp = index_file + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(html)
            os.replace(tmp, index_file)   # atomic on Linux
            log.info("Published new index.html for host %s (%d bytes)", self.headers.get("Host", ""), len(html))
        except OSError as exc:
            log.error("Write failed: %s", exc)
            self.send_json(500, {"error": "write failed"})
            return

        self.send_json(200, {"ok": True, "backup": os.path.basename(backup_path), "ts": ts})


if __name__ == "__main__":
    os.makedirs(DEFAULT_SITE_ROOT, exist_ok=True)
    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), SaveHandler)
    log.info("Save API listening on %s:%d", LISTEN_HOST, LISTEN_PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Stopped.")
