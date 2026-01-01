#!/usr/bin/env python3
"""
Export two parallel datasets from latest JSON per case:
- private dataset (includes PII fields)
- clean dataset (PII removed, long text truncated)

Outputs:
- cases_private.csv.gz
- cases_clean.csv.gz
- json_fields_manifest.json

Defaults: clean text truncation = 1000 chars
"""
import os, glob, json, re, gzip, csv, time
from collections import defaultdict

ROOT = os.path.abspath(os.path.dirname(__file__))
OUT_GLOB = os.path.join(ROOT, 'out', '**', '*.json')
TS_RE = re.compile(r'([0-9]{8}_[0-9_]{6,})')
CR_RE = re.compile(r'(CR-\d{2}-\d{6,}-[A-Z])')

# Fields to include
COMMON_FIELDS = [
    'case_number','defendant_name','judge','prosecutor','attorneys',
    'case_status','defendant_status','charges','charges_short','outcome',
    'disposition','court_date','filing_date','sentencing','fees','fees_charged',
    'reparations','bond_amount','bail','counts'
]

PII_FIELDS = [
    'address','defendant_address','victim_address','phone','defendant_phone','victim_phone',
    'email','attorney_contact','contact_info','dob','date_of_birth','ssn','social_security',
    'raw_text','transcript','notes_full'
]

# Clean fields will include COMMON_FIELDS + a short `case_summary` and `notes_trunc`.
CLEAN_EXTRA = ['case_summary','notes_trunc']

TRUNCATE_CLEAN = 1000


def extract_case_and_ts(path):
    case = None
    ts = ''
    try:
        with open(path, encoding='utf-8') as fh:
            j = json.load(fh)
    except Exception:
        j = None
    if isinstance(j, dict):
        for key in ['case_number','case_num','case','caseNo','case_number_raw']:
            if key in j and j[key]:
                case = str(j[key]).strip(); break
        if not case:
            # search for CR- pattern in values
            def find_cr(obj):
                if isinstance(obj, str):
                    m = CR_RE.search(obj)
                    if m: return m.group(1)
                elif isinstance(obj, dict):
                    for v in obj.values():
                        r = find_cr(v)
                        if r: return r
                elif isinstance(obj, list):
                    for v in obj:
                        r = find_cr(v)
                        if r: return r
                return None
            case = find_cr(j)
    if not case:
        case = os.path.basename(path)
    m = TS_RE.search(os.path.basename(path))
    if m:
        ts = m.group(1)
    else:
        try:
            ts = str(int(os.path.getmtime(path)))
        except Exception:
            ts = ''
    return case, ts


