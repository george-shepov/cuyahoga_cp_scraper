#!/usr/bin/env python3
"""
Extract all cases between two markers and save to a destination folder
First marker: CR-23-677500 (2023, case 677500)
Last marker: CR-25-707148 (2025, case 707148)
"""

import json
import shutil
from pathlib import Path
from collections import defaultdict

# Define markers
FIRST_CASE_YEAR = 2023
FIRST_CASE_NUM = 677500
LAST_CASE_YEAR = 2025
LAST_CASE_NUM = 707148

# Source and destination
SOURCE_DIR = Path("out")
DEST_DIR = Path.home() / "Desktop" / "CUYAHOGA_CASES_677500_707148"

def extract_year_and_number(filename: str) -> tuple:
    """Extract year and case number from filename like 2025-706395_20251110_024420.json"""
    try:
        parts = filename.split('_')[0]  # Get "2025-706395"
        year, num = parts.split('-')
        return int(year), int(num)
    except:
        return None, None

def is_in_range(year: int, num: int) -> bool:
    """Check if a case is within our markers"""
    # Convert to comparable format
    case_key = year * 1000000 + num
    first_key = FIRST_CASE_YEAR * 1000000 + FIRST_CASE_NUM
    last_key = LAST_CASE_YEAR * 1000000 + LAST_CASE_NUM
    return first_key <= case_key <= last_key

def main():
    """Extract and copy all cases in range"""
    
    # Create destination
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    
    # Organize by year
    cases_by_year = defaultdict(list)
    total_count = 0
    
    print(f"🔍 Scanning source directory: {SOURCE_DIR}")
    print(f"📦 Destination: {DEST_DIR}")
    print(f"📍 Range: CR-{FIRST_CASE_YEAR}-{FIRST_CASE_NUM:06d} to CR-{LAST_CASE_YEAR}-{LAST_CASE_NUM:06d}")
    print()
    
    # Find all JSON files
    for year_folder in SOURCE_DIR.glob("*/"):
        if year_folder.is_dir():
            year_name = year_folder.name
            json_files = list(year_folder.glob("*.json"))
            
            for json_file in json_files:
                year, num = extract_year_and_number(json_file.name)
                
                if year is None or num is None:
                    continue
                
                if is_in_range(year, num):
                    cases_by_year[year].append((num, json_file))
                    total_count += 1
    
    # Copy files organized by year
    for year in sorted(cases_by_year.keys()):
        year_dest = DEST_DIR / str(year)
        year_dest.mkdir(exist_ok=True)
        
        cases = sorted(cases_by_year[year])
        print(f"📁 Year {year}: {len(cases)} cases")
        
        for num, source_file in cases:
            dest_file = year_dest / source_file.name
            shutil.copy2(source_file, dest_file)
    
    print()
    print(f"✅ Extraction complete!")
    print(f"📊 Total cases copied: {total_count}")
    print(f"📂 Destination folder: {DEST_DIR}")
    
    # Create summary file
    summary_file = DEST_DIR / "EXTRACTION_SUMMARY.txt"
    with open(summary_file, 'w') as f:
        f.write(f"""CUYAHOGA COUNTY CASES EXTRACTION SUMMARY
========================================

Range: CR-{FIRST_CASE_YEAR}-{FIRST_CASE_NUM:06d} through CR-{LAST_CASE_YEAR}-{LAST_CASE_NUM:06d}
Total Cases: {total_count}

Cases by Year:
""")
        
        for year in sorted(cases_by_year.keys()):
            count = len(cases_by_year[year])
            nums = [num for num, _ in sorted(cases_by_year[year])]
            min_num = min(nums)
            max_num = max(nums)
            f.write(f"  {year}: {count} cases (CR-{year}-{min_num:06d} to CR-{year}-{max_num:06d})\n")

if __name__ == "__main__":
    main()
