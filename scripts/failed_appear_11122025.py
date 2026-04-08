#!/usr/bin/env python3
import json
from pathlib import Path
import csv

root = Path(__file__).resolve().parents[1]
matches = {}

for p in root.rglob('out/**/*.json'):
    try:
        data = json.loads(p.read_text())
    except Exception:
        continue
    # support files where root is a dict or a list of dicts
    docket = []
    if isinstance(data, dict):
        docket = data.get('docket') or data.get('docket_entries') or []
    elif isinstance(data, list):
        # if root is a list, try to find a dict with docket
        for item in data:
            if isinstance(item, dict) and ('docket' in item or 'docket_entries' in item):
                docket = item.get('docket') or item.get('docket_entries') or []
                break
    # ensure docket is a list
    if not isinstance(docket, list):
        continue
    for entry in docket:
        desc = entry.get('description','') or entry.get('docket_description','') or ''
        date = entry.get('date','')
        if not isinstance(desc,str):
            continue
        if '11/12/2025' in desc or date == '11/12/2025':
            if 'failed to appear' in desc.lower():
                case_id = p.stem.split('_')[0]
                if case_id not in matches:
                    matches[case_id] = []
                matches[case_id].append({'file': str(p), 'date': date, 'desc': desc.strip()[:400]})

out_csv = root / 'other' / 'failed_appear_11-12-2025.csv'
out_csv.parent.mkdir(parents=True, exist_ok=True)
with out_csv.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['case_id','sample_file','sample_date','sample_description'])
    for case_id, entries in sorted(matches.items()):
        sample = entries[0]
        w.writerow([case_id, sample['file'], sample['date'], sample['desc']])

print(f"Found {len(matches)} unique cases with 'FAILED TO APPEAR' on 11/12/2025")
for case_id, entries in sorted(matches.items()):
    print(case_id)
    print('  sample:', entries[0]['sample_file'] if 'sample_file' in entries[0] else entries[0]['file'])
    print('  desc:', entries[0]['desc'])

print('CSV written to', out_csv)