def deep_find_key(obj, key):
    """Search nested dict/list for a key name (case-insensitive). Return first match."""
    if obj is None:
        return None
    lk = key.lower()
    if isinstance(obj, dict):
        for k,v in obj.items():
            if k.lower() == lk:
                return v
        for v in obj.values():
            r = deep_find_key(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = deep_find_key(v, key)
            if r is not None:
                return r
    return None


def find_top_key(obj, key):
    if not isinstance(obj, dict):
        return None
    lk = key.lower()
    for k,v in obj.items():
        if k.lower() == lk:
            return v
    return None


def norm_val(v):
    if v is None:
        return ''
    if isinstance(v, (list, dict)):
        try:
            return json.dumps(v, ensure_ascii=False)
        except Exception:
            return str(v)
    return str(v)


def build_latest_map():
    files = glob.glob(OUT_GLOB, recursive=True)
    case_map = {}
    for p in files:
        case, ts = extract_case_and_ts(p)
        prev = case_map.get(case)
        if prev is None:
            case_map[case] = (ts, p)
        else:
            if ts and prev[0] and ts > prev[0]:
                case_map[case] = (ts, p)
            else:
                try:
                    if os.path.getmtime(p) > os.path.getmtime(prev[1]):
                        case_map[case] = (ts, p)
                except Exception:
                    pass
    return case_map


def collect_fields(jobj, fields, deep=False, truncate=None):
    row = {}
    for f in fields:
        v = find_top_key(jobj, f)
        if v is None and deep:
            v = deep_find_key(jobj, f)
        if v is None:
            row[f] = ''
        else:
            s = norm_val(v)
            if truncate and isinstance(s, str) and len(s) > truncate:
                s = s[:truncate]
            row[f] = s
    return row


def main():
    manifest = defaultdict(int)
    case_map = build_latest_map()
    json_objs = {}
    for case,(ts,path) in case_map.items():
        try:
            with open(path, encoding='utf-8') as fh:
                json_objs[case] = json.load(fh)
        except Exception:
            try:
                with open(path, encoding='utf-8', errors='ignore') as fh:
                    json_objs[case] = {'_raw_text': fh.read()}
            except Exception:
                json_objs[case] = None

    total = len(json_objs)
    print('Latest JSON objects found:', total)

    # Prepare fieldnames
    private_fnames = ['case_number'] + COMMON_FIELDS + PII_FIELDS
    clean_fnames = ['case_number'] + COMMON_FIELDS + CLEAN_EXTRA

    # Ensure uniqueness and order
    private_fnames = list(dict.fromkeys(private_fnames))
    clean_fnames = list(dict.fromkeys(clean_fnames))

    # Write gzipped CSVs
    priv_path = os.path.join(ROOT, 'cases_private.csv.gz')
    clean_path = os.path.join(ROOT, 'cases_clean.csv.gz')

    with gzip.open(priv_path, 'wt', encoding='utf-8', newline='') as pfp, \
         gzip.open(clean_path, 'wt', encoding='utf-8', newline='') as cfp:
        priv_writer = csv.DictWriter(pfp, fieldnames=private_fnames)
        clean_writer = csv.DictWriter(cfp, fieldnames=clean_fnames)
        priv_writer.writeheader(); clean_writer.writeheader()

        priv_count = 0; clean_count = 0
        for case, jobj in json_objs.items():
            if not jobj:
                continue
            # ensure jobj is dict
            if isinstance(jobj, dict):
                # canonical case_number
                cn = ''
                for cand in ['case_number','case_num','case','caseNo','case_number_raw']:
                    v = find_top_key(jobj, cand)
                    if v:
                        cn = str(v).strip(); break
                if not cn:
                    cn = case
                # collect common
                common_row = collect_fields(jobj, COMMON_FIELDS, deep=True)
                common_row['case_number'] = cn

                # private row
                priv_row = {k: '' for k in private_fnames}
                priv_row.update(common_row)
                pii_row = collect_fields(jobj, PII_FIELDS, deep=True, truncate=None)
                priv_row.update(pii_row)
                priv_writer.writerow(priv_row)
                priv_count += 1

                # clean row: exclude PII and truncate long texts
                clean_row = {k: '' for k in clean_fnames}
                clean_row.update(common_row)
                # attempt to pull a short summary/notes
                summary = deep_find_key(jobj, 'case_summary') or deep_find_key(jobj, 'summary') or deep_find_key(jobj, 'notes') or deep_find_key(jobj, 'case_text')
                if summary:
                    s = norm_val(summary)
                    if len(s) > TRUNCATE_CLEAN:
                        s = s[:TRUNCATE_CLEAN]
                else:
                    s = ''
                clean_row['case_summary'] = s
                clean_row['notes_trunc'] = s
                clean_writer.writerow(clean_row)
                clean_count += 1

                # manifest counts
                for k in list(jobj.keys()):
                    manifest[k] += 1
            else:
                # non-dict: skip for now
                continue

    # write manifest of top-level json keys and counts
    manifest_path = os.path.join(ROOT, 'json_fields_manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as mf:
        json.dump({'total_cases': total, 'field_counts': dict(manifest)}, mf, indent=2, ensure_ascii=False)

    print('Wrote:', priv_path, 'rows=', priv_count)
    print('Wrote:', clean_path, 'rows=', clean_count)
    print('Wrote manifest:', manifest_path)


if __name__ == '__main__':
    main()
