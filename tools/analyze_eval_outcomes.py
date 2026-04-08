#!/usr/bin/env python3
import os, csv, json, re
from glob import glob

ROOT = os.path.dirname(os.path.dirname(__file__))
EVAL_CSV = os.path.join(ROOT, 'analysis_output', 'eval_mentions_all.csv')
OUT_DIR = os.path.join(ROOT, 'out')
PAT_PROB = re.compile(r'\bprobation\b', re.I)
PAT_JASMINE = re.compile(r'jasmine\s+jackson', re.I)

cases = []
if not os.path.exists(EVAL_CSV):
    print('Missing', EVAL_CSV)
    raise SystemExit(1)

with open(EVAL_CSV, newline='', encoding='utf-8') as f:
    r = csv.DictReader(f)
    for row in r:
        # row fields: case_key,year,case_number,mention_count,files_with_mentions_count,sample_files,total_files
        try:
            mention_count = int(row.get('mention_count') or 0)
        except Exception:
            mention_count = 0
        cases.append({'case_key': row['case_key'], 'year': row.get('year',''), 'case_number': row.get('case_number',''), 'mention_count': mention_count})

print('Scanning', len(cases), 'cases...')
summary_rows = []
probation_rows = []
count_probation = 0
count_jasmine = 0

for c in cases:
    case_key = c['case_key']
    year = c['year']
    # find files for this case
    pattern = os.path.join(OUT_DIR, '*', f'{case_key}_*.json')
    files = glob(pattern)
    probation_found = False
    probation_context = ''
    attorneys = set()
    outcome_snippets = set()
    jasmine_present = False
    for fp in files:
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            try:
                txt = open(fp, 'rb').read().decode('utf-8', errors='ignore')
            except Exception:
                txt = ''
        else:
            txt = json.dumps(data)
            # extract attorneys heuristically
            if isinstance(data, dict):
                for k,v in data.items():
                    if isinstance(v, list):
                        for item in v:
                            if isinstance(item, dict):
                                name = item.get('name') or item.get('attorney') or item.get('full_name')
                                if name:
                                    attorneys.add(name.strip())
                # possible outcome fields
                for key in ('outcome','case_outcome','final_status','disposition','disposition_text','outcome_text'):
                    val = data.get(key)
                    if val:
                        outcome_snippets.add(str(val))
        # search text for probation
        if PAT_PROB.search(txt):
            probation_found = True
            if not probation_context:
                # take a short snippet
                m = PAT_PROB.search(txt)
                start = max(0, m.start()-60)
                probation_context = txt[start:m.end()+60].replace('\n',' ')[:400]
        # search for jasmine
        if PAT_JASMINE.search(txt):
            jasmine_present = True
    if probation_found:
        count_probation += 1
    if jasmine_present:
        count_jasmine += 1
    summary_rows.append({'case_key': case_key, 'mention_count': c['mention_count'], 'total_files': len(files), 'probation_found': int(probation_found), 'jasmine_present': int(jasmine_present), 'attorneys': ';'.join(sorted(attorneys))[:1000], 'outcome_snippets': ';'.join(list(outcome_snippets))[:1000], 'probation_context': probation_context})
    if probation_found:
        probation_rows.append(summary_rows[-1])

# write outputs
os.makedirs(os.path.join(ROOT,'analysis_output'), exist_ok=True)
out_sum = os.path.join(ROOT,'analysis_output','eval_outcomes_summary.csv')
out_prob = os.path.join(ROOT,'analysis_output','eval_outcomes_probation_cases.csv')
with open(out_sum, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['case_key','mention_count','total_files','probation_found','jasmine_present','attorneys','outcome_snippets','probation_context'])
    w.writeheader()
    for r in summary_rows:
        w.writerow(r)
with open(out_prob, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['case_key','mention_count','total_files','probation_found','jasmine_present','attorneys','outcome_snippets','probation_context'])
    w.writeheader()
    for r in probation_rows:
        w.writerow(r)

print('Total cases scanned:', len(cases))
print('Probation found in cases:', count_probation)
print('Cases with Jasmine Jackson mention:', count_jasmine)
print('Wrote:', out_sum)
print('Wrote:', out_prob)
