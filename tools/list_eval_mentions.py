#!/usr/bin/env python3
import os
import json
import re
import csv
from glob import glob

ROOT = os.path.dirname(os.path.dirname(__file__))
OUT_GLOB = os.path.join(ROOT, 'out', '*', '*.json')
KEYWORDS = [
    r'eval', r'evaluation', r'competenc', r'competency', r'competent', r'psych', r'psychiat',
    r'mental health', r'mental[- ]?ill', r'behavioral health', r'forensic', r'competency evaluation'
]
PAT = re.compile('|'.join(KEYWORDS), flags=re.I)

stats = {}

files = glob(OUT_GLOB)
for fp in files:
    fname = os.path.basename(fp)
    case_key = fname.split('_')[0]  # e.g. '2023-684826'
    total = stats.setdefault(case_key, {'year': None, 'number': None, 'mention_count': 0, 'files_with_mentions': set(), 'sample_files': [], 'total_files': 0})
    try:
        year, num = case_key.split('-', 1)
        total['year'] = year
        total['number'] = num
    except Exception:
        total['year'] = ''
        total['number'] = case_key
    total['total_files'] += 1
    try:
        with open(fp, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        try:
            text = open(fp, 'rb').read().decode('utf-8', errors='ignore')
        except Exception:
            text = ''
    else:
        try:
            text = json.dumps(data)
        except Exception:
            text = str(data)
    matches = PAT.findall(text)
    if matches:
        total['mention_count'] += len(matches)
        total['files_with_mentions'].add(fp)
        if len(total['sample_files']) < 5:
            total['sample_files'].append(fp)

# prepare CSVs
rows = []
for case_key, v in stats.items():
    rows.append((case_key, v['year'], v['number'], v['mention_count'], len(v['files_with_mentions']), ';'.join(v['sample_files']), v['total_files']))

rows.sort(key=lambda r: r[3], reverse=True)

os.makedirs(os.path.join(ROOT, 'analysis_output'), exist_ok=True)
all_csv = os.path.join(ROOT, 'analysis_output', 'eval_mentions_all.csv')
top_csv = os.path.join(ROOT, 'analysis_output', 'eval_mentions_top200.csv')

with open(all_csv, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['case_key','year','case_number','mention_count','files_with_mentions_count','sample_files','total_files'])
    for r in rows:
        w.writerow(r)

with open(top_csv, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['case_key','year','case_number','mention_count','files_with_mentions_count','sample_files','total_files'])
    for r in rows[:200]:
        w.writerow(r)

print(f'Processed {len(files)} files; found {sum(1 for r in rows if r[3]>0)} cases with mentions')
print('Wrote:', all_csv)
print('Wrote:', top_csv)
