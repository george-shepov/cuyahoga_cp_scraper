#!/usr/bin/env python3
"""
Fast sequential scraper: 677500 -> 707148
- Uses batch scraping for efficiency
- Validates disk writes
- Logs gaps
- Much faster than calling main.py per case
"""

import subprocess
import json
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

START_CASE = 677500
END_CASE = 707148
OUT_DIR = Path("out")
BATCH_SIZE = 50

def get_year_from_case(case_num):
    """Determine year based on case number"""
    if case_num < 695000:
        return 2023
    elif case_num < 700000:
        return 2024
    else:
        return 2025

def scrape_batch(start_num, batch_size):
    """Scrape a batch of cases"""
    year = get_year_from_case(start_num)
    
    try:
        result = subprocess.run(
            ["python3", "main.py", "scrape", "--year", str(year),
             "--start", str(start_num), "--limit", str(batch_size), "--direction", "up"],
            capture_output=True,
            timeout=300,
            text=True
        )
        
        if result.returncode != 0:
            return None, f"Error: {result.stderr[:100]}"
        
        return True, "Batch completed"
    
    except subprocess.TimeoutExpired:
        return None, "Timeout"
    except Exception as e:
        return None, str(e)

def check_files_in_range(start_num, end_num):
    """Check which files were created in range"""
    found = []
    year = get_year_from_case(start_num)
    year_dir = OUT_DIR / str(year)
    
    if not year_dir.exists():
        return found
    
    for json_file in year_dir.glob("*.json"):
        try:
            # Extract case number from filename
            parts = json_file.name.split('_')[0]
            _, num = parts.split('-')
            case_num = int(num)
            
            if start_num <= case_num <= end_num:
                # Verify it's valid JSON
                data = json.loads(json_file.read_text())
                if data.get('metadata', {}).get('exists'):
                    found.append(case_num)
        except:
            pass
    
    return sorted(found)

def main():
    print(f"\n{'='*80}")
    print(f"FAST SEQUENTIAL BATCH SCRAPE: {START_CASE} → {END_CASE}")
    print(f"{'='*80}\n")
    
    total_to_scrape = END_CASE - START_CASE + 1
    num_batches = (total_to_scrape + BATCH_SIZE - 1) // BATCH_SIZE
    
    print(f"📊 Total cases: {total_to_scrape:,}")
    print(f"📦 Batch size: {BATCH_SIZE}")
    print(f"📦 Total batches: {num_batches}")
    print(f"📁 Output: {OUT_DIR}")
    print(f"⏱️  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    all_found = set()
    gaps = []
    current_gap_start = None
    
    for batch_idx in range(num_batches):
        start = START_CASE + (batch_idx * BATCH_SIZE)
        end = min(start + BATCH_SIZE - 1, END_CASE)
        
        progress = f"[Batch {batch_idx+1:5d}/{num_batches:5d}]"
        
        # Scrape batch
        success, msg = scrape_batch(start, BATCH_SIZE)
        
        if not success:
            print(f"{progress} ⚠️  {msg}")
            # Try again
            success, msg = scrape_batch(start, BATCH_SIZE)
            if not success:
                print(f"{progress} ❌ FAILED RETRY: {msg}")
                continue
        
        # Check what was created
        found_in_batch = check_files_in_range(start, end)
        all_found.update(found_in_batch)
        
        # Detect gaps
        for case_num in range(start, end + 1):
            if case_num not in found_in_batch:
                if current_gap_start is None:
                    current_gap_start = case_num
            else:
                if current_gap_start is not None:
                    gap_size = case_num - current_gap_start
                    gaps.append((current_gap_start, case_num - 1, gap_size))
                    current_gap_start = None
        
        found_count = len(found_in_batch)
        print(f"{progress} ✓ Cases {start:6d}-{end:6d}: {found_count}/{BATCH_SIZE} found")
        
        if batch_idx % 10 == 0 and batch_idx > 0:
            print(f"  📈 Total so far: {len(all_found):,} cases\n")
    
    # Final gap
    if current_gap_start is not None:
        gap_size = END_CASE - current_gap_start + 1
        gaps.append((current_gap_start, END_CASE, gap_size))
    
    # Report
    print(f"\n{'='*80}")
    print(f"SCRAPE COMPLETE")
    print(f"{'='*80}\n")
    
    total_found = len(all_found)
    total_missing = total_to_scrape - total_found
    
    print(f"✅ FOUND: {total_found:,} cases")
    print(f"❌ MISSING: {total_missing:,} cases")
    print(f"📊 Gaps: {len(gaps)}")
    
    if gaps:
        print(f"\n🔍 GAPS DETECTED (showing first 20):")
        for gap_start, gap_end, gap_size in gaps[:20]:
            year_start = get_year_from_case(gap_start)
            year_end = get_year_from_case(gap_end)
            print(f"   {gap_start:7d} - {gap_end:7d} ({gap_size:6,d} cases)")
        if len(gaps) > 20:
            print(f"   ... and {len(gaps)-20} more gaps")
    
    print(f"\n⏱️  Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📂 Files saved to: {OUT_DIR}/")
    
    # Save detailed log
    log_file = Path("SCRAPE_677500_707148_LOG.txt")
    with open(log_file, 'w') as f:
        f.write(f"FAST BATCH SCRAPE LOG\n")
        f.write(f"Range: {START_CASE} → {END_CASE}\n")
        f.write(f"Batch Size: {BATCH_SIZE}\n")
        f.write(f"{'='*80}\n\n")
        
        f.write(f"SUMMARY:\n")
        f.write(f"Found: {total_found:,} cases\n")
        f.write(f"Missing: {total_missing:,} cases\n")
        f.write(f"Coverage: {100*total_found/total_to_scrape:.1f}%\n\n")
        
        f.write(f"GAPS ({len(gaps)} total):\n")
        for gap_start, gap_end, gap_size in gaps:
            f.write(f"{gap_start:7d} - {gap_end:7d}: {gap_size:6d} cases\n")
        
        f.write(f"\n\nFOUND CASES (first 100):\n")
        for i, case_num in enumerate(sorted(all_found)[:100]):
            f.write(f"{case_num:7d}\n")
    
    print(f"📋 Log saved: {log_file}\n")

if __name__ == "__main__":
    main()
