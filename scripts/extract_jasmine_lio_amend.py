#!/usr/bin/env python3
import csv
import json
import os

INPUT_CSV = 'out/jasmine_jackson_cases_2023_2025.csv'
OUTPUT_CSV = 'out/jasmine_jackson_lio_amend_cases.csv'

def find_charges_with_token(data, token='LIO-AMEND'):
    token_up = token.upper()
    matches = []
    # Try structured: summary -> charges
    summary = data.get('summary') if isinstance(data, dict) else None
    if isinstance(summary, dict):
        charges = summary.get('charges') or summary.get('charge')
        if isinstance(charges, list):
            for c in charges:
                # c may be dict or string
                if isinstance(c, dict):
                    disp = (c.get('disposition') or '')
                    combined = json.dumps(c).upper()
                    if token_up in disp.upper() or token_up in combined:
                        matches.append({
                            'statute': c.get('statute') or c.get('code') or '',
                            'charge': c.get('charge') or c.get('name') or '',
                            'disposition': disp,
                        })
                else:
                    if token_up in str(c).upper():
                        matches.append({'statute':'','charge':str(c),'disposition':''})
    # Fallback: search whole JSON text for token and attempt to extract nearby lines
    text = json.dumps(data)
    if token_up in text.upper():
        # If we already found structured matches, still return them; otherwise create an entry per occurrence
        if matches:
            return matches
        # naive split lines by common separators to find occurrences
        for part in text.split('\n'):
            if token_up in part.upper():
                matches.append({'statute':'','charge':part.strip(),'disposition':part.strip()})
        # last resort: single match entry containing full text excerpt
        if not matches:
            matches.append({'statute':'','charge':text[:200], 'disposition':token_up})
    return matches


def prosecutor_present_in_json(data, prosecutor_name='JASMINE JACKSON'):
    p = prosecutor_name.upper()
    # Check attorneys array
    if isinstance(data, dict):
        attorneys = data.get('attorneys') or data.get('attorney')
        if isinstance(attorneys, list):
            for a in attorneys:
                if isinstance(a, dict):
                    for v in a.values():
                        try:
                            if p in str(v).upper():
                                return True
                        except Exception:
                            pass
                else:
                    if p in str(a).upper():
                        return True
        # Check summary fields and description
        for key in ('summary','description','docket_description','Case Caption'):
            val = data.get(key)
            if isinstance(val, str) and p in val.upper():
                return True
    # Fallback: search entire JSON text
    try:
        if p in json.dumps(data).upper():
            return True
    except Exception:
        pass
    return False


def main():
    rows_found = 0
    total_cases = 0
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    with open(INPUT_CSV, newline='', encoding='utf-8') as inf, open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as outf:
        reader = csv.reader(inf)
        writer = csv.writer(outf)
        writer.writerow(['case_id','year','file_path','statute','charge_description','disposition','prosecutor_present'])
        header = next(reader, None)
        for row in reader:
            if not row:
                continue
            # defensive parsing: first three columns are case_id, year, file_path
            case_id = row[0]
            year = row[1] if len(row) > 1 else ''
            file_path = row[2] if len(row) > 2 else ''
            total_cases += 1
            # normalize path relative to repo root if needed
            if file_path and not os.path.exists(file_path):
                # try to resolve relative to repo root
                alt = os.path.join(os.getcwd(), file_path)
                if os.path.exists(alt):
                    file_path = alt
            if not file_path or not os.path.exists(file_path):
                continue
            try:
                with open(file_path, 'r', encoding='utf-8') as jf:
                    data = json.load(jf)
            except Exception:
                # try reading as text and simple search
                try:
                    with open(file_path, 'r', encoding='utf-8') as jf:
                        text = jf.read()
                    if 'LIO-AMEND' in text.upper():
                        proc = 'JASMINE JACKSON' in text.upper()
                        writer.writerow([case_id, year, file_path, '', text[:200].replace('\n',' '), 'LIO-AMEND', proc])
                        rows_found += 1
                except Exception:
                    continue
                continue
            matches = find_charges_with_token(data, token='LIO-AMEND')
            if matches:
                proc_present = prosecutor_present_in_json(data, 'JASMINE JACKSON')
                for m in matches:
                    writer.writerow([case_id, year, file_path, m.get('statute',''), m.get('charge',''), m.get('disposition',''), proc_present])
                    rows_found += 1
    print(f'DONE. Scanned {total_cases} cases; found {rows_found} charge-level matches. Output: {OUTPUT_CSV}')

if __name__ == '__main__':
    main()
