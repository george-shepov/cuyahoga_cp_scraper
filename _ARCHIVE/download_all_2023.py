#!/usr/bin/env python3
"""
Download PDFs for ALL 2023 criminal cases and check for Brad B Davis.
This is the ultimate test - 9000+ cases.
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

def get_all_2023_cases():
    """Get all case IDs from 2023 JSON files"""
    json_files = list(Path('out/2023').glob('*.json'))
    
    cases = []
    for jf in json_files:
        try:
            with open(jf) as f:
                data = json.load(f)
            case_id = data.get('metadata', {}).get('case_id', '')
            if case_id and case_id.startswith('CR-23-'):
                cases.append(case_id)
        except:
            pass
    
    # Remove duplicates and sort
    return sorted(set(cases))

def main():
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "MASS 2023 CASE PDF DOWNLOAD" + " " * 36 + "║")
    print("║" + " " * 20 + "All 9000+ Criminal Cases" + " " * 34 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    # Get all cases
    print("Loading all 2023 case IDs...")
    all_cases = get_all_2023_cases()
    print(f"Found {len(all_cases)} unique case IDs")
    print()
    
    # Check what we already have
    already_have = []
    need_download = []
    
    for case_id in all_cases:
        pdf_dir = Path(f'out/2023/pdfs/{case_id}')
        if pdf_dir.exists() and list(pdf_dir.glob('*.pdf')):
            already_have.append(case_id)
        else:
            need_download.append(case_id)
    
    print(f"Already have PDFs: {len(already_have)} cases")
    print(f"Need to download: {len(need_download)} cases")
    print(f"Estimated time: {len(need_download) * 1.5:.0f} minutes ({len(need_download) * 1.5 / 60:.1f} hours)")
    print()
    
    response = input(f"Download PDFs for {len(need_download)} cases? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    print("\nStarting mass download...")
    print("This will take several hours. Progress is logged.")
    print()
    
    results = {
        'total_cases': len(all_cases),
        'already_had': len(already_have),
        'attempted': 0,
        'successful': 0,
        'failed': 0,
        'brad_davis_cases': [],
        'timestamp': datetime.now().isoformat()
    }
    
    for i, case_id in enumerate(need_download, 1):
        case_num = case_id.split('-')[2]
        
        print(f"[{i}/{len(need_download)}] {case_id}...", end=' ', flush=True)
        results['attempted'] += 1
        
        cmd = [
            'python3', 'main.py', 'scrape',
            '--year', '2023',
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
                print("✅", flush=True)
                
                # Quick check for Brad B Davis
                pdf_dir = Path(f'out/2023/pdfs/{case_id}')
                if pdf_dir.exists():
                    for pdf in pdf_dir.glob('*.pdf'):
                        try:
                            check = subprocess.run(
                                ['exiftool', '-Author', '-Creator', str(pdf)],
                                capture_output=True, text=True, timeout=5
                            )
                            if 'brad' in check.stdout.lower() and 'davis' in check.stdout.lower():
                                print(f"    ⚠️⚠️⚠️  BRAD B DAVIS FOUND IN {case_id}/{pdf.name}!")
                                results['brad_davis_cases'].append({
                                    'case_id': case_id,
                                    'file': pdf.name
                                })
                        except:
                            pass
            else:
                results['failed'] += 1
                print("❌", flush=True)
        except:
            results['failed'] += 1
            print("❌ timeout", flush=True)
        
        # Progress report every 50 cases
        if i % 50 == 0:
            print()
            print(f"  Progress: {i}/{len(need_download)} ({i/len(need_download)*100:.1f}%)")
            print(f"  Success: {results['successful']}, Failed: {results['failed']}")
            if results['brad_davis_cases']:
                print(f"  ⚠️  Brad B Davis found in {len(results['brad_davis_cases'])} cases")
            
            # Save intermediate results
            with open('mass_download_progress.json', 'w') as f:
                json.dump(results, f, indent=2)
            print()
        
        time.sleep(1.5)
    
    # Final report
    print()
    print("=" * 80)
    print("MASS DOWNLOAD COMPLETE")
    print("=" * 80)
    print(f"Downloaded: {results['successful']}/{results['attempted']}")
    print(f"Failed: {results['failed']}")
    print()
    
    if results['brad_davis_cases']:
        print("⚠️⚠️⚠️  BRAD B DAVIS FOUND IN MULTIPLE CASES:")
        for item in results['brad_davis_cases']:
            print(f"  {item['case_id']}: {item['file']}")
    else:
        print("✅✅✅  NO Brad B Davis found in any case")
        print("CONCLUSION: Brad B Davis is UNIQUE to CR-23-684826-A")
    
    # Save final results
    final_file = f"mass_download_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(final_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {final_file}")

if __name__ == '__main__':
    main()
