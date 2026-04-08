#!/usr/bin/env python3
import csv, json, os
from collections import defaultdict

target = "jasmine jackson"
base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
index = os.path.join(base, 'out', 'jasmine_jackson_cases_2023_2025.csv')
out_proc = os.path.join(base, 'out', 'jasmine_jackson_prosecutor_cases.csv')
out_def = os.path.join(base, 'out', 'jasmine_jackson_defendant_cases.csv')
out_amb = os.path.join(base, 'out', 'jasmine_jackson_ambiguous_cases.csv')

counts = defaultdict(lambda: {'proc':0,'def':0,'amb':0})
rows_proc=[]
rows_def=[]
rows_amb=[]

with open(index, newline='') as f:
    reader = csv.DictReader(f)
    for r in reader:
        case_id = r['case_id']
        year = r['year']
        path = os.path.join(base, r['file_path'])
        role = 'ambiguous'
        reason = ''
        try:
            with open(path) as jf:
                doc = json.load(jf)
        except Exception as e:
            reason = f'error loading json: {e}'
            rows_amb.append({**r,'reason':reason})
            counts[year]['amb']+=1
            continue
        # 1) check case caption / summary fields for "THE STATE OF OHIO vs. JASMINE JACKSON"
        cap = ''
        try:
            # summary.fields may contain caption-like entries
            fields = doc.get('summary', {}).get('fields', {})
            # some cases have a mapping like "CR-25-705153-A": "THE STATE OF OHIO vs. JASMINE JACKSON"
            for v in fields.values():
                if isinstance(v, str) and target in v.lower():
                    # if value also contains 'THE STATE OF OHIO' treat as defendant
                    if 'the state of ohio' in v.lower():
                        role = 'defendant'
                        reason = 'case caption indicates defendant'
                        break
            if role == 'defendant':
                rows_def.append({**r,'reason':reason})
                counts[year]['def']+=1
                continue
        except Exception:
            pass
        # 2) check attorneys array for name match and party/role
        try:
            attys = doc.get('attorneys', [])
            found = None
            for a in attys:
                name = (a.get('name') or '').lower()
                if target in name:
                    # check party/role
                    party = (a.get('party') or '').lower()
                    role_field = (a.get('role') or '').lower()
                    if 'prosecut' in party or 'prosecut' in role_field or 'state' in party:
                        role = 'prosecutor'
                        reason = 'attorneys array: prosecutor'
                        found = True
                        break
                    elif 'defen' in party or 'defend' in role_field or 'defense' in party:
                        role = 'defendant'
                        reason = 'attorneys array: defense'
                        found = True
                        break
                    else:
                        found = True
                        # ambiguous via attorneys list
                        reason = 'attorneys array: name present but ambiguous party/role'
            if found:
                if role == 'prosecutor':
                    rows_proc.append({**r,'reason':reason})
                    counts[year]['proc']+=1
                elif role == 'defendant':
                    rows_def.append({**r,'reason':reason})
                    counts[year]['def']+=1
                else:
                    rows_amb.append({**r,'reason':reason})
                    counts[year]['amb']+=1
                continue
        except Exception:
            pass
        # 3) check docket descriptions for prosecuting attorney mention or "THE STATE OF OHIO vs."
        try:
            dockets = doc.get('docket', [])
            foundp = False
            foundd = False
            for d in dockets:
                desc = (d.get('description') or '').lower()
                if target in desc:
                    if 'prosecut' in desc or 'prosecuting attorney' in desc:
                        foundp = True
                    if 'the state of ohio' in desc:
                        foundd = True
            if foundd and not foundp:
                role='defendant'
                reason='docket description shows state vs. name'
                rows_def.append({**r,'reason':reason})
                counts[year]['def']+=1
                continue
            if foundp and not foundd:
                role='prosecutor'
                reason='docket description shows prosecuting attorney present'
                rows_proc.append({**r,'reason':reason})
                counts[year]['proc']+=1
                continue
            if foundp and foundd:
                role='ambiguous'
                reason='both defendant and prosecuting mentions'
                rows_amb.append({**r,'reason':reason})
                counts[year]['amb']+=1
                continue
        except Exception:
            pass
        # fallback: ambiguous
        rows_amb.append({**r,'reason':'no structured match'})
        counts[year]['amb']+=1

# write outputs
keys = ['case_id','year','file_path','match_snippet','reason']
for path, rows in [(out_proc, rows_proc),(out_def, rows_def),(out_amb, rows_amb)]:
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for row in rows:
            # ensure keys
            write_row = {k: row.get(k,'') for k in keys}
            w.writerow(write_row)

# print summary
total_proc = sum(c['proc'] for c in counts.values())
total_def = sum(c['def'] for c in counts.values())
total_amb = sum(c['amb'] for c in counts.values())
print('SUMMARY')
for y in sorted(counts):
    c = counts[y]
    print(f"{y}: prosecutor={c['proc']}, defendant={c['def']}, ambiguous={c['amb']}")
print('TOTALS: prosecutor=%d defendant=%d ambiguous=%d' % (total_proc, total_def, total_amb))
