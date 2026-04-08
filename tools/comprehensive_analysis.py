import csv
from pathlib import Path
import re
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1] / "other"
FILES = [ROOT / "2023_cases_comprehensive.csv",
         ROOT / "2024_cases_comprehensive.csv",
         ROOT / "2025_cases_comprehensive.csv"]

OUT_DIR = Path(__file__).resolve().parents[1] / "analysis_output"
OUT_DIR.mkdir(exist_ok=True)

def parse_final_status(events: str, verdict: str) -> str:
    s = (events or "") + " " + (verdict or "")
    s = s.upper()
    if "CASE DISMISSED" in s or "DISM OTHER" in s or "NOLLE" in s or "NOL PROS" in s:
        return "DISMISSED"
    if "PLD GLTY" in s or "PLEA" in s or "PLEAD" in s or re.search(r"PLD|PLED", s):
        return "PLEA_BARGAIN"
    if "FND GLTY" in s or "GUILTY" in s or "CONVICT" in s:
        return "CONVICTED"
    if "FND N/GLTY" in s or "NOT GUILTY" in s or "ACQUITT" in s:
        return "ACQUITTED"
    return "UNKNOWN"

def categorize_charges(charges: str) -> set:
    s = (charges or "").upper()
    cats = set()
    if not s:
        return cats
    if "MURDER" in s or "HOMICIDE" in s:
        cats.add("MURDER")
    if any(k in s for k in ("FELONIOUS", "FELONY", "AGGRAVATED", "FELON")):
        cats.add("FELONY")
    if any(k in s for k in ("ASSAULT", "ROBBERY", "RAPE", "HOMICIDE", "BATTERY")):
        cats.add("VIOLENT")
    if any(k in s for k in ("DRUG", "NARCOTIC", "TRAFFICK")):
        cats.add("DRUG")
    if any(k in s for k in ("THEFT", "BURGLARY", "ROBBERY", "EMBEZZLE", "FRAUD")):
        cats.add("PROPERTY")
    return cats

def normalize_name(name: str) -> str:
    if not name:
        return "(UNKNOWN)"
    return re.sub(r"\s+", " ", name.strip())

