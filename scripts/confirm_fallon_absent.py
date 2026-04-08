#!/usr/bin/env python3
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / 'out' / '2023'
INPUT_CSV = ROOT / 'other' / 'fallon_radigan_billing.csv'
OUTPUT_CSV = ROOT / 'other' / 'fallon_confirmed_absent_2023.csv'

FALLON_TOKEN = 'FALLON RADIGAN'
AMT_RE = re.compile(r"\$\s*[0-9,]+(?:\.\d{2})?")
BILLING_PHRASES = [
    'ATTORNEY FEE BILL', 'ATTORNEY FEE BILL SUBMITTED', 'BE ALLOWED', 'CERTIFY SAID AMOUNT',
    'ATTORNEY FEE', 'ATTORNEY FEE BILL SUBMITTED', 'ATTORNEY FEE ALLOWED'
]


def norm_name(s: str) -> str:
    if not s:
        return ''
    s = re.sub(r"\s+", ' ', s.strip())
    s = re.sub(r"\bESQ\.?\b", '', s, flags=re.I)
    s = re.sub(r"[^A-Z0-9 ]", '', s.upper())
    s = re.sub(r"\s+", ' ', s).strip()
    return s


def extract_attorneys_from_json(obj, raw_text):
    names = set()
    # JSON attorneys array
    for k in ('attorneys', 'attys', 'attorney'):
        arr = obj.get(k)
        if isinstance(arr, list):
            for a in arr:
                if isinstance(a, dict):
                    n = a.get('name') or a.get('attorney') or a.get('full_name')
                    if n:
                        names.add(norm_name(n))
                elif isinstance(a, str):
                    names.add(norm_name(a))
    # prosecutor field
    for pk in ('prosecutor', 'prosecutors'):
        p = obj.get(pk)
        if isinstance(p, str):
            names.add(norm_name(p))
    # fallback: search raw_text for common span/label patterns
    for m in re.findall(r'>([^<>]{3,80}RADIGAN[^<>]{0,10})<', raw_text, flags=re.I):
        names.add(norm_name(m))
    # generic name capture in raw_text for attorneys table
    for m in re.findall(r'([A-Z\s]{3,50}RADIGAN)', raw_text, flags=re.I):
        names.add(norm_name(m))
    return names


def find_billing_lines(obj, raw_text):
    hits = []
    docket = obj.get('docket') or obj.get('dockets') or []
    if isinstance(docket, list) and docket:
        for entry in docket:
            txt = ''
            if isinstance(entry, dict):
                txt = ' '.join(str(entry.get(k, '')) for k in ('description', 'details', 'text') if entry.get(k))
                date = entry.get('date') or entry.get('entry_date') or ''
            else:
                txt = str(entry)
                date = ''
            u = txt.upper()
            if FALLON_TOKEN.split()[0] in u and any(p in u for p in BILLING_PHRASES):
                amt = AMT_RE.search(u)
                hits.append((date, txt.strip(), amt.group(0) if amt else ''))
            else:
                # also catch lines that mention FALLON and a $ amount
                if FALLON_TOKEN.split()[0] in u and AMT_RE.search(u):
                    amt = AMT_RE.search(u)
                    hits.append((date, txt.strip(), amt.group(0) if amt else ''))
    else:
        # fallback: search raw_text for billing phrases and Fallon
        for m in re.finditer(r'(.{0,120}?FALLON[^.\n]{0,120}?(?:' + '|'.join(map(re.escape, BILLING_PHRASES)) + r')[^.\n]{0,120}?(\$[0-9,\.]*)?)', raw_text, flags=re.I):
            snippet = m.group(0)
            amt_m = AMT_RE.search(snippet)
            hits.append(('', snippet.strip(), amt_m.group(0) if amt_m else ''))
    return hits


def main():
    rows = []
    with open(INPUT_CSV, newline='') as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r.get('Year') != '2023':
                continue
            rows.append(r)

    out_rows = []
    for r in rows:
        case = r['Case Number']
        # case number like CR-23-677573-A -> want 677573
        m = re.search(r'CR-\d{2}-(\d+)', case)
        if not m:
            continue
        num = m.group(1)
        matched = list(OUT_DIR.glob(f'2023-{num}_*.json'))
        if not matched:
            matched = [p for p in OUT_DIR.iterdir() if p.name.startswith(f'2023-{num}_')]
        for fp in matched:
            try:
                raw = fp.read_text(errors='ignore')
                obj = json.loads(raw)
            except Exception:
                try:
                    jstart = raw.find('{')
                    obj = json.loads(raw[jstart:])
                except Exception:
                    continue
            roster = extract_attorneys_from_json(obj, raw)
            roster_has_fallon = any('FALLON RADIGAN' in n for n in roster)
            # detect prosecutor presence explicitly
            prosecutor_names = set()
            p = obj.get('prosecutor') or obj.get('prosecutors')
            if isinstance(p, str):
                prosecutor_names.add(norm_name(p))
            if isinstance(p, list):
                for it in p:
                    prosecutor_names.add(norm_name(it if isinstance(it, str) else it.get('name','')))
            fallon_is_pros = any('FALLON RADIGAN' in n for n in prosecutor_names)

            hits = find_billing_lines(obj, raw)
            if hits:
                for date, txt, amt in hits:
                    out_rows.append({
                        'Case': case,
                        'File': str(fp.relative_to(ROOT)),
                        'DocketDate': date,
                        'DocketText': txt,
                        'Amount': amt,
                        'FallonInRoster': 'Y' if roster_has_fallon else 'N',
                        'FallonIsProsecutor': 'Y' if fallon_is_pros else 'N'
                    })

    # write results
    with open(OUTPUT_CSV, 'w', newline='') as f:
        fieldnames = ['Case', 'File', 'DocketDate', 'DocketText', 'Amount', 'FallonInRoster', 'FallonIsProsecutor']
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for rr in out_rows:
            w.writerow(rr)

    print('Wrote', OUTPUT_CSV)


if __name__ == '__main__':
    main()
