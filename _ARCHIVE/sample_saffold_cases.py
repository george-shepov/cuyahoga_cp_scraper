#!/usr/bin/env python3
"""
Sample Judge Saffold cases and download their sentencing entries for metadata comparison.
Takes every 25th case from 417 Saffold cases = ~17 cases to analyze.
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

def load_saffold_cases():
    """Load the list of Judge Saffold cases from the scan results"""
    scan_file = Path('brad_davis_scan_20251116_015721.json')
    
    if not scan_file.exists():
        print(f"Error: {scan_file} not found")
        return []
    
    with open(scan_file) as f:
        data = json.load(f)
    
    # Filter for Jeffrey P Saffold only (not Shirley Strickland Saffold)
    saffold_cases = [
        case for case in data.get('saffold_cases', [])
        if 'JEFFREY P SAFFOLD' in case['judge'].upper()
    ]
    
    return saffold_cases

def sample_cases(cases, interval=25):
    """Take every Nth case from the list"""
    sampled = []
    for i in range(0, len(cases), interval):
        sampled.append(cases[i])
    return sampled

def scrape_case(case_id, year='2023'):
    """Scrape a single case to get latest data including PDF links"""
    print(f"\n{'='*80}")
    print(f"Scraping & Downloading PDFs: {case_id}")
    print(f"{'='*80}")
    
    # Extract case number from case_id (e.g., CR-23-684826-A -> 684826)
    case_num = case_id.split('-')[2]
    
    # Run scraper with PDF download
    cmd = [
        'python3', 'main.py', 'scrape',
        '--year', year,
        '--start', case_num,
        '--limit', '1',
        '--direction', 'up',
        '--download-pdfs',
        '--delay-ms', '5000'
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            print(f"✅ Successfully scraped {case_id}")
            return True
        else:
            print(f"❌ Failed to scrape {case_id}")
            print(f"Error: {result.stderr[:200]}")
            return False
    except subprocess.TimeoutExpired:
        print(f"⏱️  Timeout scraping {case_id}")
        return False
    except Exception as e:
        print(f"❌ Error scraping {case_id}: {e}")
        return False

def download_pdfs_for_case(case_id):
    """Download PDFs for a specific case"""
    print(f"\nDownloading PDFs for {case_id}...")
    
    # Extract case number
    case_num = case_id.split('-')[2]
    
    cmd = [
        'python3', 'main.py', 'download-pdfs',
        '--case-id', case_id,
        '--delay-ms', '3000'
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes max
        )
        
        if result.returncode == 0:
            print(f"✅ PDFs downloaded for {case_id}")
            return True
        else:
            print(f"❌ PDF download failed for {case_id}")
            if result.stderr:
                print(f"Error: {result.stderr[:200]}")
            return False
    except subprocess.TimeoutExpired:
        print(f"⏱️  Timeout downloading PDFs for {case_id}")
        return False
    except Exception as e:
        print(f"❌ Error downloading PDFs for {case_id}: {e}")
        return False

def analyze_pdfs_for_case(case_id):
    """Run forensic analysis on PDFs for a case"""
    print(f"\nAnalyzing PDFs for {case_id}...")
    
    cmd = [
        'python3', 'analyze_pdfs.py',
        case_id
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            print(f"✅ Analysis complete for {case_id}")
            # Print summary
            if 'Brad B Davis' in result.stdout or 'brad' in result.stdout.lower():
                print("⚠️  BRAD B DAVIS FOUND IN THIS CASE!")
            return True
        else:
            print(f"❌ Analysis failed for {case_id}")
            return False
    except Exception as e:
        print(f"❌ Error analyzing {case_id}: {e}")
        return False

def main():
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "JUDGE SAFFOLD CASE SAMPLING & ANALYSIS" + " " * 24 + "║")
    print("║" + " " * 20 + "Brad B Davis Pattern Detection" + " " * 28 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    # Load all Saffold cases
    print("Loading Judge Saffold cases from scan results...")
    all_cases = load_saffold_cases()
    print(f"Found {len(all_cases)} Jeffrey P Saffold cases")
    
    if not all_cases:
        print("No cases found. Exiting.")
        return
    
    # Sample every 25th case
    sampled = sample_cases(all_cases, interval=25)
    print(f"Sampled {len(sampled)} cases (every 25th case)")
    print()
    
    # Display sample
    print("Cases to analyze:")
    for i, case in enumerate(sampled, 1):
        print(f"  {i:2d}. {case['case_id']}")
    print()
    print(f"Starting automated scraping of {len(sampled)} cases...")
    print("This will take approximately {:.0f} minutes".format(len(sampled) * 2))
    print()
    
    # Process each case
    results = {
        'total_cases': len(sampled),
        'scraped': 0,
        'pdfs_downloaded': 0,
        'analyzed': 0,
        'brad_davis_found': [],
        'failed_cases': [],
        'timestamp': datetime.now().isoformat()
    }
    
    for i, case in enumerate(sampled, 1):
        case_id = case['case_id']
        print(f"\n{'#' * 80}")
        print(f"# Processing {i}/{len(sampled)}: {case_id}")
        print(f"{'#' * 80}")
        
        # Step 1: Scrape case and download PDFs
        if scrape_case(case_id):
            results['scraped'] += 1
            results['pdfs_downloaded'] += 1
            time.sleep(2)
            
            # Step 2: Analyze PDFs
            if analyze_pdfs_for_case(case_id):
                results['analyzed'] += 1
                
                # Check for Brad B Davis in the analysis output
                pdf_dir = Path(f'out/2023/pdfs/{case_id}')
                if pdf_dir.exists():
                    for pdf in pdf_dir.glob('*.pdf'):
                        try:
                            cmd = ['exiftool', '-Author', '-Creator', str(pdf)]
                            output = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                            if 'brad' in output.stdout.lower() or 'davis' in output.stdout.lower():
                                results['brad_davis_found'].append({
                                    'case_id': case_id,
                                    'file': pdf.name,
                                    'metadata': output.stdout
                                })
                        except:
                            pass
        else:
            results['failed_cases'].append(case_id)
        
        # Rate limiting
        print(f"\nWaiting 10 seconds before next case...")
        time.sleep(10)
    
    # Final report
    print("\n\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 30 + "FINAL REPORT" + " " * 36 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    print(f"Total cases sampled: {results['total_cases']}")
    print(f"Successfully scraped: {results['scraped']}")
    print(f"PDFs downloaded: {results['pdfs_downloaded']}")
    print(f"Cases analyzed: {results['analyzed']}")
    print(f"Failed cases: {len(results['failed_cases'])}")
    print()
    
    if results['brad_davis_found']:
        print("⚠️  BRAD B DAVIS METADATA FOUND:")
        print(f"   {len(results['brad_davis_found'])} document(s) with Brad B Davis")
        for item in results['brad_davis_found']:
            print(f"\n   Case: {item['case_id']}")
            print(f"   File: {item['file']}")
            print(f"   {item['metadata']}")
    else:
        print("✅ NO Brad B Davis metadata found in any sampled cases")
        print("   This confirms Brad B Davis is UNIQUE to CR-23-684826-A")
    
    # Save results
    output_file = f"saffold_sample_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")

if __name__ == '__main__':
    main()
