#!/usr/bin/env python3
"""
OCR all September 2023 indictment PDFs and extract grand jury term.
Reads existing and newly-downloaded CR PDFs from out/2023/pdfs/
Cross-references with ±60 day window report for case dates.
Outputs: sep_2023_full_term_report.csv
"""
import csv, json, re, subprocess, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent

# Term extraction patterns
# Handles multi-column layout: "The Term Of" on one line, month on the next (often with spaces)
RX_TERM_OF = re.compile(r'\bThe\s+Term\s+Of\s*[\r\n ]+\s*([A-Za-z]+\s+of\s+\d{4})', re.I)
RX_TERM_LABEL = re.compile(r'\bThe\s+Term\s+Of\b[^\n]{0,80}\n\s*([A-Za-z]+\s+of\s+\d{4})', re.I)
# Also handle "The Term Of" and the month appearing within 300 chars (multi-column spacing)
RX_TERM_NEARBY = re.compile(r'\bThe\s+Term\s+Of\b', re.I)
RX_MONTH_TERM = re.compile(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+of\s+\d{4}\b', re.I)
RX_MONTH_TERM2 = re.compile(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+TERM\b', re.I)
RX_GJ_NUM = re.compile(r'(Sep|Sept)\s+\d{4}\s+GJ\s*#\d+', re.I)
RX_TRUE_BILL = re.compile(r'A\s+True\s+Bill', re.I)
RX_BINDOVER = re.compile(r'(BIND\s*OVER|BOUND\s+OVER|BINDOVER)', re.I)

def extract_text_pdftotext(pdf_path: Path) -> str:
    """Extract text using pdftotext (poppler)."""
    try:
        result = subprocess.run(
            ['pdftotext', '-layout', str(pdf_path), '-'],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout
    except Exception as e:
        return ''

def extract_text_python(pdf_path: Path) -> str:
    """Fallback: pdfplumber."""
    try:
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            return '\n'.join(page.extract_text() or '' for page in pdf.pages)
    except Exception:
        return ''

def extract_term(text: str) -> tuple[str, str]:
    """Returns (term_string, indictment_type)."""
    if not text.strip():
        return 'NO_TEXT_EXTRACTED', 'UNKNOWN'

    # Determine type
    ind_type = 'UNKNOWN'
    if RX_TRUE_BILL.search(text):
        ind_type = 'ORIGINAL_INDICTMENT'
    if RX_BINDOVER.search(text):
        ind_type = 'BINDOVER'

    # Try "The Term Of\n<month> of <year>" (direct / compact layout)
    for rx in (RX_TERM_OF, RX_TERM_LABEL):
        m = rx.search(text)
        if m:
            return m.group(1).strip().title(), ind_type

    # Multi-column layout: "The Term Of" label appears on same line as other text,
    # but the month value appears within the next 300 chars
    m_label = RX_TERM_NEARBY.search(text)
    if m_label:
        window = text[m_label.end(): m_label.end() + 300]
        m_month = RX_MONTH_TERM.search(window)
        if m_month:
            return m_month.group(0).strip().title(), ind_type

    # Fallback: any "Month of YYYY" near "True Bill" or "Term"
    for m in RX_MONTH_TERM.finditer(text):
        context = text[max(0, m.start()-200):m.end()+200]
        if re.search(r'(True Bill|Term Of|Grand Jury|Indictment)', context, re.I):
            return m.group(0).strip().title(), ind_type

    # Fallback 2: "Month TERM"
    for m in RX_MONTH_TERM2.finditer(text):
        return m.group(0).strip().title(), ind_type

    # GJ number
    m = RX_GJ_NUM.search(text)
    if m:
        return m.group(0).strip(), ind_type

    return 'TERM_NOT_FOUND_IN_PDF', ind_type


def main():
    # Load September case dates from report
    report_path = ROOT / 'out/2023/case_window_report_684826_pm60.csv'
    case_dates = {}
    with report_path.open() as f:
        for row in csv.DictReader(f):
            cd = row.get('case_date','').strip()
            cn = row.get('case_id','').strip()
            if cd.startswith('09/') and cd.endswith('/2023'):
                case_dates[cn] = cd

    print(f"September 2023 cases in report: {len(case_dates)}")

    results = []
    pdf_base = ROOT / 'out/2023/pdfs'

    for case_id, case_date in sorted(case_dates.items(), key=lambda x: (x[1], x[0])):
        pdf_dir = pdf_base / case_id
        cr_pdfs = sorted(pdf_dir.glob('*_CR_*.pdf')) if pdf_dir.exists() else []

        if not cr_pdfs:
            results.append({
                'case_id': case_id,
                'case_date': case_date,
                'gj_term': 'NO_CR_PDF',
                'indictment_type': 'NO_CR_PDF',
                'pdf_file': '',
                'pdf_text_len': 0,
            })
            continue

        # Use the earliest-dated CR PDF (the indictment filing)
        pdf = cr_pdfs[0]
        text = extract_text_pdftotext(pdf)
        if not text.strip():
            text = extract_text_python(pdf)

        term, ind_type = extract_term(text)

        results.append({
            'case_id': case_id,
            'case_date': case_date,
            'gj_term': term,
            'indictment_type': ind_type,
            'pdf_file': pdf.name,
            'pdf_text_len': len(text),
        })
        print(f"  {case_id}  {case_date}  {term:30s}  {ind_type}  [{pdf.name}]")

    # Write CSV
    out_csv = ROOT / 'sep_2023_full_term_report.csv'
    fields = ['case_id', 'case_date', 'gj_term', 'indictment_type', 'pdf_file', 'pdf_text_len']
    with out_csv.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(results)

    # Summary
    print(f"\n{'='*60}")
    print(f"Total Sep 2023 cases: {len(results)}")
    by_term = defaultdict(list)
    for r in results:
        by_term[r['gj_term']].append(r['case_id'])
    print("\nBy Grand Jury Term:")
    for term in sorted(by_term, key=lambda t: -len(by_term[t])):
        cases = by_term[term]
        print(f"  {term:40s}: {len(cases):3d} cases")
        if len(cases) <= 10:
            for c in sorted(cases):
                day = case_dates.get(c, '?')
                print(f"    {c}  {day}")

    # May term specifically
    may_cases = [r for r in results if 'May' in r['gj_term']]
    print(f"\n{'='*60}")
    print(f"MAY TERM CASES IN SEPTEMBER ({len(may_cases)} total):")
    by_day = defaultdict(list)
    for r in may_cases:
        by_day[r['case_date']].append(r['case_id'])
    for day in sorted(by_day):
        print(f"  {day}: {sorted(by_day[day])}")

    print(f"\nOutput: {out_csv}")


if __name__ == '__main__':
    main()
