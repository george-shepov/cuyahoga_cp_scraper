#!/usr/bin/env python3
"""
Import case summaries into SQLite DB `out/cases.db`.
Creates a minimal `cases` table and a `raw_json` table.
"""
import os, json, sqlite3, re
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(__file__))
OUT = os.path.join(ROOT, 'out')
DB_PATH = os.path.join(OUT, 'cases.db')
YEARS = ['2023','2024','2025']

DATE_RE = re.compile(r"(\d{1,2}/\d{1,2}/\d{4})")


def parse_date(s):
    if not s:
        return None
    s = str(s).strip()
    for fmt in ('%m/%d/%Y','%m/%d/%Y %H:%M:%S','%Y-%m-%d','%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    m = DATE_RE.search(s)
    if m:
        try:
            return datetime.strptime(m.group(1), '%m/%d/%Y').date()
        except Exception:
            pass
    return None


def extract_case_info(j, path):
    md = j.get('metadata', {}) or {}
    summary = j.get('summary', {}) or {}
    fields = summary.get('fields', {}) or {}
    case_id = md.get('case_id') or summary.get('case_id') or path.split('/')[-1].split('_')[0]
    year = md.get('year') or (md.get('case_number_formatted') or '')[:4]
    try:
        year = int(year)
    except Exception:
        year = None
    status = fields.get('Status:') or summary.get('status') or ''
    # find earliest capias date and earliest arrest date
    capias_dates = set()
    arrest_dates = set()
    # case_actions
    for ca in (summary.get('case_actions') or []) + (j.get('case_actions') or []):
        try:
            ev = ca.get('event','') if isinstance(ca, dict) else str(ca)
            d = ca.get('date') if isinstance(ca, dict) else None
        except Exception:
            ev = str(ca); d = None
        if ev and 'CAPIAS' in ev.upper():
            pd = parse_date(d)
            if pd: capias_dates.add(pd)
        if ev and 'ARREST' in ev.upper():
            pd = parse_date(d)
            if pd: arrest_dates.add(pd)
    # fields with embedded tables or date-keyed entries
    for k,v in fields.items():
        if isinstance(v, str) and 'EVENT DATE' in v.upper() and 'EVENT DESCRIPTION' in v.upper():
            lines = v.strip().splitlines()
            for row in lines[1:]:
                cols = row.split(',')
                if len(cols) < 2: continue
                dstr = cols[0].strip().strip('"')
                desc = cols[1].strip().strip('"')
                pd = parse_date(dstr)
                if not pd: continue
                if 'CAPIAS' in desc.upper(): capias_dates.add(pd)
                if 'ARREST' in desc.upper(): arrest_dates.add(pd)
        if isinstance(k, str) and '/' in k and isinstance(v, str):
            pd = parse_date(k)
            if pd:
                if 'CAPIAS' in v.upper(): capias_dates.add(pd)
                if 'ARREST' in v.upper(): arrest_dates.add(pd)
    # docket
    for de in j.get('docket') or []:
        desc = (de.get('docket_description') or '')
        pdate = de.get('proceeding_date') or de.get('filing_date')
        if not desc: continue
        if 'CAPIAS' in desc.upper():
            pd = parse_date(pdate)
            if pd:
                capias_dates.add(pd)
            else:
                m = DATE_RE.search(desc)
                if m:
                    d = parse_date(m.group(1))
                    if d: capias_dates.add(d)
        if 'ARREST' in desc.upper():
            pd = parse_date(pdate)
            if pd: arrest_dates.add(pd)
            else:
                m = DATE_RE.search(desc)
                if m:
                    d = parse_date(m.group(1))
                    if d: arrest_dates.add(d)
    # explicit Arrested Date:
    ad = fields.get('Arrested Date:')
    if isinstance(ad, str) and ad.strip().upper() not in ('N/A',''):
        pd = parse_date(ad)
        if pd: arrest_dates.add(pd)
    earliest_capias = min(capias_dates).isoformat() if capias_dates else None
    earliest_arrest = min(arrest_dates).isoformat() if arrest_dates else None
    return {
        'case_id': case_id,
        'year': year,
        'status': status,
        'earliest_capias_date': earliest_capias,
        'arrested_date': earliest_arrest,
        'metadata_json': json.dumps(md),
        'example_json_path': path
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # create tables
    cur.executescript(open(os.path.join(OUT,'sql','schema_sqlite.sql')).read())
    conn.commit()
    counts = 0
    # walk years
    for y in YEARS:
        folder = os.path.join(OUT, y)
        if not os.path.isdir(folder):
            continue
        for fn in os.listdir(folder):
            if not fn.endswith('.json'): continue
            path = os.path.join(folder, fn)
            try:
                j = json.load(open(path,'r',encoding='utf-8'))
            except Exception:
                continue
            info = extract_case_info(j, path)
            # upsert into cases
            cur.execute('''INSERT OR REPLACE INTO cases(case_id, year, status, arrested_date, earliest_capias_date, metadata_json, example_json_path)
                           VALUES (?, ?, ?, ?, ?, ?, ?)''', (
                info['case_id'], info['year'], info['status'], info['arrested_date'], info['earliest_capias_date'], info['metadata_json'], info['example_json_path']
            ))
            # raw_json
            scraped_at = j.get('metadata',{}).get('scraped_at')
            cur.execute('INSERT OR REPLACE INTO raw_json(path, case_id, scraped_at) VALUES (?, ?, ?)', (path, info['case_id'], scraped_at))
            counts += 1
            if counts % 500 == 0:
                conn.commit()
    conn.commit()
    # simple verification
    cur.execute('SELECT COUNT(*) FROM cases')
    total_cases = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM raw_json')
    total_raw = cur.fetchone()[0]
    print('Imported', counts, 'JSON files; cases rows:', total_cases, 'raw_json rows:', total_raw)
    conn.close()

if __name__ == '__main__':
    main()
