#!/usr/bin/env python3
"""Robust scanner: writes a concise results file to /tmp/scan_case_features_safe.txt

Scans files under `out/` for occurrences of:
- KLODNIK
- FELONIOUS ASSAULT
- NEGLIGENT ASSAULT
- PROBATION
- COMMUNITY SERVICE
- COMMUNITY SERVICE COMPLETED variants

Outputs counts and small samples to /tmp/scan_case_features_safe.txt
"""
from pathlib import Path
import re

OUT_DIR = Path('out')
RESULT_PATH = Path('/tmp/scan_case_features_safe.txt')

def scan():
    kl=set(); fel=set(); neg=set(); prob=set(); comm=set(); comm_done=set()
    cr_re = re.compile(r'CR-[0-9]{2}-[0-9]{6}-[A-Z]')
    files = list(OUT_DIR.rglob('*'))
    for f in files:
        if not f.is_file():
            continue
        if f.suffix.lower() not in ('.json','.txt','.csv'):
            continue
        try:
            txt = f.read_text(errors='ignore')
        except Exception:
            continue
        up = txt.upper()
        ids = set(cr_re.findall(txt))
        if not ids:
            # try extracting from filename if none in content
            m = cr_re.search(str(f))
            if m:
                ids = {m.group(0)}
        if not ids:
            continue
        if 'KLODNIK' in up:
            kl.update(ids)
        if 'FELONIOUS ASSAULT' in up:
            fel.update(ids)
        if 'NEGLIGENT ASSAULT' in up:
            neg.update(ids)
        if 'PROBATION' in up:
            prob.update(ids)
        if 'COMMUNITY SERVICE' in up:
            comm.update(ids)
        if re.search(r'COMMUNITY SERVICE.*(COMPLETE|COMPLETED|COMPLETION)', up):
            comm_done.update(ids)

    inter = sorted(list(fel & neg))
    with RESULT_PATH.open('w') as out:
        out.write(f'KLODNIK_CASES: {len(kl)}\n')
        out.write('SAMPLE_KLODNIK: ' + ','.join(sorted(kl)[:5]) + '\n')
        out.write(f'FELONIOUS_CASES: {len(fel)}\n')
        out.write(f'NEGLIGENT_CASES: {len(neg)}\n')
        out.write(f'FEL->NEGL_COUNT: {len(inter)}\n')
        if inter:
            out.write('SAMPLE_FEL->NEGL: ' + ','.join(inter[:10]) + '\n')
        out.write(f'PROBATION_CASES: {len(prob)}\n')
        out.write('SAMPLE_PROBATION: ' + ','.join(sorted(list(prob))[:5]) + '\n')
        out.write(f'COMMUNITY_SERVICE_CASES: {len(comm)}\n')
        out.write('SAMPLE_COMMUNITY: ' + ','.join(sorted(list(comm))[:5]) + '\n')
        out.write(f'COMMUNITY_SERVICE_COMPLETED_CASES: {len(comm_done)}\n')
        out.write('SAMPLE_COMMUNITY_DONE: ' + ','.join(sorted(list(comm_done))[:5]) + '\n')

    print('Wrote results to', RESULT_PATH)

if __name__ == '__main__':
    scan()
