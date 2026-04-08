#!/usr/bin/env python3
from pathlib import Path
import re

OUT = Path('out')
OUTFILE = Path('/tmp/on_probation_cases.txt')

def main():
    cr_re = re.compile(r'CR-[0-9]{2}-[0-9]{6}-[A-Z]')
    found = set()
    for year in ('2023','2024','2025'):
        d = OUT / year
        if not d.exists():
            continue
        for f in d.rglob('*.json'):
            try:
                with f.open('r', errors='ignore') as fh:
                    txt = fh.read()
            except Exception:
                continue
            if 'ON PROBATION' in txt.upper():
                m = cr_re.search(txt)
                if not m:
                    m = cr_re.search(str(f))
                if m:
                    found.add(m.group(0))

    OUTFILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTFILE.open('w') as out:
        for c in sorted(found):
            out.write(c + '\n')

    print(f'WROTE {OUTFILE} ({len(found)} cases)')


if __name__ == '__main__':
    main()
