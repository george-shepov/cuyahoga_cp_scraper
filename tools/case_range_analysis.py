"""
Analyze actual case counts and month-to-number mapping between two known case numbers.
"""
import json, re
from pathlib import Path
from collections import defaultdict

OUT = Path("/home/shepov/dev/scrapers/criminal/cuyahoga_cp_scraper/out")
LOW, HIGH = 684826, 711396


def parse_date_to_ym(d):
    """Return (YYYY-MM, int_year) from MM/DD/YYYY or YYYY-MM-DD, else (None, None)."""
    if not d:
        return None, None
    m = re.match(r'(\d{2})/(\d{2})/(\d{4})', d)
    if m:
        return f"{m.group(3)}-{m.group(1)}", int(m.group(3))
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', d)
    if m:
        return f"{m.group(1)}-{m.group(2)}", int(m.group(1))
    return None, None


def date_to_sortkey(entry):
    d = entry.get("filing_date") or entry.get("proceeding_date") or ""
    if not d:
        return "9999-99-99"
    m = re.match(r'(\d{2})/(\d{2})/(\d{4})', d)
    if m:
        return f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
    return d


cases_in_range = []  # (num, year, filing_ym_or_None)

for year in [2023, 2024, 2025, 2026]:
    year_dir = OUT / str(year)
    if not year_dir.exists():
        continue
    for f in year_dir.glob(f"{year}-*.json"):
        m = re.match(rf"{year}-(\d{{6}})_", f.name)
        if not m:
            continue
        num = int(m.group(1))
        if not (LOW <= num <= HIGH):
            continue
        try:
            data = json.loads(f.read_text())
            if not data.get("metadata", {}).get("exists", False):
                continue

            # Get filing date from the earliest matching docket entry
            docket = data.get("docket", [])
            entries_sorted = sorted(docket, key=date_to_sortkey)
            filing_ym = None
            for entry in entries_sorted:
                raw = entry.get("filing_date") or entry.get("proceeding_date")
                ym, yr = parse_date_to_ym(raw)
                if ym and yr and abs(yr - year) <= 1:
                    filing_ym = ym
                    break

            # Fallback: case_id encodes the year (CR-23-XXXXXX-A → 2023)
            if not filing_ym:
                case_id = data.get("metadata", {}).get("case_id") or ""
                yr_m = re.match(r'CR-(\d{2})-', case_id)
                if yr_m:
                    y2 = int(yr_m.group(1))
                    full_yr = (1900 + y2) if y2 >= 40 else (2000 + y2)
                    filing_ym = str(full_yr)  # year-only fallback

            cases_in_range.append((num, year, filing_ym))
        except Exception:
            pass

# Sort only by (num, year) — ignore filing_ym for sort order
cases_in_range.sort(key=lambda t: (t[0], t[1]))

total = len(cases_in_range)
span = HIGH - LOW + 1

print(f"{'='*60}")
print(f"  CR-23-684826-A  →  CR-26-711396-A")
print(f"  Sequential number span : {LOW:,} – {HIGH:,}  ({span:,} numbers)")
print(f"  Actual cases found     : {total:,}  ({total/span*100:.1f}% of number space)")
print(f"  Empty / missing slots  : {span - total:,}  ({(span-total)/span*100:.1f}%)")
print(f"{'='*60}\n")

# Group by month
by_month = defaultdict(list)
no_date = []
for num, year, fm in cases_in_range:
    if fm:
        by_month[fm].append(num)
    else:
        no_date.append((num, year))

# Only keep clean YYYY-MM keys (not bare year fallbacks) for the detailed table
clean_months = {k: v for k, v in by_month.items() if re.match(r'\d{4}-\d{2}', k)}
year_only = {k: v for k, v in by_month.items() if re.match(r'^\d{4}$', k)}

print(f"{'Month':<12} {'Cases':>6}  {'First #':>8}  {'Last #':>8}  {'Span':>8}  {'Cases/wk':>9}")
print("-" * 60)
for month in sorted(clean_months):
    nums = sorted(clean_months[month])
    per_week = len(nums) / 4.33
    span_m = nums[-1] - nums[0]
    print(f"{month:<12} {len(nums):>6}  {nums[0]:>8}  {nums[-1]:>8}  {span_m:>8,}  {per_week:>9.0f}")

if year_only:
    print(f"\n--- Cases with year-only date (no month resolved) ---")
    for yr_k in sorted(year_only):
        nums = sorted(year_only[yr_k])
        print(f"  {yr_k}  : {len(nums):,} cases  ({nums[0]:,} – {nums[-1]:,})")

if no_date:
    by_yr = defaultdict(int)
    for _, y in no_date:
        by_yr[y] += 1
    print(f"\n--- No date at all: {len(no_date)} cases — {dict(sorted(by_yr.items()))}")

# Summary: tight boundaries for scrape targeting
print(f"\n{'─'*60}")
print(f"  SCRAPE TARGETS BY MONTH  (number range per month)")
print(f"{'─'*60}")
print(f"{'Month':<12}  {'Start':>8}  {'End':>8}  {'Count':>6}")
for month in sorted(clean_months):
    nums = sorted(clean_months[month])
    print(f"  {month:<10}  {nums[0]:>8,}  {nums[-1]:>8,}  {len(nums):>6,}")
