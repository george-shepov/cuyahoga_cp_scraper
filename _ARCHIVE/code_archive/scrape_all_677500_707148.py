#!/usr/bin/env python3
"""
Sequential comprehensive scraper: 677500 -> 707148
- Check EVERY case number sequentially
- Validate all writes to disk
- Detect and log gaps
- Fix errors before continuing
"""

import subprocess
import json
import sys
from pathlib import Path
from datetime import datetime

START_CASE = 677500
END_CASE = 707148
OUT_DIR = Path("out")

# Tracking
found_cases = []
missing_cases = []
write_errors = []
errors_fixed = []
skipped_cases = {}

def get_year_from_case(case_num):
    """Determine year based on case number"""
    if case_num < 695000:
        return 2023
    elif case_num < 700000:
        return 2024
    else:
        return 2025

def verify_file_written(filepath, expected_case_num):
    """Verify file was actually written and contains valid JSON"""
    if not filepath.exists():
        return False, "File does not exist"
    
    try:
        size = filepath.stat().st_size
        if size < 100:
            return False, f"File too small ({size} bytes)"
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Verify it has case data
        if not data.get('metadata', {}).get('exists'):
            return False, "Case marked as not existing"
        
        case_num = data.get('metadata', {}).get('number')
        if case_num != expected_case_num:
            return False, f"Case number mismatch: expected {expected_case_num}, got {case_num}"
        
        return True, "Valid"
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    except Exception as e:
        return False, f"Error reading file: {e}"

def scrape_case(case_num):
    """Scrape a single case"""
    year = get_year_from_case(case_num)
    year_dir = OUT_DIR / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Run scraper
        result = subprocess.run(
            ["python3", "main.py", "scrape", "--year", str(year),
             "--start", str(case_num), "--limit", "1", "--direction", "up"],
            capture_output=True,
            timeout=120,
            text=True
        )
        
        if result.returncode != 0:
            error_msg = result.stdout or result.stderr
            if "not found" in error_msg.lower() or "404" in error_msg.lower():
                return None, "Case not found"
            return None, f"Error: {error_msg[:100]}"
        
        # Find the file that was just created
        json_files = sorted(year_dir.glob(f"*{case_num:06d}*.json"))
        if not json_files:
            return None, "No file created"
        
        newest_file = json_files[-1]
        
        # Verify it was written correctly
        valid, msg = verify_file_written(newest_file, case_num)
        if not valid:
            # Try to fix by re-scraping
            return None, f"Write verification failed: {msg} - RETRYING"
        
        return newest_file, "Success"
    
    except subprocess.TimeoutExpired:
        return None, "Timeout"
    except Exception as e:
        return None, str(e)

def main():
    print(f"\n{'='*80}")
    print(f"COMPREHENSIVE SEQUENTIAL SCRAPE: {START_CASE} → {END_CASE}")
    print(f"{'='*80}\n")
    
    total_to_scrape = END_CASE - START_CASE + 1
    print(f"📊 Total cases to check: {total_to_scrape:,}")
    print(f"📁 Output directory: {OUT_DIR}")
    print(f"⏱️  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    current_gap_start = None
    gap_size = 0
    
    for idx, case_num in enumerate(range(START_CASE, END_CASE + 1), 1):
        # Progress indicator
        progress = f"[{idx:7d}/{total_to_scrape:7d}] ({100*idx/total_to_scrape:5.1f}%)"
        
        # Attempt scrape with retry logic
        max_retries = 3
        retry_count = 0
        file_path = None
        error_msg = None
        
        while retry_count < max_retries:
            file_path, error_msg = scrape_case(case_num)
            
            if file_path:
                # SUCCESS
                found_cases.append(case_num)
                
                # End gap tracking if we were in a gap
                if current_gap_start is not None:
                    gap_size = case_num - current_gap_start
                    missing_cases.append((current_gap_start, case_num - 1, gap_size))
                    print(f"  ⚠️  GAP DETECTED: {current_gap_start:6d} - {case_num-1:6d} ({gap_size:5d} cases)")
                    current_gap_start = None
                    gap_size = 0
                
                print(f"{progress} ✓ CR-{get_year_from_case(case_num):02d}-{case_num:06d} → {file_path.name}")
                break
            
            else:
                # Check if it's a "not found" (case doesn't exist) vs error
                if "not found" in error_msg.lower():
                    # Case legitimately doesn't exist
                    if current_gap_start is None:
                        current_gap_start = case_num
                    break
                else:
                    # Transient error - retry
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"{progress} ⚡ RETRY #{retry_count}: {error_msg[:50]}")
                        import time
                        time.sleep(2)
                    else:
                        print(f"{progress} ✗ ERROR (retries exhausted): {error_msg[:60]}")
                        errors_fixed.append((case_num, error_msg))
        
        # Show status every 100 cases
        if idx % 100 == 0:
            found_so_far = len(found_cases)
            print(f"\n📈 Status at case {case_num}: {found_so_far} cases found so far\n")
    
    # Report final gap if exists
    if current_gap_start is not None:
        gap_size = END_CASE - current_gap_start + 1
        missing_cases.append((current_gap_start, END_CASE, gap_size))
        print(f"  ⚠️  FINAL GAP: {current_gap_start:6d} - {END_CASE:6d} ({gap_size:5d} cases)")
    
    # Print summary
    print(f"\n{'='*80}")
    print(f"SCRAPE COMPLETE")
    print(f"{'='*80}\n")
    
    print(f"✅ FOUND: {len(found_cases):,} cases")
    print(f"❌ MISSING: {sum(g[2] for g in missing_cases):,} cases (in {len(missing_cases)} gaps)")
    print(f"⚠️  ERRORS DURING RETRY: {len(errors_fixed)}")
    
    print(f"\n📊 GAPS DETECTED:")
    for gap_start, gap_end, gap_size in missing_cases:
        print(f"   CR-{get_year_from_case(gap_start):02d}-{gap_start:06d} to CR-{get_year_from_case(gap_end):02d}-{gap_end:06d}: {gap_size:,} cases")
    
    if errors_fixed:
        print(f"\n⚠️  CASES WITH ERRORS:")
        for case_num, error in errors_fixed[:20]:  # Show first 20
            print(f"   {case_num}: {error[:60]}")
        if len(errors_fixed) > 20:
            print(f"   ... and {len(errors_fixed) - 20} more")
    
    print(f"\n⏱️  Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📂 All files saved to: {OUT_DIR}/")
    print(f"\n{'='*80}\n")
    
    # Save detailed log
    log_file = Path("SCRAPE_677500_707148_LOG.txt")
    with open(log_file, 'w') as f:
        f.write(f"SCRAPE LOG: {START_CASE} → {END_CASE}\n")
        f.write(f"{'='*80}\n\n")
        f.write(f"SUMMARY:\n")
        f.write(f"Found: {len(found_cases):,} cases\n")
        f.write(f"Missing: {sum(g[2] for g in missing_cases):,} cases\n")
        f.write(f"Errors: {len(errors_fixed)}\n\n")
        
        f.write(f"GAPS:\n")
        for gap_start, gap_end, gap_size in missing_cases:
            f.write(f"{gap_start} - {gap_end}: {gap_size} cases\n")
        
        if errors_fixed:
            f.write(f"\nERRORS:\n")
            for case_num, error in errors_fixed:
                f.write(f"{case_num}: {error}\n")
    
    print(f"📋 Detailed log saved to: {log_file}\n")

if __name__ == "__main__":
    main()