def analyze():
    case_rows = []

    for f in FILES:
        if not f.exists():
            continue
        with f.open(newline='', encoding='utf-8') as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                case_number = row.get('case_number') or row.get('case_number'.upper())
                judge = normalize_name(row.get('judge') or row.get('judge'.upper()))
                prosecutor = normalize_name(row.get('prosecutor') or row.get('prosecutor'.upper()))
                defense = normalize_name(row.get('defense_attorney') or row.get('defense_attorney'.upper()) or row.get('defense_attorney'))
                defendant = normalize_name(row.get('defendant_name') or row.get('defendant_name'.upper()))
                charges = row.get('charges') or row.get('charges'.upper())
                events = row.get('events') or row.get('events'.upper())
                verdict = row.get('verdict') or row.get('verdict'.upper())
                case_status = (row.get('case_status') or row.get('case_status'.upper()) or "").upper()
                def_status = (row.get('def_status') or row.get('def_status'.upper()) or "").upper()

                final_status = parse_final_status(events, verdict)
                categories = categorize_charges(charges)

                case_rows.append({
                    'case_number': case_number,
                    'judge': judge,
                    'prosecutor': prosecutor,
                    'defense': defense,
                    'defendant': defendant,
                    'charges': charges,
                    'categories': ";".join(sorted(categories)) if categories else "",
                    'final_status': final_status,
                    'case_status': case_status,
                    'def_status': def_status,
                    'events': events,
                })

    # Aggregate per participant
    judges = defaultdict(lambda: defaultdict(int))
    prosecutors = defaultdict(lambda: defaultdict(int))
    defenses = defaultdict(lambda: defaultdict(int))
    defendants = defaultdict(lambda: defaultdict(int))

    # Also category buckets
    category_buckets = defaultdict(list)

    lvjail_cc = []

    for r in case_rows:
        status = r['final_status']
        cats = r['categories'].split(';') if r['categories'] else []

        # Judges
        j = r['judge']
        judges[j]['cases'] += 1
        if status == 'DISMISSED':
            judges[j]['dismissals'] += 1
        if status == 'CONVICTED':
            judges[j]['convictions'] += 1
        if status == 'ACQUITTED':
            judges[j]['acquittals'] += 1
        if status == 'PLEA_BARGAIN':
            judges[j]['pleas'] += 1

        # Prosecutors
        p = r['prosecutor']
        prosecutors[p]['cases'] += 1
        if status == 'CONVICTED':
            prosecutors[p]['convictions'] += 1
        if status == 'DISMISSED':
            prosecutors[p]['dismissals'] += 1

        # Defense
        d = r['defense']
        defenses[d]['cases'] += 1
        if status in ('DISMISSED', 'ACQUITTED'):
            defenses[d]['wins'] += 1
        if status == 'CONVICTED':
            defenses[d]['losses'] += 1

        # Defendant
        df = r['defendant']
        defendants[df]['cases'] += 1
        if status == 'DISMISSED':
            defendants[df]['dismissals'] += 1
        if status == 'CONVICTED':
            defendants[df]['convictions'] += 1
        if status == 'ACQUITTED':
            defendants[df]['acquittals'] += 1

        # Categories
        for c in cats:
            if c:
                category_buckets[c].append(r['case_number'])

        # LV JAIL + community control: check def_status or events
        if ('LVJAIL' in (r['def_status'] or '') or 'LV JAIL' in (r['def_status'] or '')):
            if r['events'] and 'COMMUNITY CONTROL' in r['events'].upper():
                lvjail_cc.append(r)

    # Write outputs
    # 1) case_categories.csv
    with (OUT_DIR / 'case_categories.csv').open('w', newline='', encoding='utf-8') as fh:
        writer = csv.writer(fh)
        writer.writerow(['category', 'case_number'])
        for cat, cases in sorted(category_buckets.items()):
            for c in cases:
                writer.writerow([cat, c])

    # 2) participants summary
    def write_participant(path, mapping, fields):
        with path.open('w', newline='', encoding='utf-8') as fh:
            writer = csv.writer(fh)
            writer.writerow(['participant'] + fields)
            for name, data in sorted(mapping.items(), key=lambda x: (-x[1].get('cases',0), x[0])):
                row = [name] + [data.get(f, 0) for f in fields]
                writer.writerow(row)

    write_participant(OUT_DIR / 'judges_summary.csv', judges, ['cases','convictions','dismissals','acquittals','pleas'])
    write_participant(OUT_DIR / 'prosecutors_summary.csv', prosecutors, ['cases','convictions','dismissals'])
    write_participant(OUT_DIR / 'defenses_summary.csv', defenses, ['cases','wins','losses'])
    write_participant(OUT_DIR / 'defendants_summary.csv', defendants, ['cases','convictions','dismissals','acquittals'])

    # 3) LVJAIL + community control
    with (OUT_DIR / 'lvjail_community_control.csv').open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=['case_number','defendant','def_status','events','categories','final_status','judge','prosecutor','defense'])
        writer.writeheader()
        for r in lvjail_cc:
            writer.writerow({
                'case_number': r['case_number'],
                'defendant': r['defendant'],
                'def_status': r['def_status'],
                'events': r['events'],
                'categories': r['categories'],
                'final_status': r['final_status'],
                'judge': r['judge'],
                'prosecutor': r['prosecutor'],
                'defense': r['defense'],
            })

    # Print brief summary
    print('Analysis complete.')
    print(f"Total cases scanned: {len(case_rows)}")
    print(f"Categories found: {', '.join(sorted(category_buckets.keys()))}")
    print(f"LVJail + Community Control cases: {len(lvjail_cc)}")
    print(f"Outputs written to: {OUT_DIR}")

if __name__ == '__main__':
    analyze()
