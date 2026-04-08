#!/usr/bin/env python3
import os, re, csv, collections

OUT_DIR = 'other'
MASTER_CSV = os.path.join(OUT_DIR, 'lori_klodnik_matches.csv')
BY_YEAR_DIR = os.path.join(OUT_DIR, 'lori_klodnik_by_year')
os.makedirs(BY_YEAR_DIR, exist_ok=True)

pattern_case = re.compile(r'CR-\d{2}-\d{6}(?:-[A-Z])?', re.IGNORECASE)
pattern_kl = re.compile(r'klodnik', re.IGNORECASE)

agg_files = []
agg_cases = collections.defaultdict(lambda: {'total':0,'files':set()})

for root, dirs, files in os.walk('out'):
    for fn in files:
        path = os.path.join(root, fn)
        try:
            with open(path, 'r', errors='ignore') as f:
                txt = f.read()
        except Exception:
            continue
        matches = len(pattern_kl.findall(txt))
        if matches == 0:
            continue
        m_case = pattern_case.search(txt)
        case = m_case.group(0).upper() if m_case else ''
        year = ''
        if case:
            year = '20' + case.split('-')[1]
        agg_files.append((path, matches, case, year))
        if case:
            agg_cases[case]['total'] += matches
            agg_cases[case]['files'].add(path)

# write master CSV (one row per matching file)
with open(MASTER_CSV, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['file_path','match_count','case_number','year'])
    for row in sorted(agg_files):
        w.writerow(row)

# write per-year unique-case CSVs
years = collections.defaultdict(list)
for case, info in agg_cases.items():
    yy = 'unknown'
    m = re.match(r'CR-(\d{2})-', case)
    if m:
        yy = '20' + m.group(1)
    years[yy].append((case, info))

for y, items in years.items():
    outp = os.path.join(BY_YEAR_DIR, f'lorik_unique_{y}.csv')
    with open(outp, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['case_number','total_matches','num_files','file_paths'])
        for case, info in sorted(items):
            w.writerow([case, info['total'], len(info['files']), ';'.join(sorted(info['files']))])

print(f'FOUND_FILES={len(agg_files)} UNIQUE_CASES={len(agg_cases)} YEARS={len(years)}')
