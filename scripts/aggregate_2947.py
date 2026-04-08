#!/usr/bin/env python3
import csv, os, re, collections

IN_CSV = "other/2947_06_matches_with_case.csv"
OUT_ALL = "other/2947_06_unique_cases.csv"
BY_YEAR_DIR = "other/2947_06_by_year"

os.makedirs(BY_YEAR_DIR, exist_ok=True)

agg = {}
with open(IN_CSV, newline='') as f:
    reader = csv.DictReader(f)
    for r in reader:
        case = r.get('case_number', '').strip()
        if not case:
            continue
        try:
            cnt = int(r.get('match_count') or 0)
        except:
            cnt = 0
        ent = agg.setdefault(case, {'total': 0, 'files': set()})
        ent['total'] += cnt
        ent['files'].add(r.get('file_path', ''))

with open(OUT_ALL, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['case_number', 'total_matches', 'num_files', 'file_paths', 'year'])
    for case in sorted(agg.keys()):
        info = agg[case]
        files = ';'.join(sorted(info['files']))
        m = re.match(r'CR-(\d{2})-', case)
        year = ('20' + m.group(1)) if m else ''
        w.writerow([case, info['total'], len(info['files']), files, year])

years = collections.defaultdict(list)
for case, info in agg.items():
    m = re.match(r'CR-(\d{2})-', case)
    year = ('20' + m.group(1)) if m else 'unknown'
    years[year].append((case, info))

for y, items in years.items():
    path = os.path.join(BY_YEAR_DIR, f"2947_06_unique_{y}.csv")
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['case_number', 'total_matches', 'num_files', 'file_paths'])
        for case, info in sorted(items):
            files = ';'.join(sorted(info['files']))
            w.writerow([case, info['total'], len(info['files']), files])

print(f"WROTE {OUT_ALL} and {len(years)} per-year files to {BY_YEAR_DIR}")
