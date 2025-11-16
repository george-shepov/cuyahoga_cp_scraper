#!/usr/bin/env python3
"""Validate cached JSON case files under out/<year>/.

Checks that files are JSON, parseable, and contain minimal data from the 5 tabs:
  - summary (or case_id)
  - docket (list, at least 1 entry)
  - costs (list or empty)
  - defendant (dict with some keys)
  - attorneys (list)

The script keeps a small state file at scripts/validated_state.json so subsequent
runs only validate newly added files by mtime. Use --full to revalidate all files.

Usage examples:
  python3 scripts/validate_cache.py --years 2025 2024 2023
  python3 scripts/validate_cache.py --years 2025 --limit 500
  python3 scripts/validate_cache.py --full
"""
import argparse
import json
from pathlib import Path
import time
from datetime import datetime
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
STATE = ROOT / "scripts" / "validated_state.json"
LOG = ROOT / "scripts" / "validation.log"


def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding='utf-8')


def log(msg: str):
    ts = datetime.utcnow().isoformat() + 'Z'
    s = f"{ts} {msg}\n"
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, 'a') as fh:
        fh.write(s)
    print(s, end='')


def list_files(year: int):
    d = OUT / str(year)
    if not d.exists():
        return []
    return sorted(d.glob('*.json'), key=lambda p: p.stat().st_mtime)


def validate_file(path: Path):
    """Return (valid: bool, reason:str)"""
    try:
        text = path.read_text(encoding='utf-8')
        data = json.loads(text)
    except Exception as e:
        return False, f"json-parse-error: {e}"

    meta = data.get('metadata', {})
    # summary
    summary = data.get('summary') or {}
    # docket
    docket = data.get('docket')
    # costs
    costs = data.get('costs')
    # defendant
    defendant = data.get('defendant')
    # attorneys
    attorneys = data.get('attorneys')

    # Minimal checks
    if not summary or (isinstance(summary, dict) and not summary):
        # allow if case_id present in metadata
        if not meta.get('case_id'):
            return False, 'missing-summary-or-case_id'

    if not isinstance(docket, list) or len(docket) == 0:
        return False, 'docket-empty-or-missing'

    if defendant is None or (isinstance(defendant, dict) and not defendant):
        return False, 'defendant-empty-or-missing'

    if attorneys is None:
        return False, 'attorneys-missing'

    # passed minimal checks
    return True, 'ok'


def main():
    p = argparse.ArgumentParser(description="Validate cached case JSON files")
    p.add_argument('--years', nargs='*', type=int, default=[2025, 2024, 2023])
    p.add_argument('--limit', type=int, default=1000, help='max new files to validate per run')
    p.add_argument('--full', action='store_true', help='revalidate all files for given years')
    p.add_argument('--sample-every', type=int, default=50, help='if no new files, sample every Nth file for older years')
    args = p.parse_args()

    state = load_state()
    results = {y: {'checked': 0, 'invalid': []} for y in args.years}

    for y in args.years:
        files = list_files(y)
        if not files:
            log(f"year={y}: no files found")
            continue

        # Determine files to check
        if args.full:
            to_check = files
        else:
            last_mtime = state.get(str(y), 0)
            to_check = [f for f in files if int(f.stat().st_mtime) > int(last_mtime)]

            # If none new, sample older files every sample-every
            if not to_check:
                to_check = files[-args.limit:] if args.limit and len(files) > args.limit else files
                to_check = to_check[::args.sample_every]

        if args.limit:
            to_check = to_check[-args.limit:]

        if not to_check:
            log(f"year={y}: nothing to validate (state) — skipping")
            continue

        log(f"year={y}: validating {len(to_check)} files")
        max_mtime = state.get(str(y), 0)
        checked = 0
        for f in to_check:
            checked += 1
            valid, reason = validate_file(f)
            results[y]['checked'] += 1
            if not valid:
                results[y]['invalid'].append({'file': str(f), 'reason': reason})
                log(f"INVALID {f} -> {reason}")
            # update max mtime
            m = int(f.stat().st_mtime)
            if m > max_mtime:
                max_mtime = m

        state[str(y)] = max_mtime

    # Save state
    save_state(state)

    # Summarize
    total_checked = sum(results[y]['checked'] for y in results)
    total_invalid = sum(len(results[y]['invalid']) for y in results)
    log(f"validation-complete: checked={total_checked} invalid={total_invalid}")

    # Exit non-zero if invalid found
    if total_invalid > 0:
        # print short list
        for y in results:
            for inv in results[y]['invalid']:
                print(f"{inv['file']} -> {inv['reason']}")
        sys.exit(2)


if __name__ == '__main__':
    main()
