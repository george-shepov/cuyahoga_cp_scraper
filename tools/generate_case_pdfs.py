#!/usr/bin/env python3
"""Render stored case JSON into 5 timestamped PDFs (summary, docket, defendant, attorneys, costs).

Usage:
  ./tools/generate_case_pdfs.py --cases CR-23-684826-A CR-25-706402-A
  ./tools/generate_case_pdfs.py --from-file cases.txt

This script uses Playwright to render simple HTML for each of the 5 UI nodes
and saves a PDF with an embedded capture timestamp in the footer.

Note: This renders from the local `out/` JSON snapshots. If you prefer to
navigate the live Cuyahoga site and capture their printer-friendly pages,
we can adapt the script to drive the site (requires knowing URL structure
and obeying robots/terms of service).
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out'
AO = ROOT / 'analysis_output'
PDF_OUT = AO / 'case_pdfs'
PDF_OUT.mkdir(parents=True, exist_ok=True)

NODES = [
    ('summary', 'Case Summary'),
    ('docket', 'Docket'),
    ('defendant', 'Defendant'),
    ('attorneys', 'Attorneys'),
    ('costs', 'Costs'),
]


def find_json_for_case(case_number: str) -> Path | None:
    """Find the latest JSON in out/2023-2025 that matches the case_number.
    Returns Path or None.
    """
    parts = case_number.split('-')
    if len(parts) < 3:
        candidates = list(OUT.rglob(f"*{case_number}*.json"))
    else:
        year = '20' + parts[1] if parts[1].isdigit() and len(parts[1]) == 2 else None
        if year and (OUT / year).exists():
            candidates = sorted((OUT / year).glob(f"{year}-{parts[2]}_*.json"), reverse=True)
        else:
            candidates = list(OUT.rglob(f"*{case_number}*.json"))
    return candidates[0] if candidates else None


def render_node_html(node_name: str, node_label: str, data: Dict) -> str:
    """Create a simple HTML representation for the node data.
    Keep layout minimal so PDFs are readable and include the capture timestamp.
    """
    body = '<h1>%s</h1>' % node_label
    if not data:
        body += '<p><em>no data</em></p>'
    else:
        # If it's a list (like docket entries), render a table
        if isinstance(data, list):
            body += '<table border="1" cellspacing="0" cellpadding="6">'
            # collect keys
            keys = set()
            for item in data:
                if isinstance(item, dict):
                    keys.update(item.keys())
            keys = sorted(keys)
            if keys:
                body += '<thead><tr>' + ''.join(f'<th>{k}</th>' for k in keys) + '</tr></thead>'
                body += '<tbody>'
                for item in data:
                    if isinstance(item, dict):
                        body += '<tr>' + ''.join(f'<td>{(item.get(k) or "")} </td>' for k in keys) + '</tr>'
                body += '</tbody>'
            else:
                for item in data:
                    body += f'<div>{item}</div>'
            body += '</table>'
        elif isinstance(data, dict):
            body += '<dl>'
            for k, v in data.items():
                body += f'<dt><strong>{k}</strong></dt><dd>{json.dumps(v, ensure_ascii=False)}</dd>'
            body += '</dl>'
        else:
            body += f'<pre>{json.dumps(data, indent=2, ensure_ascii=False)}</pre>'

    html = f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width,initial-scale=1" />
        <style>
          body {{ font-family: Helvetica, Arial, sans-serif; margin: 24px; }}
          table {{ border-collapse: collapse; width: 100%; font-size: 12px }}
          th {{ background: #eee; text-align: left }}
          td, th {{ border: 1px solid #ccc; padding: 6px }}
          dt {{ font-weight: bold }}
          dd {{ margin-left: 0  }}
        </style>
      </head>
      <body>
        {body}
      </body>
    </html>
    """
    return html


def capture_pdfs_from_json(json_path: Path, playwright, out_dir: Path):
    data = json.loads(json_path.read_text(encoding='utf-8'))
    # try summary node mapping
    for node_key, node_label in NODES:
        # best-effort extraction
        node_data = None
        if node_key in data:
            node_data = data[node_key]
        elif node_key == 'summary' and 'summary' in data:
            node_data = data['summary']
        elif node_key == 'docket' and 'docket' in data:
            node_data = data['docket']
        elif node_key == 'attorneys' and 'attorneys' in data:
            node_data = data['attorneys']
        elif node_key == 'costs' and 'costs' in data:
            node_data = data['costs']

        html = render_node_html(node_key, node_label, node_data)

        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until='networkidle')

        ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        case_id = (data.get('summary') or {}).get('case_number') or data.get('case_number') or json_path.stem
        safe_case = case_id.replace('/', '_')
        pdf_name = f"{safe_case}--{node_key}--{ts}.pdf"
        pdf_path = out_dir / pdf_name

        # header/footer templates include timestamp for legal traceability
        footer = f'<div style="font-size:10px;width:100%;text-align:center;">Captured: {ts} UTC · source: {json_path.name}</div>'

        page.pdf(path=str(pdf_path), format='A4', print_background=True,
                 display_header_footer=True,
                 header_template='<div></div>',
                 footer_template=f'<div style="font-size:10px;margin:0 auto;text-align:center">{footer}</div>')

        browser.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--cases', nargs='*', help='Case numbers to process')
    p.add_argument('--from-file', help='File with one case_number per line')
    p.add_argument('--out-dir', help='Where to write PDFs', default=str(PDF_OUT))
    args = p.parse_args()

    cases = []
    if args.cases:
        cases.extend(args.cases)
    if args.from_file:
        cases.extend([ln.strip() for ln in Path(args.from_file).read_text(encoding='utf-8').splitlines() if ln.strip()])
    if not cases:
        print('Provide case numbers via --cases or --from-file')
        return

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        for case in cases:
            json_path = find_json_for_case(case)
            if not json_path:
                print('JSON not found for', case)
                continue
            print('Processing', case, '->', json_path)
            try:
                capture_pdfs_from_json(json_path, pw, out_dir)
            except Exception as e:
                print('Error capturing', case, e)


if __name__ == '__main__':
    main()
