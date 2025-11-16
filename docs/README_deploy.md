# Deploying the Cuyahoga CP Scraper (VPS / Docker)

This document explains how to deploy the project to a VPS (single node or multiple nodes), what components are included, and how we collect stats and re-check cases for changes.

Overview
- `scripts/manager.py` — Orchestrator that runs multiple scraper worker subprocesses, schedules validation (`scripts/validate_cache.py`), runs the `scripts/stats_collector.py`, and performs periodic rechecks of recent cases.
- `scripts/validate_cache.py` — Validates cached JSON files for minimal completeness.
- `scripts/stats_collector.py` — Aggregates dataset snapshots into `data/stats.db` and detects docket changes between the most recent saved JSONs.
- `deploy/Dockerfile` and `deploy/docker-compose.yml` — Containerization scaffolding for VPS deployment.

Quick start (Docker)
1. Build the image on the VPS

```bash
cd /path/to/repo
docker build -t cuyahoga_scraper -f deploy/Dockerfile .
```

2. Run a single node (simple)

```bash
docker run -d --name cuyahoga_scraper \
  -v $(pwd)/out:/app/out \
  -v $(pwd)/browser_data:/app/browser_data \
  -v $(pwd)/data:/app/data \
  cuyahoga_scraper
```

3. Or use docker-compose

```bash
docker-compose -f deploy/docker-compose.yml up -d --build
```

Systemd unit (example)
If you prefer systemd over Docker, use this unit as a template (adjust paths and user):

```ini
[Unit]
Description=Cuyahoga CP Scraper Manager
After=network.target

[Service]
Type=simple
User=scraper
WorkingDirectory=/srv/cuyahoga_cp_scraper
ExecStart=/usr/bin/python3 /srv/cuyahoga_cp_scraper/scripts/manager.py --workers 8
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Monitoring & logs
- The manager prints stdout/stderr; when run via Docker, logs are available via `docker logs`.
- Validation logs are in `scripts/validation.log`.
- Stats DB is `data/stats.db` (SQLite) and contains snapshots and detected case changes.

Scaling to multiple nodes
- To operate multiple nodes, each VPS runs the same container or systemd unit. Each node stores `out/` locally and reports metrics via the `data/stats.db`. For a centralized dashboard, aggregate `stats.db` outputs or set up a secure endpoint where nodes push their snapshots.

Safety & politeness
- Default worker chunking is conservative (small --limit). Keep `--workers` at or below 8 unless you have measured load.
- Use `--delay-ms` to tune politeness; increase if you see timeouts or if the site blocks you.

Monetization & metrics model (brief)
- Charge per monitored case per month, with tiers based on 'case complexity' measured by docket entry count and attached PDFs.
- Key metrics to estimate pricing:
  - Storage per case (bytes)
  - Average recheck bandwidth (how often a case changes)
  - Processing cost (CPU to parse and diff)
  - API queries per monitored case
- Provide plans: Basic (X cases, weekly recheck), Pro (Y cases, daily recheck), Enterprise (custom frequency + SLA)

Security
- Do not expose Playwright browser debugging ports publicly.
- Protect any central API endpoints with authentication and rate limits.

Next steps
- If you want, I can:
  - Add a small HTTP API to serve stats from `data/stats.db` (Flask/FastAPI) for a dashboard.
  - Add an automated aggregator script to push node snapshots to a central git repo or a secure API.
  - Implement `scripts/retry_invalid.py` to re-download invalid files in controlled batches.
