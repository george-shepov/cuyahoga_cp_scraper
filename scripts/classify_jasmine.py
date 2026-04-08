#!/usr/bin/env python3
import re,csv
from pathlib import Path
csvp = Path('out/jasmine_jackson_cases_2023_2025.csv')
if not csvp.exists():
    print('MISSING CSV:', csvp)
    raise SystemExit(1)
prosec = []
defend = []
ambig = []
for row in csv.DictReader(csvp.open(encoding='utf-8')):
    cid = row['case_id']
    year = row['year']
    fp = Path(row['file_path'])
    try:
        s = fp.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        s = row.get('match_snippet','')
    is_def = False
    if re.search(r'the state of ohio\s+vs\.?\s*jasmine', s, re.I) or re.search(r'vs\.?\s*jasmine', s, re.I) or re.search(r'v\.?\s*jasmine', s, re.I):
        is_def = True
    if re.search(r'jasmine\s+jackson.{0,120}defendant', s, re.I) or re.search(r'defendant.{0,120}jasmine\s+jackson', s, re.I):
        is_def = True
    is_proc = False
    if re.search(r'prosecut(or|ing)\s+attorney', s, re.I) and re.search(r'jasmine', s, re.I):
        is_proc = True
    if re.search(r'for\s+jasmine\s+jackson', s, re.I) or re.search(r'jasmine\s+jackson\s+present', s, re.I):
        is_proc = True
    if is_def and not is_proc:
        defend.append((cid,year,str(fp)))
    elif is_proc and not is_def:
        prosec.append((cid,year,str(fp)))
    elif is_def and is_proc:
        ambig.append((cid,year,str(fp)))
    else:
        if '"name": "JASMINE JACKSON"' in s or '"name": "JASMINE L JACKSON"' in s:
            prosec.append((cid,year,str(fp)))
        else:
            ambig.append((cid,year,str(fp)))
from collections import Counter
pcnt = Counter(y for _,y,_ in prosec)
dcnt = Counter(y for _,y,_ in defend)
acnt = Counter(y for _,y,_ in ambig)
print('SUMMARY')
for y in ['2023','2024','2025']:
    print(f"{y}: prosecutor={pcnt[y]}, defendant={dcnt[y]}, ambiguous={acnt[y]}")
print('\nTOTALS: prosecutor=%d defendant=%d ambiguous=%d' % (len(prosec), len(defend), len(ambig)))
# write lists
outp = Path('out')
outp.mkdir(parents=True, exist_ok=True)
with (outp/'jasmine_jackson_prosecutor_cases.csv').open('w', encoding='utf-8') as f:
    f.write('case_id,year,file_path\n')
    for r in prosec:
        f.write(','.join(r) + '\n')
with (outp/'jasmine_jackson_defendant_cases.csv').open('w', encoding='utf-8') as f:
    f.write('case_id,year,file_path\n')
    for r in defend:
        f.write(','.join(r) + '\n')
print('WROTE', outp/'jasmine_jackson_prosecutor_cases.csv', outp/'jasmine_jackson_defendant_cases.csv')
