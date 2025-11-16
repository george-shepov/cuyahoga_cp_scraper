#!/usr/bin/env python3
"""Collect simple statistics about the cached dataset and record into a local SQLite DB.

This records per-run snapshots: total files per year, total bytes, invalid count (via validate_cache),
and detects docket changes by comparing the last two saved JSONs for a given case.

The DB is stored at ./data/stats.db
"""
import sqlite3
from pathlib import Path
import json
from datetime import datetime
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out'
DBDIR = ROOT / 'data'
DB = DBDIR / 'stats.db'


def ensure_db():
    DBDIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS snapshots (
        ts TEXT PRIMARY KEY,
        files_2025 INTEGER,
        files_2024 INTEGER,
        files_2023 INTEGER,
        bytes_total INTEGER,
        invalid_count INTEGER
    )''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS case_changes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT,
        year INTEGER,
        case_num TEXT,
        reason TEXT
    )''')
    conn.commit()
    conn.close()


def count_files_and_bytes():
    totals = {2025: (0, 0), 2024: (0, 0), 2023: (0, 0)}
    bytes_total = 0
    for y in [2025, 2024, 2023]:
        d = OUT / str(y)
        if not d.exists():
            totals[y] = (0, 0)
            continue
        files = list(d.glob('*.json'))
        count = len(files)
        b = sum(f.stat().st_size for f in files)
        totals[y] = (count, b)
        bytes_total += b
    return totals, bytes_total


def detect_case_changes(limit_per_year=200):
    # For each year, look at the most recent N files and detect cases with differing dockets
    changes = []
    for y in [2025, 2024, 2023]:
        d = OUT / str(y)
        if not d.exists():
            continue
        files = sorted(d.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:limit_per_year]
        # group by case number
        by_case = {}
        for f in files:
            name = f.name.split('_', 1)[0]
            parts = name.split('-')
            if len(parts) < 2:
                continue
            case = parts[1]
            by_case.setdefault(case, []).append(f)

        for case, flist in by_case.items():
            if len(flist) < 2:
                continue
            # compare last two
            a = json.loads(flist[0].read_text(encoding='utf-8'))
            b = json.loads(flist[1].read_text(encoding='utf-8'))
            if a.get('docket') != b.get('docket'):
                changes.append((y, case, 'docket_changed'))
    return changes


def main():
    ensure_db()
    totals, bytes_total = count_files_and_bytes()
    # run validator in quick mode to find invalids (but don't fail)
    # We'll call validate_cache in --sample mode by invoking it and counting stderr output lines
    invalid_count = 0
    try:
        import subprocess
        r = subprocess.run(['python3', str(ROOT / 'scripts' / 'validate_cache.py'), '--years', '2025', '2024', '2023', '--limit', '100'], capture_output=True, text=True)
        # count occurrences of 'INVALID' in stdout
        invalid_count = r.stdout.count('INVALID')
    except Exception:
        invalid_count = -1

    ts = datetime.utcnow().isoformat() + 'Z'
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO snapshots (ts, files_2025, files_2024, files_2023, bytes_total, invalid_count) VALUES (?,?,?,?,?,?)', (
        ts, totals[2025][0], totals[2024][0], totals[2023][0], bytes_total, invalid_count
    ))
    conn.commit()

    # detect changes
    changes = detect_case_changes(200)
    for y, case, reason in changes:
        c.execute('INSERT INTO case_changes (ts, year, case_num, reason) VALUES (?,?,?,?)', (ts, y, case, reason))
    conn.commit()
    print(f"snapshots: files 2025={totals[2025][0]} 2024={totals[2024][0]} 2023={totals[2023][0]} bytes={bytes_total} invalid={invalid_count} changes_detected={len(changes)}")
    conn.close()


if __name__ == '__main__':
    main()
