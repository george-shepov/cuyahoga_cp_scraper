#!/usr/bin/env python3
"""Find cases that had evaluation-related docket entries and whose charges
increased between earliest and latest JSON snapshots.

Outputs a CSV `analysis_output/eval_charge_expansion_candidates.csv` with the
top candidates sorted by increase in charge count.
"""
import csv
import json
import re
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out'
AO = ROOT / 'analysis_output'
AO.mkdir(exist_ok=True)

EVAL_KEYWORDS = re.compile(r'eval|evaluation|competenc|psych|psychiat', re.I)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def case_key_from_json(data, path: Path):
    # prefer canonical case number in JSON
    if not data:
        return path.stem.split('_')[0]
    s = data.get('summary') or {}
    cn = s.get('case_number') or data.get('case_number')
    if cn:
        return cn
    # fallback: filename prefix like 2023-684826
    return path.stem.split('_')[0]


def extract_charges_count(data):
    if not data:
        return 0
    # charges may be list under 'charges' or embedded in 'charges' string
    charges = data.get('charges')
    if isinstance(charges, list):
        return len(charges)
    if isinstance(charges, str):
        # rough: count occurrences of statute-like patterns or commas
        parts = charges.split('},')
        return max(1, len(parts))
    # some JSONs store 'docket' array with charge additions — ignore
    return 0


def docket_has_evaluation(data):
    if not data:
        return False
    docket = data.get('docket') or data.get('events') or data.get('events_raw')
    # docket may be list of dicts or a string
    if isinstance(docket, list):
        for e in docket:
            text = ''
            if isinstance(e, dict):
                # try common fields
                for k in ('description','text','event','details'):
                    if k in e and isinstance(e[k], str):
                        text += ' ' + e[k]
            elif isinstance(e, str):
                text += ' ' + e
            if EVAL_KEYWORDS.search(text):
                return True
    elif isinstance(docket, str):
        return bool(EVAL_KEYWORDS.search(docket))
    # try scanning 'events' field if string
    events = data.get('events')
    if isinstance(events, str) and EVAL_KEYWORDS.search(events):
        return True
    return False


def main():
    json_files = sorted(list((OUT / '2023').glob('*.json')) + list((OUT / '2024').glob('*.json')) + list((OUT / '2025').glob('*.json')))
    by_case = {}
    for jf in json_files:
        data = load_json(jf)
        key = case_key_from_json(data, jf)
        by_case.setdefault(key, []).append((jf, data))

    candidates = []
    for case, snaps in by_case.items():
        # sort snapshots by filename (timestamp embedded) to get earliest/latest
        snaps_sorted = sorted(snaps, key=lambda x: x[0].name)
        earliest_path, earliest_data = snaps_sorted[0]
        latest_path, latest_data = snaps_sorted[-1]

        earliest_charges = extract_charges_count(earliest_data)
        latest_charges = extract_charges_count(latest_data)
        increase = latest_charges - earliest_charges

        # evaluation anywhere in snapshots
        eval_found = any(docket_has_evaluation(d) for (_, d) in snaps)

        # heuristics: evaluation found and charges increased by >=2 OR latest >=7
        if eval_found and (increase >= 2 or latest_charges >= 7):
            candidates.append({
                'case': case,
                'earliest_charges': earliest_charges,
                'latest_charges': latest_charges,
                'increase': increase,
                'snapshots': len(snaps),
                'earliest_path': str(earliest_path),
                'latest_path': str(latest_path),
            })

    candidates_sorted = sorted(candidates, key=lambda x: (-x['increase'], -x['latest_charges'], -x['snapshots']))

    out_csv = AO / 'eval_charge_expansion_candidates.csv'
    with out_csv.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['case','earliest_charges','latest_charges','increase','snapshots','earliest_path','latest_path'])
        for row in candidates_sorted[:200]:
            w.writerow([row['case'], row['earliest_charges'], row['latest_charges'], row['increase'], row['snapshots'], row['earliest_path'], row['latest_path']])

    # print top 20
    print('Wrote:', out_csv)
    print('\nTop 20 candidates:')
    for r in candidates_sorted[:20]:
        print(f"{r['case']}: {r['earliest_charges']} -> {r['latest_charges']} (+{r['increase']}) snaps={r['snapshots']}")


if __name__ == '__main__':
    main()
