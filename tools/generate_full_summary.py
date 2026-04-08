import csv
from pathlib import Path
import re
import json
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1] / "other"
FILES = [ROOT / "2023_cases_comprehensive.csv",
         ROOT / "2024_cases_comprehensive.csv",
         ROOT / "2025_cases_comprehensive.csv"]

OUT_DIR = Path(__file__).resolve().parents[1] / "analysis_output"
OUT_DIR.mkdir(exist_ok=True)

def parse_final_status(events: str, verdict: str) -> str:
    s = (events or "") + " " + (verdict or "")
    S = s.upper()
    if "CASE DISMISSED" in S or "DISM OTHER" in S or "NOLLE" in S or "NOL PROS" in S:
        return "DISMISSED"
    if "PLD GLTY" in S or "PLEA" in S or "PLEAD" in S or re.search(r"\bPLD\b|PLED", S):
        return "PLEA_BARGAIN"
    if "FND GLTY" in S or "GUILTY" in S or "CONVICT" in S:
        return "CONVICTED"
    if "FND N/GLTY" in S or "NOT GUILTY" in S or "ACQUITT" in S:
        return "ACQUITTED"
    return "UNKNOWN"

def categorize(charges: str):
    s = (charges or "").upper()
    cats = set()
    if not s:
        return cats
    if "MURDER" in s or "HOMICIDE" in s:
        cats.add('MURDER')
    if any(k in s for k in ("FELONIOUS", "FELONY", "AGGRAVATED", "FELON")):
        cats.add('FELONY')
    if any(k in s for k in ("ASSAULT", "ROBBERY", "RAPE", "BATTERY")):
        cats.add('VIOLENT')
    if any(k in s for k in ("DRUG", "NARCOTIC", "TRAFFICK")):
        cats.add('DRUG')
    if any(k in s for k in ("THEFT", "BURGLARY", "EMBEZZLE", "FRAUD")):
        cats.add('PROPERTY')
    return cats

def year_from_case(case_number: str):
    # case format like CR-23-677529-A -> year 2023
    if not case_number:
        return None
    m = re.search(r"CR-(\d{2})-", case_number)
    if m:
        yy = int(m.group(1))
        return 2000 + yy
    return None

def main():
    total = 0
    by_year = defaultdict(int)
    by_final = defaultdict(int)
    by_category = defaultdict(int)
    judges = defaultdict(lambda: defaultdict(int))
    prosecutors = defaultdict(lambda: defaultdict(int))
    defenses = defaultdict(lambda: defaultdict(int))
    lvjail_cc = []

    for f in FILES:
        if not f.exists():
            continue
        with f.open(newline='', encoding='utf-8') as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                total += 1
                case_number = row.get('case_number') or row.get('case_number'.upper())
                charges = row.get('charges') or row.get('charges'.upper())
                events = row.get('events') or row.get('events'.upper())
                verdict = row.get('verdict') or row.get('verdict'.upper())
                judge = (row.get('judge') or row.get('judge'.upper()) or '(UNKNOWN)')
                prosecutor = (row.get('prosecutor') or row.get('prosecutor'.upper()) or '(UNKNOWN)')
                defense = (row.get('defense_attorney') or row.get('defense_attorney'.upper()) or '(UNKNOWN)')
                def_status = (row.get('def_status') or row.get('def_status'.upper()) or '')

                year = year_from_case(case_number) or 'UNKNOWN'
                by_year[year] += 1

                final = parse_final_status(events, verdict)
                by_final[final] += 1

                cats = categorize(charges)
                if not cats:
                    by_category['UNCLASSIFIED'] += 1
                else:
                    for c in cats:
                        by_category[c] += 1

                judges[judge]['cases'] += 1
                judges[judge][final.lower()] += 1

                prosecutors[prosecutor]['cases'] += 1
                prosecutors[prosecutor][final.lower()] += 1

                defenses[defense]['cases'] += 1
                defenses[defense][final.lower()] += 1

                # LVJail + community control check
                if ('LVJAIL' in def_status or 'LV JAIL' in def_status) and events and 'COMMUNITY CONTROL' in events.upper():
                    lvjail_cc.append(case_number)

    summary = {
        'total_cases_scanned': total,
        'by_year': dict(sorted(by_year.items())),
        'by_final_status': dict(by_final),
        'by_category': dict(by_category),
        'top_judges': sorted(((k, v['cases']) for k,v in judges.items()), key=lambda x: -x[1])[:50],
        'top_prosecutors': sorted(((k, v['cases']) for k,v in prosecutors.items()), key=lambda x: -x[1])[:50],
        'top_defenses': sorted(((k, v['cases']) for k,v in defenses.items()), key=lambda x: -x[1])[:50],
        'lvjail_community_control_cases': lvjail_cc,
    }

    out_file = OUT_DIR / 'full_summary.json'
    with out_file.open('w', encoding='utf-8') as fh:
        json.dump(summary, fh, indent=2)

    print('Wrote summary to', out_file)
    print('Total cases scanned:', total)
    print('By final status:', dict(by_final))
    print('By category (sample):', dict(list(by_category.items())[:10]))
    print('LVJail + Community Control cases:', len(lvjail_cc))

if __name__ == '__main__':
    main()
