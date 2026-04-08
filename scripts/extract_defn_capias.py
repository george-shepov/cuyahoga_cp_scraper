#!/usr/bin/env python3
import csv
import os

ROOT = os.getcwd()
files = [
    os.path.join(ROOT, 'other', '2023_cases_comprehensive.csv'),
    os.path.join(ROOT, 'other', '2024_cases_comprehensive.csv'),
    os.path.join(ROOT, 'other', '2025_cases_comprehensive.csv'),
]

out_path = os.path.join(ROOT, 'other', 'defn_capias_by_year.csv')

results = {}

for fp in files:
    if not os.path.exists(fp):
        continue
    year = os.path.basename(fp).split('_')[0]
    results.setdefault(year, [])
    with open(fp, newline='') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            status = (row.get('case_status') or '').strip().upper()
            if status == 'DEFN CAPIAS':
                results[year].append({
                    'case_number': row.get('case_number',''),
                    'def_status': row.get('def_status',''),
                    'defendant_name': row.get('defendant_name',''),
                    'first_docket_date': row.get('first_docket_date',''),
                    'last_docket_date': row.get('last_docket_date',''),
                })

# write summary CSV
with open(out_path, 'w', newline='') as outfh:
    fieldnames = ['year','case_number','def_status','defendant_name','first_docket_date','last_docket_date']
    writer = csv.DictWriter(outfh, fieldnames=fieldnames)
    writer.writeheader()
    for year in sorted(results.keys()):
        for r in results[year]:
            row = {'year': year}
            row.update(r)
            writer.writerow(row)

# print counts
for year in sorted(results.keys()):
    print(f"{year}: {len(results[year])} cases (DEFN CAPIAS)")

print(f"Wrote summary to: {out_path}")
