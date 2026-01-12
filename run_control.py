#!/usr/bin/env python3
"""
Simple local control server to start/stop/pause/resume the scraper.
Serves a control page at http://localhost:8765 with a textbox for case IDs.

Usage: python3 run_control.py
"""
import http.server
import socketserver
import subprocess
import threading
import urllib.parse
import os
import json
import signal
from pathlib import Path

PORT = 8765
LOG_FILE = Path("control_scraper.log")
SCRAPER_CMD_BASE = ["python3", "main.py", "scrape", "--download-pdfs", "--workers", "1"]
REPO_ROOT = Path(__file__).parent


class ControlHandler(http.server.BaseHTTPRequestHandler):
    def _send_html(self, html):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _send_json(self, obj):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/status"):
            self._send_json(get_status())
            return

        # Serve control page
        html = """
        <html>
        <head><title>Scraper Control</title></head>
        <body>
        <h3>Scraper Control</h3>
        <form id="startForm" method="post" action="/start">
          Case IDs (space-separated):<br>
          <input type="text" name="cases" id="cases" size="60" value="CR-23-684826-A CR-25-706402-A"><br><br>
          <button type="submit">Start</button>
        </form>
        <button onclick="fetch('/stop',{{method:'POST'}}).then(()=>update())">STOP</button>
        <button onclick="fetch('/pause',{{method:'POST'}}).then(()=>update())">PAUSE</button>
        <button onclick="fetch('/resume',{{method:'POST'}}).then(()=>update())">RESUME</button>
        <h4>Status</h4>
        <pre id="status">Loading...</pre>
        <h4>Log (tail)</h4>
        <pre id="log">Loading...</pre>
        <script>
        async function update(){
          const r = await fetch('/status');
          const s = await r.json();
          document.getElementById('status').textContent = JSON.stringify(s,null,2);
          const lr = await fetch('/log');
          document.getElementById('log').textContent = await lr.text();
        }
        setInterval(update,2000);
        update();
        </script>
        </body>
        </html>
        """
        self._send_html(html)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8') if length else ''
        path = urllib.parse.urlparse(self.path).path

        if path == '/start':
            params = urllib.parse.parse_qs(body)
            cases = params.get('cases', [''])[0].strip()
            start_scraper(cases)
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
            return

        if path == '/stop':
            stop_scraper()
            self._send_json({'result':'stopping'})
            return

        if path == '/pause':
            pause_scraper()
            self._send_json({'result':'paused'})
            return

        if path == '/resume':
            resume_scraper()
            self._send_json({'result':'resumed'})
            return

        if path == '/log':
            self._send_log()
            return

        self.send_response(404)
        self.end_headers()

    def _send_log(self):
        if LOG_FILE.exists():
            data = LOG_FILE.read_text(encoding='utf-8', errors='replace')
        else:
            data = ''
        self.send_response(200)
        self.send_header('Content-type','text/plain; charset=utf-8')
        self.send_header('Content-length', str(len(data.encode('utf-8'))))
        self.end_headers()
        self.wfile.write(data.encode('utf-8'))


SCRAPER_PROC = {'p': None}


def start_scraper(cases_text: str):
    if SCRAPER_PROC['p'] and SCRAPER_PROC['p'].poll() is None:
        return
    args = SCRAPER_CMD_BASE.copy()
    if cases_text:
        args += ['--pdf-cases'] + cases_text.split()

    LOG_FILE.write_text('')
    logfile = open(LOG_FILE, 'ab')

    p = subprocess.Popen(args, cwd=str(REPO_ROOT), stdout=logfile, stderr=logfile)
    SCRAPER_PROC['p'] = p


def stop_scraper():
    p = SCRAPER_PROC.get('p')
    if p and p.poll() is None:
        try:
            p.send_signal(signal.SIGINT)
        except Exception:
            try:
                p.terminate()
            except Exception:
                pass


def pause_scraper():
    p = SCRAPER_PROC.get('p')
    if p and p.poll() is None:
        try:
            os.kill(p.pid, signal.SIGSTOP)
        except Exception:
            pass


def resume_scraper():
    p = SCRAPER_PROC.get('p')
    if p and p.poll() is None:
        try:
            os.kill(p.pid, signal.SIGCONT)
        except Exception:
            pass


def get_status():
    p = SCRAPER_PROC.get('p')
    if not p:
        return {'running': False}
    alive = p.poll() is None
    return {'running': alive, 'pid': p.pid if alive else None}


def run_server():
    with socketserver.ThreadingTCPServer(('127.0.0.1', PORT), ControlHandler) as httpd:
        print(f"Control server running at http://127.0.0.1:{PORT}/")
        httpd.serve_forever()


if __name__ == '__main__':
    # Auto-start scraper with default cases
    threading.Thread(target=run_server, daemon=True).start()
    print(f"Logs: {LOG_FILE.resolve()}")
    # Start default cases
    start_scraper('CR-23-684826-A CR-25-706402-A')
    try:
        while True:
            cmd = input("Control server running. Type 'quit' to exit this launcher: ")
            if cmd.strip().lower() in ('quit', 'exit'):
                stop_scraper()
                break
    except KeyboardInterrupt:
        stop_scraper()
