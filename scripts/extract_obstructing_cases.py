#!/usr/bin/env python3
import re
from pathlib import Path
import shutil
import csv

KEYWORD_RE = re.compile(r"obstruct", re.IGNORECASE)
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "out" / "obstructing_cases"
SKIP_DIRS = {"node_modules", ".git", "__pycache__"}

DEST.mkdir(parents=True, exist_ok=True)

rows = []
seen = set()

for p in ROOT.rglob("*.json"):
    # skip common irrelevant dirs
    if any(part in SKIP_DIRS for part in p.parts):
        continue
    try:
        text = p.read_text(errors="ignore")
    except Exception:
        continue
    m = KEYWORD_RE.search(text)
    if not m:
        continue
    # determine destination path preserving relative structure
    rel = p.relative_to(ROOT)
    dest_path = DEST / rel
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    # avoid copying the same file twice
    if str(p) in seen:
        continue
    seen.add(str(p))
    try:
        shutil.copy2(p, dest_path)
    except Exception as e:
        # fallback: just write the text
        try:
            dest_path.write_text(text)
        except Exception:
            pass
    snippet_start = max(m.start() - 40, 0)
    snippet_end = m.end() + 40
    snippet = text[snippet_start:snippet_end].replace("\n", " ")
    rows.append((str(p), str(dest_path), snippet))

# write summary CSV
summary = DEST / "summary.csv"
with summary.open("w", newline="", encoding="utf-8") as fh:
    writer = csv.writer(fh)
    writer.writerow(["original_path", "copied_path", "match_snippet"])
    for r in rows:
        writer.writerow(r)

print(f"Found {len(rows)} matching JSON files. Copied to: {DEST}")
print(f"Summary saved to: {summary}")
