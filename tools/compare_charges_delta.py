#!/usr/bin/env python3
import os, csv, json, re
from glob import glob
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(__file__))
PROB_CSV = os.path.join(ROOT, 'analysis_output', 'eval_outcomes_probation_cases.csv')
OUT_DIR = os.path.join(ROOT, 'out')
OUT_DELTA = os.path.join(ROOT, 'analysis_output', 'probation_charge_deltas.csv')
OUT_TOP = os.path.join(ROOT, 'analysis_output', 'probation_charge_deltas_top_increases.csv')

KEY_CANDIDATE_KEYS = ['charges','counts','offenses','charges_list','charge_list']

def parse_ts_from_fname(fname):
    # fname like '2023-684826_20260101_124157.json' -> timestamp part after first '_'
    try:
        rest = fname.split('_',1)[1]
        ts = rest.rsplit('.',1)[0]
        # some have two parts YYYYMMDD_HHMMSS
        return datetime.strptime(ts, '%Y%m%d_%H%M%S')
    except Exception:
        try:
            return datetime.fromtimestamp(os.path.getmtime(os.path.join(fname)))
        except Exception:
            return None


def find_charge_list(data):
    # If dict and has known keys
    if isinstance(data, dict):
        for k in KEY_CANDIDATE_KEYS:
            if k in data and isinstance(data[k], list):
                return data[k]
        # search nested for lists of dicts that look like charges
        candidate = None
        def rec(obj):
            nonlocal candidate
            if candidate is not None:
                return
            if isinstance(obj, dict):
                for v in obj.values():
                    rec(v)
            elif isinstance(obj, list):
                # if list of dicts and items have 'statute' or 'description' or 'charge'
                if len(obj)>0 and isinstance(obj[0], dict):
                    keys = set().union(*(set(x.keys()) for x in obj if isinstance(x, dict)))
                    if any(k in keys for k in ('statute','description','charge','count','offense')):
                        candidate = obj
                        return
                for it in obj:
                    rec(it)
        rec(data)
        if candidate is not None:
            return candidate
    return None


def count_from_text(text):
    # fallback: count occurrences of "statute" or "charge"
    c = len(re.findall(r'"statute"', text, flags=re.I))
    c2 = len(re.findall(r'"charge"', text, flags=re.I))
    c3 = len(re.findall(r'\bCharge\b', text, flags=re.I))
    return max(c,c2,c3)


cases = []
if not os.path.exists(PROB_CSV):
    print('Missing', PROB_CSV); raise SystemExit(1)
with open(PROB_CSV, newline='', encoding='utf-8') as f:
    r = csv.DictReader(f)
    for row in r:
        cases.append(row['case_key'])

print('Probation cases to check:', len(cases))
rows = []
inc_count = 0
no_files = 0
for case_key in cases:
    # find matching files
    pattern = os.path.join(OUT_DIR, '*', f'{case_key}_*.json')
    files = glob(pattern)
    if not files:
        no_files += 1
        rows.append({'case_key': case_key, 'earliest_file':'', 'latest_file':'', 'earliest_count':0, 'latest_count':0, 'delta':0, 'sample_latest': ''})
        continue
    # sort files by parsed timestamp; fallback to filename sort
    def ts_for(fp):
        name = os.path.basename(fp)
        try:
            rest = name.split('_',1)[1].rsplit('.',1)[0]
            return datetime.strptime(rest, '%Y%m%d_%H%M%S')
        except Exception:
            return datetime.fromtimestamp(os.path.getmtime(fp))
    files_sorted = sorted(files, key=ts_for)
    earliest = files_sorted[0]
    latest = files_sorted[-1]
    e_count = 0
    l_count = 0
    sample_latest = ''
    # load earliest
    try:
        with open(earliest,'r',encoding='utf-8') as f:
            ed = json.load(f)
            elist = find_charge_list(ed)
            if elist is not None:
                e_count = len(elist)
            else:
                e_count = count_from_text(json.dumps(ed))
    except Exception:
        try:
            txt = open(earliest,'rb').read().decode('utf-8',errors='ignore')
            e_count = count_from_text(txt)
        except Exception:
            e_count = 0
    # load latest
    try:
        with open(latest,'r',encoding='utf-8') as f:
            ld = json.load(f)
            llist = find_charge_list(ld)
            if llist is not None:
                l_count = len(llist)
                # sample descriptions
                descs = []
                for it in llist[:5]:
                    if isinstance(it, dict):
                        desc = it.get('description') or it.get('statute') or it.get('charge') or str(it)
                    else:
                        desc = str(it)
                    descs.append(str(desc))
                sample_latest = ' | '.join(descs)[:800]
            else:
                txt = json.dumps(ld)
                l_count = count_from_text(txt)
    except Exception:
        try:
            txt = open(latest,'rb').read().decode('utf-8',errors='ignore')
            l_count = count_from_text(txt)
        except Exception:
            l_count = 0
    delta = l_count - e_count
    if delta > 0:
        inc_count += 1
    rows.append({'case_key': case_key, 'earliest_file': os.path.basename(earliest), 'latest_file': os.path.basename(latest), 'earliest_count': e_count, 'latest_count': l_count, 'delta': delta, 'sample_latest': sample_latest})

# write CSVs
os.makedirs(os.path.join(ROOT,'analysis_output'), exist_ok=True)
with open(OUT_DELTA,'w',newline='',encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['case_key','earliest_file','latest_file','earliest_count','latest_count','delta','sample_latest'])
    w.writeheader()
    for r in rows:
        w.writerow(r)
# top increases
rows_sorted = sorted(rows, key=lambda r: r['delta'], reverse=True)
with open(OUT_TOP,'w',newline='',encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['case_key','earliest_file','latest_file','earliest_count','latest_count','delta','sample_latest'])
    w.writeheader()
    for r in rows_sorted[:200]:
        w.writerow(r)

print('Total probation cases:', len(cases))
print('No files found for cases:', no_files)
print('Cases with charge increases:', inc_count)
print('Wrote:', OUT_DELTA)
print('Wrote:', OUT_TOP)
