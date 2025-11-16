#!/usr/bin/env python3
"""
Download ONLY sentencing entries (JE PDFs) for all cases.
This is the most critical document type for Brad B Davis comparison.
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
import re

def get_all_cases_by_year():
    """Get all case IDs from all years"""
    all_cases = {}
    
    for year in [2023, 2024, 2025]:
        year_dir = Path(f'out/{year}')
        if not year_dir.exists():
            continue
            
        json_files = list(year_dir.glob('*.json'))
        cases = []
        
        for jf in json_files:
            try:
                with open(jf) as f:
                    data = json.load(f)
                case_id = data.get('metadata', {}).get('case_id', '')
                if case_id and case_id.startswith(f'CR-{str(year)[2:4]}-'):
                    cases.append(case_id)
            except:
                pass
        
        all_cases[year] = sorted(set(cases))
    
    return all_cases

def download_sentencing_entry_only(case_id, year):
    """Download only the final/latest sentencing entry for a case"""
    case_num = case_id.split('-')[2]
    
    # First scrape to get docket
    cmd = [
        'python3', 'main.py', 'scrape',
        '--year', str(year),
        '--start', case_num,
        '--limit', '1',
        '--direction', 'up',
        '--delay-ms', '2000'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return False, "scrape_failed"
        
        # Load the JSON to find JE PDF
        json_files = list(Path(f'out/{year}').glob(f'{year}-{case_num}_*.json'))
        if not json_files:
            return False, "no_json"
        
        # Get the most recent JSON
        json_file = sorted(json_files)[-1]
        with open(json_file) as f:
            data = json.load(f)
        
        docket = data.get('docket', {})
        entries = docket.get('entries', []) if isinstance(docket, dict) else docket
        
        if not entries:
            return False, "no_docket"
        
        # Find the latest JE (Journal Entry) - these are sentencing entries
        je_entries = []
        for entry in entries:
            desc = entry.get('description', '')
            # Look for JE in description or document type
            if '_JE_' in desc or 'JOURNAL ENTRY' in desc.upper() or 'SENTENCING' in desc.upper():
                je_entries.append(entry)
        
        if not je_entries:
            return False, "no_je"
        
        # Get the latest JE entry (last one chronologically)
        latest_je = je_entries[-1]
        
        # Now we need to download this specific PDF
        # Re-scrape with PDF download enabled
        cmd_pdf = [
            'python3', 'main.py', 'scrape',
            '--year', str(year),
            '--start', case_num,
            '--limit', '1',
            '--direction', 'up',
            '--download-pdfs',
            '--delay-ms', '2000'
        ]
        
        result = subprocess.run(cmd_pdf, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            # Check if we got the JE file
            pdf_dir = Path(f'out/{year}/pdfs/{case_id}')
            if pdf_dir.exists():
                je_pdfs = list(pdf_dir.glob('*_JE_*.pdf'))
                if je_pdfs:
                    return True, f"downloaded_{len(je_pdfs)}_JE"
                else:
                    # We got PDFs but no JE - keep them but note it
                    return True, "downloaded_no_JE"
            return False, "no_pdfs"
        
        return False, "download_failed"
        
    except Exception as e:
        return False, f"error_{str(e)[:50]}"

def main():
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 10 + "SENTENCING ENTRY DOWNLOAD - ALL YEARS" + " " * 31 + "║")
    print("║" + " " * 15 + "Brad B Davis Pattern Detection" + " " * 33 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    # Load all cases
    print("Loading case IDs...")
    cases_by_year = get_all_cases_by_year()
    
    total_cases = sum(len(cases) for cases in cases_by_year.values())
    print(f"\nFound cases:")
    for year, cases in sorted(cases_by_year.items()):
        print(f"  {year}: {len(cases):,} cases")
    print(f"  TOTAL: {total_cases:,} cases")
    print()
    
    # Check what we already have
    already_have = {}
    need_download = {}
    
    for year, cases in cases_by_year.items():
        already = []
        need = []
        
        for case_id in cases:
            pdf_dir = Path(f'out/{year}/pdfs/{case_id}')
            # Check if we have any JE PDF
            if pdf_dir.exists() and list(pdf_dir.glob('*_JE_*.pdf')):
                already.append(case_id)
            else:
                need.append(case_id)
        
        already_have[year] = already
        need_download[year] = need
    
    total_have = sum(len(a) for a in already_have.values())
    total_need = sum(len(n) for n in need_download.values())
    
    print(f"Already have JE PDFs: {total_have:,} cases")
    print(f"Need to download: {total_need:,} cases")
    print()
    
    for year in sorted(cases_by_year.keys()):
        have = len(already_have[year])
        need = len(need_download[year])
        print(f"  {year}: {have:,} have JE, {need:,} need")
    
    print()
    print(f"Estimated time: {total_need * 2:.0f} minutes ({total_need * 2 / 60:.1f} hours)")
    print("(Downloading only sentencing entries - much faster)")
    print()
    
    # Start downloading
    results = {
        'total_cases': total_cases,
        'already_had_je': total_have,
        'attempted': 0,
        'successful': 0,
        'failed': 0,
        'no_je_found': 0,
        'brad_davis_cases': [],
        'by_year': {},
        'timestamp': datetime.now().isoformat()
    }
    
    overall_count = 0
    
    for year in sorted(cases_by_year.keys()):
        year_results = {
            'total': len(cases_by_year[year]),
            'attempted': 0,
            'successful': 0,
            'failed': 0,
            'no_je': 0
        }
        
        print(f"\n{'=' * 80}")
        print(f"YEAR {year}: {len(need_download[year])} cases to download")
        print(f"{'=' * 80}\n")
        
        for i, case_id in enumerate(need_download[year], 1):
            overall_count += 1
            
            print(f"[{overall_count}/{total_need}] {case_id}...", end=' ', flush=True)
            results['attempted'] += 1
            year_results['attempted'] += 1
            
            success, reason = download_sentencing_entry_only(case_id, year)
            
            if success:
                results['successful'] += 1
                year_results['successful'] += 1
                
                if 'no_JE' in reason:
                    print(f"✅ (no JE)", flush=True)
                    results['no_je_found'] += 1
                    year_results['no_je'] += 1
                else:
                    print(f"✅ {reason}", flush=True)
                    
                    # Check for Brad B Davis in JE PDFs
                    pdf_dir = Path(f'out/{year}/pdfs/{case_id}')
                    if pdf_dir.exists():
                        for pdf in pdf_dir.glob('*_JE_*.pdf'):
                            try:
                                check = subprocess.run(
                                    ['exiftool', '-Author', '-Creator', '-Title', str(pdf)],
                                    capture_output=True, text=True, timeout=5
                                )
                                if 'brad' in check.stdout.lower() and 'davis' in check.stdout.lower():
                                    print(f"    ⚠️⚠️⚠️  BRAD B DAVIS: {pdf.name}")
                                    results['brad_davis_cases'].append({
                                        'year': year,
                                        'case_id': case_id,
                                        'file': pdf.name,
                                        'metadata': check.stdout
                                    })
                            except:
                                pass
            else:
                results['failed'] += 1
                year_results['failed'] += 1
                print(f"❌ {reason}", flush=True)
            
            # Progress report every 50 cases
            if overall_count % 50 == 0:
                print()
                print(f"  Progress: {overall_count}/{total_need} ({overall_count/total_need*100:.1f}%)")
                print(f"  Success: {results['successful']}, Failed: {results['failed']}, No JE: {results['no_je_found']}")
                if results['brad_davis_cases']:
                    print(f"  ⚠️  Brad B Davis: {len(results['brad_davis_cases'])} cases")
                
                # Save intermediate results
                with open('je_download_progress.json', 'w') as f:
                    json.dump(results, f, indent=2)
                print()
            
            time.sleep(1.5)
        
        results['by_year'][str(year)] = year_results
        print(f"\nYear {year} complete: {year_results['successful']}/{year_results['attempted']} successful, {year_results['no_je']} no JE")
    
    # Final report
    print()
    print("=" * 80)
    print("SENTENCING ENTRY DOWNLOAD COMPLETE")
    print("=" * 80)
    print(f"Total cases: {total_cases:,}")
    print(f"Already had JE: {total_have:,}")
    print(f"Downloaded: {results['successful']:,}/{results['attempted']:,}")
    print(f"Failed: {results['failed']:,}")
    print(f"No JE found: {results['no_je_found']:,}")
    print()
    
    if results['brad_davis_cases']:
        print("⚠️⚠️⚠️  BRAD B DAVIS FOUND IN SENTENCING ENTRIES:")
        for item in results['brad_davis_cases']:
            print(f"  {item['year']}/{item['case_id']}: {item['file']}")
    else:
        print("✅✅✅  NO Brad B Davis in ANY sentencing entry")
        print("DEFINITIVE: Brad B Davis is UNIQUE to your case CR-23-684826-A")
    
    # Save final results
    final_file = f"je_download_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(final_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {final_file}")

if __name__ == '__main__':
    main()
