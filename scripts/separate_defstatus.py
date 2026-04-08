#!/usr/bin/env python3
import csv
import os

ROOT = os.getcwd()
in_path = os.path.join(ROOT, 'other', 'defn_capias_by_year.csv')
out_na = os.path.join(ROOT, 'other', 'defn_capias_defstatus_NA.csv')
out_capias = os.path.join(ROOT, 'other', 'defn_capias_defstatus_CAPIAS.csv')

if not os.path.exists(in_path):
    raise SystemExit(f"Input not found: {in_path}")

na_rows = []
capias_rows = []

with open(in_path, newline='') as fh:
    reader = csv.DictReader(fh)
    for row in reader:
        ds = (row.get('def_status') or '').strip().upper()
        # treat empty or explicit N/A as NA group
        if ds == '' or ds == 'N/A':
            na_rows.append(row)
        elif 'CAPIAS' in ds:
            capias_rows.append(row)
        else:
            # put others into NA for now
            na_rows.append(row)

def write(path, rows):
    if not rows:
        open(path, 'w').close()
        return
    with open(path, 'w', newline='') as outfh:
        writer = csv.DictWriter(outfh, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

write(out_na, na_rows)
write(out_capias, capias_rows)

print(f"Wrote {len(na_rows)} rows to: {out_na}")
print(f"Wrote {len(capias_rows)} rows to: {out_capias}")
