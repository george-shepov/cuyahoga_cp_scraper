#!/usr/bin/env python3
"""Deduplicate CSV rows where the only difference is the filename portion of any path-like cell.

Heuristic: for each cell, if it matches a path with a filename (has a '/...' and ends with an extension),
strip the final filename and use the directory portion when building a normalized key.

Usage:
  python3 tools/dedupe_csv_by_filename.py --dir out --dry-run
  python3 tools/dedupe_csv_by_filename.py --dir out --apply
"""
import argparse
import csv
import pathlib
import re
from datetime import datetime


PATH_FILE_RE = re.compile(r"(.*/)([^/]+\.[A-Za-z0-9]+)$")


# Also consider plain filenames without extension (rare), e.g. 'out/dir/12345'
PLAIN_FILE_RE = re.compile(r"(.*/)([^/]+)$")


def normalize_row(row):
    norm = []
    for cell in row:
        m = PATH_FILE_RE.search(cell)
        if m:
            norm.append(m.group(1))
        else:
            norm.append(cell.strip())
    return tuple(norm)


def process_csv(path: pathlib.Path, apply: bool = False):
    with path.open('r', newline='', encoding='utf-8', errors='replace') as fh:
        reader = csv.reader(fh)
        try:
            rows = list(reader)
        except Exception as e:
            print(f"Skipping unreadable CSV: {path} ({e})")
            return 0, 0

    if not rows:
        return 0, 0

    header = rows[0]
    data = rows[1:]

    seen = {}
    keep = []
    dup_count = 0
    for r in data:
        # try normalize; if normalization collapses rows too eagerly, it will be visible in dry-run
        key = normalize_row(r)
        if key in seen:
            dup_count += 1
        else:
            seen[key] = r
            keep.append(r)

    if dup_count == 0:
        return 0, 0

    out_path = path.with_name(path.name + '.dedup.csv')
    if apply:
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        backup = path.with_name(path.name + f'.bak.{timestamp}')
        path.rename(backup)
        print(f"Backed up {path} -> {backup}")
        target = path
    else:
        target = out_path

    with target.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(keep)

    print(f"Wrote {target} (kept {len(keep)} rows, removed {dup_count} duplicates)")
    return len(keep), dup_count


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dir', default='out')
    p.add_argument('--apply', action='store_true')
    p.add_argument('--pattern', default='**/*.csv')
    args = p.parse_args()

    base = pathlib.Path(args.dir)
    if not base.exists():
        print(f"Directory not found: {base}")
        raise SystemExit(1)

    files = list(base.rglob('*.csv'))
    total_removed = 0
    total_files = 0
    for f in files:
        # skip generated files
        if f.name.endswith('.bak') or f.name.endswith('.fixed.csv') or f.name.endswith('.dedup.csv'):
            continue
        total_files += 1
        kept, removed = process_csv(f, apply=args.apply)
        total_removed += removed

    print(f"Scanned {total_files} CSV files; total duplicates removed: {total_removed}")


if __name__ == '__main__':
    main()
