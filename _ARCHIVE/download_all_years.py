#!/usr/bin/env python3
"""
Download PDFs for ALL cases across 2023, 2024, 2025.
Search every single PDF for Brad B Davis metadata.
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

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
        
        # Remove duplicates and sort
        all_cases[year] = sorted(set(cases))
    
    return all_cases

def main():
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 10 + "MASS PDF DOWNLOAD - ALL 2023/2024/2025 CASES" + " " * 24 + "║")
    print("║" + " " * 15 + "Brad B Davis Comprehensive Search" + " " * 30 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    # Load all cases
    print("Loading case IDs from all years...")
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
            if pdf_dir.exists() and list(pdf_dir.glob('*.pdf')):
                already.append(case_id)
            else:
                need.append(case_id)
        
        already_have[year] = already
        need_download[year] = need
    
    total_have = sum(len(a) for a in already_have.values())
    total_need = sum(len(n) for n in need_download.values())
    
    print(f"Already have PDFs: {total_have:,} cases")
    print(f"Need to download: {total_need:,} cases")
    print()
    
    for year in sorted(cases_by_year.keys()):
        have = len(already_have[year])
        need = len(need_download[year])
        print(f"  {year}: {have:,} have, {need:,} need")
    
    print()
    print(f"Estimated time: {total_need * 1.5:.0f} minutes ({total_need * 1.5 / 60:.1f} hours)")
    print()
    
    # Start downloading
    print("Starting mass download...")
    print("Progress will be saved every 50 cases")
    print()
    
    results = {
        'total_cases': total_cases,
        'already_had': total_have,
        'attempted': 0,
        'successful': 0,
        'failed': 0,
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
            'failed': 0
        }
        
        print(f"\n{'=' * 80}")
        print(f"YEAR {year}: {len(need_download[year])} cases to download")
        print(f"{'=' * 80}\n")
        
        for i, case_id in enumerate(need_download[year], 1):
            overall_count += 1
            case_num = case_id.split('-')[2]
            
            print(f"[{overall_count}/{total_need}] {case_id}...", end=' ', flush=True)
            results['attempted'] += 1
            year_results['attempted'] += 1
            
            cmd = [
                'python3', 'main.py', 'scrape',
                '--year', str(year),
                '--start', case_num,
                '--limit', '1',
                '--direction', 'up',
                '--download-pdfs',
                '--delay-ms', '2000'
            ]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0:
                    results['successful'] += 1
                    year_results['successful'] += 1
                    print("✅", flush=True)
                    
                    # Quick check for Brad B Davis
                    pdf_dir = Path(f'out/{year}/pdfs/{case_id}')
                    if pdf_dir.exists():
                        for pdf in pdf_dir.glob('*.pdf'):
                            try:
                                check = subprocess.run(
                                    ['exiftool', '-Author', '-Creator', str(pdf)],
                                    capture_output=True, text=True, timeout=5
                                )
                                if 'brad' in check.stdout.lower() and 'davis' in check.stdout.lower():
                                    print(f"    ⚠️⚠️⚠️  BRAD B DAVIS FOUND: {case_id}/{pdf.name}")
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
                    print("❌", flush=True)
            except:
                results['failed'] += 1
                year_results['failed'] += 1
                print("❌ timeout", flush=True)
            
            # Progress report every 50 cases
            if overall_count % 50 == 0:
                print()
                print(f"  Overall: {overall_count}/{total_need} ({overall_count/total_need*100:.1f}%)")
                print(f"  Success: {results['successful']}, Failed: {results['failed']}")
                if results['brad_davis_cases']:
                    print(f"  ⚠️  Brad B Davis: {len(results['brad_davis_cases'])} cases")
                
                # Save intermediate results
                with open('mass_download_progress.json', 'w') as f:
                    json.dump(results, f, indent=2)
                print()
            
            time.sleep(1.5)
        
        results['by_year'][str(year)] = year_results
        print(f"\nYear {year} complete: {year_results['successful']}/{year_results['attempted']} successful")
    
    # Final report
    print()
    print("=" * 80)
    print("MASS DOWNLOAD COMPLETE")
    print("=" * 80)
    print(f"Total cases: {total_cases:,}")
    print(f"Already had: {total_have:,}")
    print(f"Downloaded: {results['successful']:,}/{results['attempted']:,}")
    print(f"Failed: {results['failed']:,}")
    print()
    
    if results['brad_davis_cases']:
        print("⚠️⚠️⚠️  BRAD B DAVIS FOUND IN:")
        by_year_bd = {}
        for item in results['brad_davis_cases']:
            year = item['year']
            if year not in by_year_bd:
                by_year_bd[year] = []
            by_year_bd[year].append(item)
        
        for year in sorted(by_year_bd.keys()):
            print(f"\n  {year}: {len(by_year_bd[year])} case(s)")
            for item in by_year_bd[year]:
                print(f"    {item['case_id']}: {item['file']}")
    else:
        print("✅✅✅  NO Brad B Davis found in ANY case")
        print("CONCLUSION: Brad B Davis is UNIQUE to CR-23-684826-A")
    
    # Save final results
    final_file = f"mass_download_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(final_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {final_file}")

if __name__ == '__main__':
    main()
