#!/usr/bin/env python3
"""
Download sentencing entries (JE PDFs) for ALL Judge Saffold cases.
Then analyze them for Brad B Davis metadata pattern.
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def load_saffold_cases():
    """Load all Judge Saffold cases"""
    scan_file = Path('brad_davis_scan_20251116_015721.json')
    
    with open(scan_file) as f:
        data = json.load(f)
    
    # Filter for Jeffrey P Saffold only
    saffold_cases = [
        case for case in data.get('saffold_cases', [])
        if 'JEFFREY P SAFFOLD' in case['judge'].upper()
    ]
    
    return saffold_cases

def scrape_case_with_pdfs(case_id, year='2023'):
    """Scrape case and download PDFs in one command"""
    case_num = case_id.split('-')[2]
    
    cmd = [
        'python3', 'main.py', 'scrape',
        '--year', year,
        '--start', case_num,
        '--limit', '1',
        '--direction', 'up',
        '--download-pdfs',
        '--delay-ms', '3000'
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes
        )
        return result.returncode == 0
    except:
        return False

def analyze_case_pdfs(case_id):
    """Quick analysis - just check for Brad B Davis in PDF metadata"""
    pdf_dir = Path(f'out/2023/pdfs/{case_id}')
    
    if not pdf_dir.exists():
        return {'pdf_count': 0, 'brad_davis': False}
    
    pdfs = list(pdf_dir.glob('*.pdf'))
    brad_davis_files = []
    
    for pdf in pdfs:
        try:
            cmd = ['exiftool', '-Author', '-Creator', '-Title', str(pdf)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if 'brad' in result.stdout.lower() and 'davis' in result.stdout.lower():
                brad_davis_files.append({
                    'file': pdf.name,
                    'metadata': result.stdout
                })
        except:
            pass
    
    return {
        'pdf_count': len(pdfs),
        'brad_davis': len(brad_davis_files) > 0,
        'brad_davis_files': brad_davis_files
    }

def main():
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "MASS SAFFOLD CASE PDF DOWNLOAD" + " " * 33 + "║")
    print("║" + " " * 20 + "Brad B Davis Detection" + " " * 37 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    # Load cases
    cases = load_saffold_cases()
    print(f"Found {len(cases)} Jeffrey P Saffold cases")
    print()
    
    # Check what's already downloaded
    already_have = []
    need_download = []
    
    for case in cases:
        case_id = case['case_id']
        pdf_dir = Path(f'out/2023/pdfs/{case_id}')
        if pdf_dir.exists() and list(pdf_dir.glob('*.pdf')):
            already_have.append(case_id)
        else:
            need_download.append(case)
    
    print(f"Already have PDFs: {len(already_have)} cases")
    print(f"Need to download: {len(need_download)} cases")
    print()
    
    if need_download:
        print(f"Estimated time: {len(need_download) * 1.5:.0f} minutes ({len(need_download) * 1.5 / 60:.1f} hours)")
        print()
        print("Starting downloads...")
        print()
        
        results = {
            'total_cases': len(cases),
            'already_had': len(already_have),
            'attempted': 0,
            'successful': 0,
            'failed': 0,
            'brad_davis_cases': [],
            'timestamp': datetime.now().isoformat()
        }
        
        for i, case in enumerate(need_download, 1):
            case_id = case['case_id']
            
            print(f"[{i}/{len(need_download)}] {case_id}...", end=' ', flush=True)
            results['attempted'] += 1
            
            if scrape_case_with_pdfs(case_id):
                results['successful'] += 1
                print("✅", flush=True)
                
                # Quick check for Brad B Davis
                analysis = analyze_case_pdfs(case_id)
                if analysis['brad_davis']:
                    print(f"    ⚠️  BRAD B DAVIS FOUND!")
                    results['brad_davis_cases'].append({
                        'case_id': case_id,
                        'files': analysis['brad_davis_files']
                    })
            else:
                results['failed'] += 1
                print("❌", flush=True)
            
            # Rate limiting
            if i % 10 == 0:
                print(f"    Progress: {i}/{len(need_download)} ({i/len(need_download)*100:.1f}%)")
                print(f"    Successful: {results['successful']}, Failed: {results['failed']}")
                if results['brad_davis_cases']:
                    print(f"    ⚠️  Brad B Davis found in {len(results['brad_davis_cases'])} cases so far")
                print()
            
            time.sleep(2)
        
        # Save results
        output_file = f"saffold_mass_download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print()
        print("=" * 80)
        print("DOWNLOAD COMPLETE")
        print("=" * 80)
        print(f"Total cases: {results['total_cases']}")
        print(f"Already had: {results['already_had']}")
        print(f"Downloaded: {results['successful']}/{results['attempted']}")
        print(f"Failed: {results['failed']}")
        print()
        
        if results['brad_davis_cases']:
            print("⚠️  BRAD B DAVIS FOUND IN:")
            for item in results['brad_davis_cases']:
                print(f"    {item['case_id']}: {len(item['files'])} file(s)")
        else:
            print("✅ NO Brad B Davis found in any case")
            print("   CONFIRMS: Brad B Davis is UNIQUE to CR-23-684826-A")
        
        print()
        print(f"Results saved to: {output_file}")
    
    # Now analyze ALL cases (including already downloaded)
    print()
    print("=" * 80)
    print("ANALYZING ALL SAFFOLD CASE PDFs")
    print("=" * 80)
    
    all_results = {
        'total_cases': len(cases),
        'cases_with_pdfs': 0,
        'total_pdfs': 0,
        'brad_davis_cases': [],
        'timestamp': datetime.now().isoformat()
    }
    
    for case in cases:
        case_id = case['case_id']
        analysis = analyze_case_pdfs(case_id)
        
        if analysis['pdf_count'] > 0:
            all_results['cases_with_pdfs'] += 1
            all_results['total_pdfs'] += analysis['pdf_count']
            
            if analysis['brad_davis']:
                all_results['brad_davis_cases'].append({
                    'case_id': case_id,
                    'pdf_count': analysis['pdf_count'],
                    'brad_davis_files': analysis['brad_davis_files']
                })
    
    print(f"Cases with PDFs: {all_results['cases_with_pdfs']}/{all_results['total_cases']}")
    print(f"Total PDFs analyzed: {all_results['total_pdfs']}")
    print()
    
    if all_results['brad_davis_cases']:
        print("⚠️  BRAD B DAVIS METADATA FOUND:")
        for item in all_results['brad_davis_cases']:
            print(f"\n  Case: {item['case_id']}")
            print(f"  PDFs: {item['pdf_count']}")
            for bd_file in item['brad_davis_files']:
                print(f"    - {bd_file['file']}")
    else:
        print("✅ NO Brad B Davis metadata found")
        print("   Brad B Davis appears ONLY in CR-23-684826-A")
    
    # Save final analysis
    final_file = f"saffold_final_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(final_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\nFinal analysis saved to: {final_file}")

if __name__ == '__main__':
    main()
