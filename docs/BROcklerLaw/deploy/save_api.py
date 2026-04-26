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
import re
import urllib.request
import urllib.error
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

# ── Config ──────────────────────────────────────────────────────────────────
DEFAULT_SITE_ROOT = "/var/www/prosecutordefense.com/brocklerlaw"
SITE_ROOTS = {
    "prosecutordefense.com": "/var/www/prosecutordefense.com/brocklerlaw",
    "www.prosecutordefense.com": "/var/www/prosecutordefense.com/brocklerlaw",
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
CASES_FILE        = "/opt/brocklerlaw-save/cases_data.json"
VISITS_FILE       = "/opt/brocklerlaw-save/visits.log"
SCRAPE_TRIGGER_FILE = "/opt/brocklerlaw-save/scrape_trigger.json"
BACKUP_NAME_RE = re.compile(r"^index_\d{8}_\d{6}\.html$")

# ── Stripe config (set via environment variables) ────────────────────────────
STRIPE_SECRET_KEY   = os.environ.get("STRIPE_SECRET_KEY", "")          # sk_live_... or sk_test_...
STRIPE_PRICE_ID     = os.environ.get("STRIPE_PRICE_ID", "")             # price_... from Stripe dashboard
STRIPE_TRIAL_DAYS   = int(os.environ.get("STRIPE_TRIAL_DAYS", "14"))
STRIPE_SUCCESS_URL  = os.environ.get("STRIPE_SUCCESS_URL",
                                     "https://prosecutordefense.com/?trial=success")
STRIPE_CANCEL_URL   = os.environ.get("STRIPE_CANCEL_URL",
                                     "https://prosecutordefense.com/?trial=cancelled")
STRIPE_API_BASE     = "https://api.stripe.com/v1"

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


def list_backups(site_root: str, limit: int = 50) -> list[dict]:
    try:
        names = os.listdir(site_root)
    except OSError:
        return []

    backups = []
    for name in names:
        if not BACKUP_NAME_RE.match(name):
            continue
        full = os.path.join(site_root, name)
        try:
            stat = os.stat(full)
        except OSError:
            continue
        backups.append(
            {
                "name": name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        )

    backups.sort(key=lambda item: item["name"], reverse=True)
    return backups[: max(1, min(limit, 200))]


def write_atomic_text(path: str, content: str):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(content)
    os.replace(tmp, path)


def backup_current_index(index_file: str, site_root: str) -> str | None:
    if not os.path.exists(index_file):
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(site_root, f"index_{ts}.html")
    with open(index_file, "rb") as src:
        content = src.read()
    with open(backup_path, "wb") as dst:
        dst.write(content)
    return os.path.basename(backup_path)


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

    def _log_visit(self, page: str):
        """Append one visit record to VISITS_FILE."""
        try:
            os.makedirs(os.path.dirname(VISITS_FILE), exist_ok=True)
            ip = self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()
            ua = self.headers.get("User-Agent", "")[:200]
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            line = f"{ts}  page={page}  ip={ip}  ua={ua}\n"
            with open(VISITS_FILE, "a", encoding="utf-8") as fh:
                fh.write(line)
            log.info("VISIT  page=%s  ip=%s", page, ip)
        except OSError as exc:
            log.warning("visits log write failed: %s", exc)

    def do_GET(self):
        parsed = urlparse(self.path)
        # ── /ping – lightweight visit beacon (no auth) ───────────────────
        if parsed.path.rstrip("/") == "/ping":
            qs = parse_qs(parsed.query)
            page = (qs.get("page", ["unknown"])[0])[:64]
            self._log_visit(page)
            self.send_response(204)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if parsed.path.rstrip("/") == "/backups":
            qs = parse_qs(parsed.query)
            token = qs.get("token", [""])[0]
            if not isinstance(token, str) or not token_is_valid(token):
                self.send_json(403, {"error": "unauthorized"})
                return

            host = self.headers.get("Host", "")
            site_root = site_root_for_host(host)
            limit_raw = qs.get("limit", ["50"])[0]
            try:
                limit = int(limit_raw)
            except ValueError:
                limit = 50

            self.send_json(200, {"ok": True, "backups": list_backups(site_root, limit=limit)})
            return

        if parsed.path.rstrip("/") != "/cases":
            self.send_json(404, {"error": "not found"})
            return
        qs = parse_qs(parsed.query)
        token = qs.get("token", [""])[0]
        if not isinstance(token, str) or not token_is_valid(token):
            self.send_json(403, {"error": "unauthorized"})
            return
        try:
            with open(CASES_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.send_json(200, data)
        except FileNotFoundError:
            self.send_json(200, {"brockler_cases": [], "vacant_cases": [], "synced_at": None})
        except (OSError, ValueError) as exc:
            log.error("cases read error: %s", exc)
            self.send_json(500, {"error": "read failed"})

    def do_POST(self):
        path = self.path.rstrip("/")

        # ── /stripe-checkout – public, no token required ─────────────────
        if path == "/stripe-checkout":
            self._handle_stripe_checkout()
            return

        # ── /ping – visit beacon (no auth) ───────────────────────────────
        if path == "/ping":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(min(length, 512)) if length else b""
            try:
                body = json.loads(raw.decode("utf-8")) if raw.strip() else {}
            except (ValueError, UnicodeDecodeError):
                body = {}
            page = str(body.get("page", "unknown"))[:64]
            self._log_visit(page)
            self.send_response(204)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return

        # ── /scrape-trigger – queue a real-time scrape on the mining node ──
        if path == "/scrape-trigger":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(min(length, MAX_BYTES)) if length else b""
            try:
                body = json.loads(raw.decode("utf-8")) if raw.strip() else {}
            except (ValueError, UnicodeDecodeError):
                self.send_json(400, {"error": "invalid JSON"})
                return
            token = body.get("token", "")
            if not isinstance(token, str) or not token_is_valid(token):
                self.send_json(403, {"error": "unauthorized"})
                return
            ts = datetime.now().isoformat()
            trigger = {"requested": True, "requested_at": ts, "requested_by": "admin"}
            try:
                os.makedirs(os.path.dirname(SCRAPE_TRIGGER_FILE), exist_ok=True)
                tmp = SCRAPE_TRIGGER_FILE + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(trigger, fh)
                os.replace(tmp, SCRAPE_TRIGGER_FILE)
                log.info("scrape trigger queued at %s", ts)
                self.send_json(200, {"ok": True, "queued_at": ts})
            except OSError as exc:
                log.error("trigger write error: %s", exc)
                self.send_json(500, {"error": "write failed"})
            return

        if path not in ("/save", "/cases-sync", "/restore"):
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

        # ── /cases-sync branch ───────────────────────────────────────────
        if path == "/cases-sync":
            cases_data = payload.get("data")
            if not isinstance(cases_data, dict):
                self.send_json(400, {"error": "data must be an object"})
                return
            ts = datetime.now().isoformat()
            cases_data["synced_at"] = ts
            try:
                os.makedirs(os.path.dirname(CASES_FILE), exist_ok=True)
                tmp = CASES_FILE + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(cases_data, fh, indent=2)
                os.replace(tmp, CASES_FILE)
                log.info("cases_data.json synced (%d brockler / %d vacant)",
                         len(cases_data.get("brockler_cases", [])),
                         len(cases_data.get("vacant_cases", [])))
                self.send_json(200, {"ok": True, "synced_at": ts})
            except OSError as exc:
                log.error("cases write error: %s", exc)
                self.send_json(500, {"error": "write failed"})
            return

        if path == "/restore":
            backup_name = payload.get("backup", "")
            if not isinstance(backup_name, str) or not BACKUP_NAME_RE.match(backup_name):
                self.send_json(400, {"error": "invalid backup name"})
                return

            site_root = site_root_for_host(self.headers.get("Host", ""))
            index_file = os.path.join(site_root, "index.html")
            backup_file = os.path.join(site_root, backup_name)

            if not os.path.exists(backup_file):
                self.send_json(404, {"error": "backup not found"})
                return

            try:
                os.makedirs(site_root, exist_ok=True)
                pre_restore_backup = backup_current_index(index_file, site_root)
                with open(backup_file, "r", encoding="utf-8") as src:
                    restored_html = src.read()
                write_atomic_text(index_file, restored_html)
                log.info(
                    "Restored index.html from %s for host %s",
                    backup_name,
                    self.headers.get("Host", ""),
                )
                self.send_json(
                    200,
                    {
                        "ok": True,
                        "restored_from": backup_name,
                        "backup": pre_restore_backup,
                    },
                )
            except OSError as exc:
                log.error("Restore failed: %s", exc)
                self.send_json(500, {"error": "restore failed"})
            return

        html = payload.get("html", "")
        if not isinstance(html, str) or len(html.strip()) < 100:
            self.send_json(400, {"error": "html missing or too short"})
            return

        site_root = site_root_for_host(self.headers.get("Host", ""))
        index_file = os.path.join(site_root, "index.html")

        # ── Backup existing index.html ───────────────────────────────────
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            os.makedirs(site_root, exist_ok=True)
            backup_name = backup_current_index(index_file, site_root)
            if backup_name:
                log.info("Backed up → %s", os.path.join(site_root, backup_name))
            else:
                log.info("No existing index.html to back up")
        except OSError as exc:
            log.error("Backup failed: %s", exc)
            self.send_json(500, {"error": "backup failed"})
            return

        # ── Write new index.html ─────────────────────────────────────────
        try:
            write_atomic_text(index_file, html)
            log.info("Published new index.html for host %s (%d bytes)", self.headers.get("Host", ""), len(html))
        except OSError as exc:
            log.error("Write failed: %s", exc)
            self.send_json(500, {"error": "write failed"})
            return

        self.send_json(200, {"ok": True, "backup": backup_name, "ts": ts})

    def _handle_stripe_checkout(self):
        """Create a Stripe Checkout Session for a subscription with trial period."""
        if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID:
            log.error("Stripe not configured: STRIPE_SECRET_KEY or STRIPE_PRICE_ID missing")
            self.send_json(503, {"error": "Stripe not configured on server"})
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(min(length, 4096))
        try:
            body = json.loads(raw.decode("utf-8")) if raw.strip() else {}
        except (ValueError, UnicodeDecodeError):
            body = {}

        email = (body.get("email") or "").strip()[:254]
        firm  = (body.get("firm") or "").strip()[:200]

        import urllib.parse as _urlparse
        params = {
            "mode": "subscription",
            "line_items[0][price]": STRIPE_PRICE_ID,
            "line_items[0][quantity]": "1",
            "subscription_data[trial_period_days]": str(STRIPE_TRIAL_DAYS),
            "success_url": STRIPE_SUCCESS_URL,
            "cancel_url": STRIPE_CANCEL_URL,
            "allow_promotion_codes": "true",
        }
        if email:
            params["customer_email"] = email
        if firm:
            params["metadata[firm_name]"] = firm

        encoded = _urlparse.urlencode(params).encode("utf-8")
        req = urllib.request.Request(
            f"{STRIPE_API_BASE}/checkout/sessions",
            data=encoded,
            method="POST",
        )
        req.add_header("Authorization", f"Bearer {STRIPE_SECRET_KEY}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("Stripe-Version", "2024-04-10")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                session = json.loads(resp.read().decode("utf-8"))
            checkout_url = session.get("url", "")
            log.info("Stripe Checkout Session created: %s (email=%s)", session.get("id"), email or "-")
            self.send_json(200, {"url": checkout_url})
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            log.error("Stripe API error %d: %s", exc.code, err_body[:400])
            self.send_json(502, {"error": "Stripe API error"})
        except urllib.error.URLError as exc:
            log.error("Stripe network error: %s", exc)
            self.send_json(502, {"error": "Stripe network error"})


if __name__ == "__main__":
    os.makedirs(DEFAULT_SITE_ROOT, exist_ok=True)
    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), SaveHandler)
    log.info("Save API listening on %s:%d", LISTEN_HOST, LISTEN_PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Stopped.")
