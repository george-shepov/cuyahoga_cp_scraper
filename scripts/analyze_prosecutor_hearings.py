#!/usr/bin/env python3
import csv, json, os, re
from collections import defaultdict

base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
proc_csv = os.path.join(base, 'out', 'jasmine_jackson_prosecutor_cases.csv')
out_csv = os.path.join(base, 'out', 'jasmine_jackson_prosecutor_hearing_issues.csv')

date_rx = re.compile(r'(\d{1,2}/\d{1,2}/\d{2,4})')
set_rx = re.compile(r'\bSET FOR\b', re.I)
held_rx = re.compile(r'\bHELD\b', re.I)

rows_out = []
summary = defaultdict(int)

with open(proc_csv, newline='') as f:
    reader = csv.DictReader(f)
    for r in reader:
        case_id = r['case_id']
        year = r['year']
        path = os.path.join(base, r['file_path'])
        try:
            doc = json.load(open(path))
        except Exception as e:
            rows_out.append({'case_id':case_id,'year':year,'file_path':path,'issue_type':'error','date':'','set_desc':'','held_desc':f'error loading json: {e}'})
            summary['errors']+=1
            continue
        docket = doc.get('docket', []) or []
        set_dates = defaultdict(list)  # date -> descriptions
        held_dates = defaultdict(list)
        # scan docket entries
        for entry in docket:
            desc = (entry.get('description') or '')
            pd = (entry.get('proceeding_date') or '').strip()
            # extract any dates in description
            found_dates = date_rx.findall(desc)
            # if description contains SET FOR, record set_dates
            if set_rx.search(desc):
                # prefer explicit dates in description
                if found_dates:
                    for d in found_dates:
                        set_dates[d].append(desc)
                elif pd:
                    set_dates[pd].append(desc)
                else:
                    set_dates['unknown'].append(desc)
            # if description contains HELD, record held_dates using proceeding_date if available
            if held_rx.search(desc) or 'PRETRIAL HELD' in desc.upper():
                if found_dates:
                    for d in found_dates:
                        held_dates[d].append(desc)
                elif pd:
                    held_dates[pd].append(desc)
                else:
                    held_dates['unknown'].append(desc)
        # compare
        # any set_dates without matching held_dates -> set_not_held
        for sdate, sdescs in set_dates.items():
            if sdate not in held_dates:
                rows_out.append({'case_id':case_id,'year':year,'file_path':path,'issue_type':'set_not_held','date':sdate,'set_desc':' || '.join(sdescs),'held_desc':''})
                summary['set_not_held']+=1
        # any held_dates without matching set_dates -> held_without_set
        for hdate, hdescs in held_dates.items():
            if hdate not in set_dates:
                rows_out.append({'case_id':case_id,'year':year,'file_path':path,'issue_type':'held_without_set','date':hdate,'set_desc':'','held_desc':' || '.join(hdescs)})
                summary['held_without_set']+=1
        # also if neither sets nor helds found but docket contains dates with keywords like "SET" or "HELD" captured above none -> maybe ambiguous; skip

# write output
keys = ['case_id','year','file_path','issue_type','date','set_desc','held_desc']
with open(out_csv,'w',newline='') as f:
    w = csv.DictWriter(f, fieldnames=keys)
    w.writeheader()
    for row in rows_out:
        w.writerow(row)

# print summary
print('ANALYSIS COMPLETE')
print('Rows with issues:', len(rows_out))
for k,v in summary.items():
    print(k, v)
print('Output CSV:', out_csv)
