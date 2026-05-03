# Cuyahoga CP Scraper

Python scraper and analytics tools for Cuyahoga County Common Pleas criminal case data, with a FastAPI backend and Vue admin/public frontend.

## Active Entry Points

- `main.py`: primary scraper CLI.
- `scripts/query_jobs.py`: dataset builder and scheduled query utilities.
- `backend/app/main.py`: current OVI content engine API.
- `api/main.py`: legacy analytics/content API used by existing tests.
- `frontend/`: Vue/Vite frontend.
- `deploy/docker-compose*.yml`: containerized worker and production stacks.

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install
cd frontend && npm install
```

## Verify

```bash
python3 -m pytest -q
python3 -m compileall -q backend services scripts api database main.py
cd frontend && npm run build
```

## Common Commands

```bash
python3 main.py scrape --year 2023 --start 684826 --limit 1
python3 main.py scrape --year 2023 --start 684826 --limit 1 --download-pdfs
python3 main.py stats --year 2023
python3 scripts/query_jobs.py
```

Generated scrape output belongs in ignored runtime directories such as `out/`, `logs/`, and `state/`. Historical notes and obsolete docs live under `_ARCHIVE/`.
