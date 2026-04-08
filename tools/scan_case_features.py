#!/usr/bin/env python3
import re
from pathlib import Path

def scan(out_dir='out'):
    p = Path(out_dir)
    kl = set(); fel = set(); neg = set(); prob = set(); comm = set(); comm_done = set()
    for f in p.rglob('*'):
        if not f.is_file():
            continue
        if f.suffix.lower() not in ('.json', '.txt', '.csv'):
            continue
        try:
            t = f.read_text(errors='ignore')
        except Exception:
            continue
        tu = t.upper()
        ids = set(re.findall(r'CR-[0-9]{2}-[0-9]{6}-[A-Z]', t))
        if not ids:
            continue
        if 'KLODNIK' in tu:
            kl.update(ids)
        if 'FELONIOUS ASSAULT' in tu:
            fel.update(ids)
        if 'NEGLIGENT ASSAULT' in tu:
            neg.update(ids)
        if 'PROBATION' in tu:
            prob.update(ids)
        if 'COMMUNITY SERVICE' in tu:
            comm.update(ids)
        if re.search(r'COMMUNITY SERVICE.*(COMPLETE|COMPLETED|COMPLETION)', tu):
            comm_done.update(ids)

    inter = sorted(list(fel & neg))
    print(f"KLODNIK_CASES: {len(kl)}")
    print("SAMPLE_KLODNIK:", ','.join(sorted(kl)[:5]))
    print(f"FELONIOUS_CASES: {len(fel)}")
    print(f"NEGLIGENT_CASES: {len(neg)}")
    print(f"FEL->NEGL_COUNT: {len(inter)}")
    if inter:
        print("SAMPLE_FEL->NEGL:", ','.join(inter[:10]))
    print(f"PROBATION_CASES: {len(prob)}")
    print("SAMPLE_PROBATION:", ','.join(sorted(list(prob))[:5]))
    print(f"COMMUNITY_SERVICE_CASES: {len(comm)}")
    print("SAMPLE_COMMUNITY:", ','.join(sorted(list(comm))[:5]))
    print(f"COMMUNITY_SERVICE_COMPLETED_CASES: {len(comm_done)}")
    print("SAMPLE_COMMUNITY_DONE:", ','.join(sorted(list(comm_done))[:5]))

if __name__ == '__main__':
    scan()
