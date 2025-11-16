#!/usr/bin/env python3
"""
DEBUG version - shows actual error messages from main.py
"""
import subprocess
from pathlib import Path

# Try ONE case and see what happens
case = 677525
yr = 2023

print(f"Testing case {yr}-{case} with main.py...\n")

r = subprocess.run(
    ["python3", "main.py", "scrape", "--year", str(yr), 
     "--start", str(case), "--limit", "1", "--direction", "up"],
    capture_output=True, timeout=180, text=True
)

print(f"Return code: {r.returncode}\n")

print("=== STDOUT ===")
print(r.stdout[:2000])

print("\n=== STDERR ===")
print(r.stderr[:2000])

print("\n=== CHECK FILES ===")
year_dir = Path(f"out/{yr}")
if year_dir.exists():
    files = list(year_dir.glob(f"{yr}-{case:06d}_*.json"))
    print(f"Files found: {len(files)}")
    for f in files[-5:]:
        print(f"  - {f.name}")
else:
    print(f"Directory {year_dir} doesn't exist!")
