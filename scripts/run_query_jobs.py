#!/usr/bin/env python3
"""
Run scheduled query jobs and emit alerts when conditions are met.

Intended to be called periodically (cron/systemd), e.g. every 5 minutes.
"""

from __future__ import annotations

import argparse
from datetime import datetime

from query_jobs import (
    build_latest_dataset,
    due_to_run,
    load_job_state,
    load_jobs,
    run_job_once,
    save_job_state,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run scheduled query jobs")
    p.add_argument("--force", action="store_true", help="Run all enabled jobs regardless of schedule")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    jobs = load_jobs()
    if not jobs:
        print("No query jobs configured.")
        return 0

    state = load_job_state()
    now = datetime.now()
    df = build_latest_dataset()

    ran = 0
    triggered = 0

    for job in jobs:
        enabled = bool(job.get("enabled", True))
        if not enabled:
            continue

        if not args.force and not due_to_run(job, state, now=now):
            continue

        result = run_job_once(df, job)
        jid = result["job_id"]
        state.setdefault("last_runs", {})
        state["last_runs"][jid] = result["ran_at"]

        ran += 1
        if result["triggered"]:
            triggered += 1

        print(
            f"job={result['job_name']} id={jid} rows={result['rows']} triggered={result['triggered']} ran_at={result['ran_at']}"
        )

    save_job_state(state)
    print(f"done ran={ran} triggered={triggered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
