#!/usr/bin/env python3
"""Scan CSV files for repeated path segments like
"out/obstructing_cases/out/obstructing_cases/..." and write cleaned copies.

Usage: python3 tools/clean_repeated_paths.py --dir out
"""
import argparse
import pathlib
import re
from datetime import datetime


PATTERNS = [r'(out/obstructing_cases/)+' ]


def clean_text(text: str) -> str:
    s = text
    for p in PATTERNS:
        s = re.sub(p, 'out/obstructing_cases/', s)
    return s


def process_file(path: pathlib.Path, dry_run: bool = False) -> bool:
    text = path.read_text(encoding='utf-8', errors='replace')
    cleaned = clean_text(text)
    if cleaned == text:
        return False
    out_path = path.with_name(path.name + '.fixed.csv')
    if dry_run:
        print(f"Would write: {out_path}")
        return True
    # write cleaned copy, keep original
    out_path.write_text(cleaned, encoding='utf-8')
    print(f"Wrote cleaned file: {out_path}")
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dir', default='out', help='directory containing csv files')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()

    base = pathlib.Path(args.dir)
    if not base.exists():
        print(f"Directory not found: {base}")
        raise SystemExit(1)

    csvs = list(base.rglob('*.csv'))
    print(f"Found {len(csvs)} csv files under {base}")
    changed = 0
    for f in csvs:
        try:
            if process_file(f, dry_run=args.dry_run):
                changed += 1
        except Exception as e:
            print(f"Error processing {f}: {e}")

    print(f"Processed {len(csvs)} files; cleaned copies written for {changed} files")


if __name__ == '__main__':
    main()
