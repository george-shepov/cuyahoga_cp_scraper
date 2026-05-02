#!/usr/bin/env python3
"""Simple utility: print number of saved JSON files under out/<year>/ for 2023-2025.

Usage: python3 scripts/get_counts.py
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"

def count_year(year: int) -> int:
    p = OUT / str(year)
    if not p.exists():
        return 0
    return sum(1 for _ in p.glob('*.json'))

def list_latest(year: int, limit: int = 5):
    p = OUT / str(year)
    if not p.exists():
        return []
    files = sorted(p.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    return [f.name for f in files[:limit]]

def main():
    years = [2023, 2024, 2025, 2026]
    print("Counts of cached JSON files in ./out/")
    for y in years:
        c = count_year(y)
        print(f"{y}: {c}")
        latest = list_latest(y)
        if latest:
            print("  latest:")
            for fn in latest:
                print(f"    {fn}")

if __name__ == '__main__':
    main()
