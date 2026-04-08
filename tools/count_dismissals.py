"""Count dismissed cases from Cuyahoga County criminal court records."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "other"
files = [ROOT / "2023_cases_comprehensive.csv",
         ROOT / "2024_cases_comprehensive.csv",
         ROOT / "2025_cases_comprehensive.csv"]

def is_dismissed(events: str | None) -> bool:
    return bool(events and "CASE DISMISSED" in events.upper())

def is_murder(charges: str | None) -> bool:
    return bool(charges and "MURDER" in charges.upper())

def is_felony(charges: str | None) -> bool:
    if not charges:
        return False
    s = charges.upper()
    return any(k in s for k in ("FELON", "AGGRAVATED", "FELONY"))

def count():
    total_dismissed = 0
    dismissed_murder = 0
    dismissed_felony = 0

    for f in files:
        if not f.exists():
            continue
        with f.open(newline='', encoding='utf-8') as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                events = row.get('events') or row.get('events'.upper())
                charges = row.get('charges') or row.get('charges'.upper())
                if is_dismissed(events):
                    total_dismissed += 1
                    if is_murder(charges):
                        dismissed_murder += 1
                    if is_felony(charges):
                        dismissed_felony += 1

    return total_dismissed, dismissed_felony, dismissed_murder

if __name__ == '__main__':
    total, felony, murder = count()
    print(f"total_dismissed_cases={total} - count_dismissals.py:46")
    print(f"dismissed_felony_cases={felony} - count_dismissals.py:47")
    print(f"dismissed_murder_cases={murder} - count_dismissals.py:48")
