Watchdog and counts helper for the scraper

What I added
- `scripts/get_counts.py` — prints number of saved JSON files under `out/<year>/` for 2023–2025 and shows the most recent filenames.
- `scripts/watchdog_scraper.py` — lightweight watchdog that checks counts every 15 minutes (default). If counts are stagnant it can run a provided shell command (for example, to restart a scraper).

Quick usage

1) See current counts:

```bash
python3 scripts/get_counts.py
```

2) Run the watchdog in the foreground, checking every 15 minutes and running a restart command when stagnant:

```bash
python3 scripts/watchdog_scraper.py --check-cmd "./run_scraper.sh --resume" --interval 900
```

Notes & integrations
- The watchdog writes `scripts/watchdog.log` (append-only). Rotate externally if needed.
- For production, prefer systemd unit or a cron job that runs the watchdog in the background.
- The watchdog does not alter scraper code; it only runs the provided command when counts stop increasing.

If you want, I can:
- Wire a minimal systemd service file and a restart script that gracefully stops/starts the current scraper process in this repo.
- Change the watchdog to also inspect the scraper logs and only restart if the scraper is alive but not writing files.
