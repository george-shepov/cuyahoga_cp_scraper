#!/usr/bin/env python3
import csv
import re
from pathlib import Path
from collections import defaultdict

root = Path(__file__).resolve().parents[1]
csv_in = root / 'other' / 'late_fee_attorneys.csv'
if not csv_in.exists():
    print('Input CSV not found:', csv_in)
    raise SystemExit(1)

# heuristics to detect person-like names (all-caps tokens, 1-3 tokens, no stopwords)
person_re = re.compile(r'^[A-Z\.\-]+(?: [A-Z\.\-]+){0,2}$')
stopwords = set(['THE','IT','IS','ORDERED','COUNTY','EXECUTIVE','FISCAL','OFFICER','FOR','ALLOWED','BE','DEFENDANT','THIS','CAUSE','SERVICES','SO','RENDERED','CERTIFY','AMOUNT','AND','TO','HERETOFORE','ASSIGNED','CONSIDERATION','WHICH','IS'])

dollar_re = re.compile(r"\$\s*([0-9,]+(?:\.\d{1,2})?)")
allowed_re = re.compile(r"\b(BE ALLOWED|ALLOWED|CERTIF|PAID|AWARD|ORDERED THAT .* BE ALLOWED|APPROV)\b", re.I)
submitted_re = re.compile(r"\bSUBMITTED\b", re.I)

billed = defaultdict(float)
paid = defaultdict(float)
count_billed = defaultdict(int)
count_paid = defaultdict(int)

with csv_in.open(newline='', encoding='utf-8') as f:
    r = csv.DictReader(f)
    for row in r:
        raw_name = (row.get('name') or '').strip()
        desc = (row.get('description') or '')
        if not raw_name:
            continue
        # normalize name
        name = re.sub(r'\s+', ' ', raw_name).strip()
        # skip unlikely names
        if not person_re.match(name):
            continue
        toks = name.split()
        if any(t in stopwords for t in toks):
            continue
        # extract amount
        amt = None
        m = dollar_re.search(desc)
        if m:
            try:
                amt = float(m.group(1).replace(',',''))
            except:
                amt = None
        else:
            m2 = re.search(r"BE ALLOWED\s+\$?([0-9,]+(?:\.\d{1,2})?)", desc, re.I)
            if m2:
                try:
                    amt = float(m2.group(1).replace(',',''))
                except:
                    amt = None
        if amt is not None:
            billed[name] += amt
            count_billed[name] += 1
            if allowed_re.search(desc):
                paid[name] += amt
                count_paid[name] += 1
        else:
            if submitted_re.search(desc):
                count_billed[name] += 1

# write person-aggregate CSV
out_csv = root / 'other' / 'late_fee_aggregates_persons.csv'
with out_csv.open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['name','billed_total','paid_total','count_billed','count_paid'])
    names = sorted(set(list(billed.keys()) + list(paid.keys()) + list(count_billed.keys()) + list(count_paid.keys())), key=lambda n: (-billed.get(n,0), -paid.get(n,0), n))
    for name in names:
        w.writerow([name, f"{billed.get(name,0):.2f}", f"{paid.get(name,0):.2f}", count_billed.get(name,0), count_paid.get(name,0)])

# print top 20
print('Aggregate written to', out_csv)
print('\nTop 20 persons by billed total:')
for i, (name, amt) in enumerate(sorted(billed.items(), key=lambda x: -x[1])[:20], 1):
    print(f"{i}. {name} — billed ${amt:.2f} (paid ${paid.get(name,0):.2f}, billed_count={count_billed.get(name,0)}, paid_count={count_paid.get(name,0)})")

print('\nTop 20 persons by paid total:')
for i, (name, amt) in enumerate(sorted(paid.items(), key=lambda x: -x[1])[:20], 1):
    print(f"{i}. {name} — paid ${amt:.2f} (billed ${billed.get(name,0):.2f}, billed_count={count_billed.get(name,0)}, paid_count={count_paid.get(name,0)})")

print('\nTotals (persons) — billed: ${:.2f}, paid: ${:.2f}'.format(sum(billed.values()), sum(paid.values())))
