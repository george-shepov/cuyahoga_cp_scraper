#!/usr/bin/env python3
"""
Scrape Case API — runs on the .52 scraping node (port 8766).

POST /scrape-case  { "token": "<hash>", "case_id": "CR-25-706402-A" }
  → runs the Playwright scraper for that case (one year, one case)
  → returns the scraped JSON

Security: internal API token hash required (same as save_api.py).
Concurrency: only one scrape at a time (Lock); returns cached JSON if busy.
Cache: returns existing JSON if < 1 hour old, skipping re-scrape.

Start automatically via systemd:
  see scrape-case-api.service
"""
from __future__ import annotations

import glob
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent  # /home/shepov/brockler-scraper
PYTHON    = str(REPO_ROOT / ".venv" / "bin" / "python3")
if not os.path.exists(PYTHON):
    PYTHON = sys.executable

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8766
CACHE_MAX_AGE = 3600  # seconds: skip re-scrape if JSON is this fresh
SCRAPE_TIMEOUT = 90   # seconds for the scraper subprocess

API_TOKEN_HASH = os.environ.get(
    "BROCKLER_API_TOKEN_HASH",
    "afebf43cf94f084bf1dea949a5a1441eb51956602f2fb4caa82bae7fa45e53bb",
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("scrape_case_api")

_scrape_lock = threading.Lock()


# ── Helpers ──────────────────────────────────────────────────────────────────

def token_is_valid(token: str) -> bool:
    h = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return h == API_TOKEN_HASH


def parse_case_id(s: str) -> tuple[int | None, int | None]:
    """Return (year, number) from various case_id formats.

    Accepts: CR-25-706402-A, CR-2025-706402-A, 25-706402, 2025-706402, 706402
    """
    s = s.strip().upper().replace(" ", "")

    # CR-25-706402-A or CR-2025-706402-A
    m = re.match(r'^CR[-_](\d{2,4})[-_](\d{4,7})', s)
    if m:
        yr, num = int(m.group(1)), int(m.group(2))
        if yr < 100:
            yr += 2000
        return yr, num

    # 25-706402 or 2025-706402
    m = re.match(r'^(\d{2,4})[-_](\d{4,7})$', s)
    if m:
        yr, num = int(m.group(1)), int(m.group(2))
        if yr < 100:
            yr += 2000
        return yr, num

    # bare number: 706402
    m = re.match(r'^(\d{4,7})$', s)
    if m:
        return None, int(m.group(1))

    return None, None


def find_newest_json(year: int, number: int) -> Path | None:
    """Return the most recent JSON file for this year/number, or None."""
    pattern = str(REPO_ROOT / "out" / str(year) / f"{year}-{number}_*.json")
    files = sorted(glob.glob(pattern), reverse=True)
    return Path(files[0]) if files else None


def run_scrape(year: int, number: int) -> dict:
    """Invoke main.py for a single case, return the resulting JSON dict."""
    out_dir = REPO_ROOT / "out" / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Snapshot existing files to detect new ones
    before = set(glob.glob(str(out_dir / f"{year}-{number}_*.json")))

    cmd = [
        PYTHON, "main.py", "scrape",
        "--year", str(year),
        "--start", str(number),
        "--limit", "1",
        "--headless",
        "--delay-ms", "1500",
    ]
    log.info("scraping case year=%d number=%d", year, number)
    result = subprocess.run(
        cmd, cwd=str(REPO_ROOT),
        capture_output=True, text=True,
        timeout=SCRAPE_TIMEOUT,
    )
    log.info("scrape finished exit=%d", result.returncode)
    if result.stderr:
        log.debug("stderr: %s", result.stderr[:500])

    # Prefer brand-new files
    after = sorted(
        [f for f in glob.glob(str(out_dir / f"{year}-{number}_*.json")) if f not in before],
        reverse=True,
    )
    if after:
        with open(after[0], encoding="utf-8") as f:
            return json.load(f)

    # Fall back to any existing file for this case
    existing = find_newest_json(year, number)
    if existing:
        with open(existing, encoding="utf-8") as f:
            return json.load(f)

    raise RuntimeError(f"No JSON produced for {year}-{number}")


def try_years(number: int) -> tuple[int, dict]:
    """Try to scrape a case by cycling through likely years (newest first)."""
    current_year = datetime.now(timezone.utc).year
    for yr in range(current_year, max(current_year - 5, 2019), -1):
        # Check cache first
        cached = find_newest_json(yr, number)
        if cached and (time.time() - cached.stat().st_mtime) < CACHE_MAX_AGE:
            with open(cached, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("metadata", {}).get("exists", True):
                log.info("cache hit year=%d number=%d", yr, number)
                return yr, data

    # Not cached — scrape current year (main.py auto-detects if not found)
    current_year_data = run_scrape(current_year, number)
    if current_year_data.get("metadata", {}).get("exists", True):
        return current_year, current_year_data

    raise RuntimeError(f"Case {number} not found in any year")


# ── HTTP Handler ─────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log.info("%s - " + fmt, self.address_string(), *args)

    def send_json(self, status: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path.rstrip("/") == "/health":
            self.send_json(200, {"ok": True, "service": "scrape-case-api"})
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path.rstrip("/") != "/scrape-case":
            self.send_json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(min(length, 4096)) if length else b""
        try:
            body = json.loads(raw.decode("utf-8")) if raw.strip() else {}
        except (ValueError, UnicodeDecodeError):
            self.send_json(400, {"error": "invalid JSON"})
            return

        token = str(body.get("token", ""))
        if not token_is_valid(token):
            self.send_json(403, {"error": "unauthorized"})
            return

        case_id = str(body.get("case_id", "")).strip()
        if not case_id:
            self.send_json(400, {"error": "case_id required"})
            return

        year, number = parse_case_id(case_id)
        if number is None:
            self.send_json(400, {"error": f"Cannot parse case_id: {case_id}"})
            return

        # ── Cache check ──────────────────────────────────────────────────
        if year is not None:
            cached_path = find_newest_json(year, number)
            if cached_path and (time.time() - cached_path.stat().st_mtime) < CACHE_MAX_AGE:
                log.info("cache hit year=%d number=%d", year, number)
                with open(cached_path, encoding="utf-8") as f:
                    data = json.load(f)
                self.send_json(200, {"ok": True, "data": data, "cached": True})
                return

        # ── Acquire scrape lock (one scrape at a time) ───────────────────
        if not _scrape_lock.acquire(blocking=False):
            # Scraper busy – return cached data if available
            if year is not None:
                cached_path = find_newest_json(year, number)
                if cached_path:
                    with open(cached_path, encoding="utf-8") as f:
                        data = json.load(f)
                    self.send_json(200, {"ok": True, "data": data, "cached": True})
                    return
            self.send_json(503, {"error": "Scraper is busy. Please try again in 30 seconds."})
            return

        try:
            if year is not None:
                data = run_scrape(year, number)
            else:
                _, data = try_years(number)
            self.send_json(200, {"ok": True, "data": data})
        except subprocess.TimeoutExpired:
            self.send_json(504, {"error": "Scrape timed out (90s). Try again shortly."})
        except RuntimeError as exc:
            self.send_json(404, {"error": str(exc)})
        except Exception as exc:
            log.error("Unexpected error: %s", exc, exc_info=True)
            self.send_json(500, {"error": "Internal scraper error"})
        finally:
            _scrape_lock.release()


if __name__ == "__main__":
    log.info("scrape_case_api starting on %s:%d  repo=%s", LISTEN_HOST, LISTEN_PORT, REPO_ROOT)
    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    log.info("Listening.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Stopped.")
