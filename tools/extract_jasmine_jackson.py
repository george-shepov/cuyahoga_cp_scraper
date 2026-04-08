import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "other"
FILES = [ROOT / "2023_cases_comprehensive.csv",
         ROOT / "2024_cases_comprehensive.csv",
         ROOT / "2025_cases_comprehensive.csv"]

OUT = Path(__file__).resolve().parents[1] / "analysis_output" / "jasmine_jackson_cases.csv"
OUT.parent.mkdir(exist_ok=True)

def match_prosecutor(p: str) -> bool:
    if not p:
        return False
    return p.strip().upper() == 'JASMINE JACKSON'

def extract():
    rows = []
    for f in FILES:
        if not f.exists():
            continue
        with f.open(newline='', encoding='utf-8') as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                proc = row.get('prosecutor') or row.get('prosecutor'.upper())
                if match_prosecutor(proc):
                    charges = row.get('charges') or row.get('charges'.upper())
                    events = row.get('events') or row.get('events'.upper())
                    verdict = row.get('verdict') or row.get('verdict'.upper())

                    # parse final status
                    s = (events or "") + " " + (verdict or "")
                    S = s.upper()
                    if "CASE DISMISSED" in S or "DISM OTHER" in S or "NOLLE" in S or "NOL PROS" in S:
                        final_status = "DISMISSED"
                    elif "PLD GLTY" in S or "PLEA" in S or "PLEAD" in S or 'PLD' in S:
                        final_status = "PLEA_BARGAIN"
                    elif "FND GLTY" in S or "GUILTY" in S or "CONVICT" in S:
                        final_status = "CONVICTED"
                    elif "FND N/GLTY" in S or "NOT GUILTY" in S or "ACQUITT" in S:
                        final_status = "ACQUITTED"
                    else:
                        final_status = "UNKNOWN"

                    # categories
                    C = (charges or "").upper()
                    cats = []
                    if "MURDER" in C or "HOMICIDE" in C:
                        cats.append('MURDER')
                    if any(k in C for k in ("FELONIOUS", "FELONY", "AGGRAVATED", "FELON")):
                        cats.append('FELONY')
                    if any(k in C for k in ("ASSAULT", "ROBBERY", "RAPE", "BATTERY")):
                        cats.append('VIOLENT')
                    if any(k in C for k in ("DRUG", "NARCOTIC", "TRAFFICK")):
                        cats.append('DRUG')
                    if any(k in C for k in ("THEFT", "BURGLARY", "EMBEZZLE", "FRAUD")):
                        cats.append('PROPERTY')

                    rows.append({
                        'case_number': row.get('case_number') or row.get('case_number'.upper()),
                        'case_status': row.get('case_status') or row.get('case_status'.upper()),
                        'def_status': row.get('def_status') or row.get('def_status'.upper()),
                        'judge': row.get('judge') or row.get('judge'.upper()),
                        'defense_attorney': row.get('defense_attorney') or row.get('defense_attorney'.upper()),
                        'defendant_name': row.get('defendant_name') or row.get('defendant_name'.upper()),
                        'charges': charges,
                        'events': events,
                        'verdict': verdict,
                        'final_status': final_status,
                        'categories': ";".join(sorted(set(cats)))
                    })

    # write out
    if rows:
        with OUT.open('w', newline='', encoding='utf-8') as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            for r in rows:
                writer.writerow(r)

    print(f"Found {len(rows)} rows for prosecutor JASMINE JACKSON")
    print(f"Wrote to: {OUT}")

if __name__ == '__main__':
    extract()
