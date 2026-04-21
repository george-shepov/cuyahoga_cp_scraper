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
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# ── Config ──────────────────────────────────────────────────────────────────
SITE_ROOT   = "/var/www/foxxiie.com/brocklerlaw"
INDEX_FILE  = os.path.join(SITE_ROOT, "index.html")
# Token is read from the environment – never hardcoded.
# Set BROCKLER_API_TOKEN in /etc/brocklerlaw-save/env (not committed to git).
API_TOKEN   = os.environ.get("BROCKLER_API_TOKEN", "")
if not API_TOKEN:
    raise RuntimeError("BROCKLER_API_TOKEN environment variable is not set")
MAX_BYTES   = 2 * 1024 * 1024   # 2 MB sanity cap
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8765

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("save_api")


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
        if token != API_TOKEN:
            self.send_json(403, {"error": "unauthorized"})
            return

        html = payload.get("html", "")
        if not isinstance(html, str) or len(html.strip()) < 100:
            self.send_json(400, {"error": "html missing or too short"})
            return

        # ── Backup existing index.html ───────────────────────────────────
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(SITE_ROOT, f"index_{ts}.html")
        try:
            if os.path.exists(INDEX_FILE):
                with open(INDEX_FILE, "rb") as src:
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
        tmp = INDEX_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(html)
            os.replace(tmp, INDEX_FILE)   # atomic on Linux
            log.info("Published new index.html (%d bytes)", len(html))
        except OSError as exc:
            log.error("Write failed: %s", exc)
            self.send_json(500, {"error": "write failed"})
            return

        self.send_json(200, {"ok": True, "backup": os.path.basename(backup_path), "ts": ts})


if __name__ == "__main__":
    os.makedirs(SITE_ROOT, exist_ok=True)
    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), SaveHandler)
    log.info("Save API listening on %s:%d", LISTEN_HOST, LISTEN_PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Stopped.")
