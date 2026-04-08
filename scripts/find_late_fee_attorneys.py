#!/usr/bin/env python3
import json
from pathlib import Path
import re
import csv
from datetime import datetime

root = Path(__file__).resolve().parents[1]
pattern_keywords = re.compile(r'ATTORNEY FEE|ATTORNEY FEE BILL|FEE BILL SUBMITTED|BE ALLOWED|ORDERED THAT .* BE ALLOWED|CERTIFY SAID AMOUNT|ALLOWED .* FOR SERVICES|ATTORNEY FEE BILL SUBMITTED', re.I)
allcaps_name = re.compile(r"\b([A-Z][A-Z]+(?: [A-Z][A-Z]+){1,4})\b")
results = {}

for p in root.rglob('out/**/*.json'):
    try:
        data = json.loads(p.read_text())
    except Exception:
        continue
    # determine case id
    case_id = None
    summary = None
    if isinstance(data, dict):
        summary = data.get('summary') or {}
    elif isinstance(data, list):
        # try first dict with summary
        for item in data:
            if isinstance(item, dict) and 'summary' in item:
                summary = item.get('summary')
                data = item
                break
    if isinstance(summary, dict):
        case_id = summary.get('case_number') or summary.get('case_number_text')
        case_year = summary.get('year')
    if not case_id:
        # fall back to filename
        case_id = p.stem.split('_')[0]
    # parse case year
    if not case_year:
        m = re.search(r'CR-(\d{2})-', case_id)
        if m:
            yy = int(m.group(1))
            case_year = 2000 + yy if yy < 70 else 1900 + yy
        else:
            # try first 4-digit in filename path
            m2 = re.search(r'/out/(\d{4})/', str(p))
            case_year = int(m2.group(1)) if m2 else None
    try:
        case_year = int(case_year) if case_year else None
    except:
        case_year = None

    # attorneys listed on case
    listed_attorneys = set()
    attorneys = []
    if isinstance(data, dict):
        attorneys = data.get('attorneys') or []
    elif isinstance(data, list):
        # try to find attorneys list inside
        for item in data:
            if isinstance(item, dict) and 'attorneys' in item:
                attorneys = item.get('attorneys') or []
                break
    if isinstance(attorneys, list):
        for a in attorneys:
            if isinstance(a, dict):
                name = a.get('name') or a.get('attorney')
            else:
                name = a
            if name:
                listed_attorneys.add(name.strip().upper())

    # docket
    docket = []
    if isinstance(data, dict):
        docket = data.get('docket') or data.get('docket_entries') or []
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and ('docket' in item or 'docket_entries' in item):
                docket = item.get('docket') or item.get('docket_entries') or []
                break
    if not isinstance(docket, list):
        continue

    for entry in docket:
        desc = entry.get('description','') or entry.get('docket_description','') or ''
        date = entry.get('date','')
        if not desc or not isinstance(desc, str):
            continue
        if not pattern_keywords.search(desc):
            continue
        # parse entry year
        entry_year = None
        m = re.search(r'(\d{1,2}/\d{1,2}/(\d{4}))', desc)
        if m:
            try:
                entry_year = int(m.group(2))
            except:
                entry_year = None
        if not entry_year and date:
            try:
                entry_year = int(date.split('/')[-1])
            except:
                entry_year = None
        # check two+ years after case year if available
        if case_year and entry_year and (entry_year - case_year) < 2:
            continue
        # extract all-caps name candidates near keywords
        candidates = set()
        # search description for NAME, ESQ or NAME patterns
        for m in re.finditer(r"([A-Z][A-Z]+(?: [A-Z][A-Z]+){1,4})(?:,? ESQ\.|,? ESQ\b)?", desc):
            name = m.group(1).strip()
            # filter false positives that are common words
            if name.upper() in ('ATTORNEY','COURT','DEFENDANT','PROSECUTOR','VICTIM','THE','STATE','THIS','ORDER'):
                continue
            candidates.add(name.upper())
        # also try pattern 'ATTORNEY FEE BILL SUBMITTED FALLON RADIGAN' etc
        m2 = re.search(r'ATTORNEY FEE BILL SUBMITTED\s+([A-Z][A-Z]+(?: [A-Z][A-Z]+){0,3})', desc, re.I)
        if m2:
            candidates.add(m2.group(1).strip().upper())
        # if found candidate not in listed_attorneys, record
        for cand in candidates:
            if cand not in listed_attorneys:
                key = cand
                if key not in results:
                    results[key] = []
                results[key].append({'case_id': case_id, 'file': str(p), 'date': date or entry.get('date',''), 'desc': desc.strip()[:800], 'listed_attorneys': list(listed_attorneys)[:5]})

# write CSV of findings
out_csv = root / 'other' / 'late_fee_attorneys.csv'
out_csv.parent.mkdir(parents=True, exist_ok=True)
with out_csv.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['name','case_id','file','entry_date','description','listed_attorneys_sample'])
    for name, recs in sorted(results.items()):
        for r in recs:
            w.writerow([name, r['case_id'], r['file'], r['date'], r['desc'], ";".join(r['listed_attorneys'])])

# create tar.gz with unique case JSONs
cases = set(r['file'] for recs in results.values() for r in recs)
archive = root / 'other' / 'late_fee_attorneys_raw_jsons.tar.gz'
if cases:
    import subprocess
    cmd = ['tar','-czf', str(archive)] + sorted(cases)
    subprocess.run(cmd, check=False)

print(f"Found {len(results)} unique names; {len(cases)} files matched. CSV: {out_csv}; archive: {archive}")
