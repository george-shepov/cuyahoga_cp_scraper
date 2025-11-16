#!/usr/bin/env python3
"""
Extract attorney information from October 2025 cases
"""
import json
from pathlib import Path
from collections import defaultdict

OUT_DIR = Path("out")
OCTOBER_FILES = []

# Find all October 2025 cases
for year_folder in ["2023", "2024", "2025"]:
    year_path = OUT_DIR / year_folder
    if year_path.exists():
        for json_file in year_path.glob("*.json"):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                    summary = data.get('summary', {}).get('fields', {})
                    # Check for 10/ pattern (10/17/2025, 10/20/2025, etc)
                    for key in summary.keys():
                        if key.startswith('10/') and key.endswith('2025'):
                            OCTOBER_FILES.append(json_file)
                            break
            except:
                pass

print(f"{'='*80}")
print(f"OCTOBER 2025 CUYAHOGA COUNTY CASES - ATTORNEY ANALYSIS")
print(f"{'='*80}\n")

print(f"Total Cases Found: {len(OCTOBER_FILES)}\n")

# Track attorneys and their clients
attorneys_clients = defaultdict(set)
attorney_case_count = defaultdict(int)
cases_with_attorneys = 0

for case_file in sorted(OCTOBER_FILES):
    try:
        with open(case_file) as f:
            data = json.load(f)
            metadata = data.get('metadata', {})
            case_id = metadata.get('case_id', 'N/A')
            
            # Get attorney info
            attorneys_data = data.get('attorneys', [])
            
            if attorneys_data:
                cases_with_attorneys += 1
                
                # attorneys_data is usually a list of dicts
                if isinstance(attorneys_data, list):
                    for attorney_entry in attorneys_data:
                        if isinstance(attorney_entry, dict):
                            # Extract attorney name - could be in different fields
                            attorney_name = attorney_entry.get('name') or \
                                          attorney_entry.get('Name') or \
                                          attorney_entry.get('Attorney') or \
                                          str(attorney_entry).split(',')[0]
                            
                            if attorney_name and attorney_name != 'N/A':
                                attorneys_clients[attorney_name].add(case_id)
                                attorney_case_count[attorney_name] += 1
                        elif isinstance(attorney_entry, str):
                            # Sometimes it's just a string
                            if attorney_entry and attorney_entry != 'N/A':
                                attorneys_clients[attorney_entry].add(case_id)
                                attorney_case_count[attorney_entry] += 1
                
                # Also check in summary for attorney names
                summary = data.get('summary', {}).get('fields', {})
                for key, value in summary.items():
                    if 'attorney' in key.lower() and isinstance(value, str):
                        if value and value != 'N/A' and len(value) > 3:
                            attorneys_clients[value].add(case_id)
                            attorney_case_count[value] += 1
    except Exception as e:
        pass

print(f"Cases with Attorney Information: {cases_with_attorneys}\n")
print(f"Unique Attorneys Found: {len(attorney_case_count)}\n")

if attorney_case_count:
    print(f"\nTOP 30 ATTORNEYS BY NUMBER OF CLIENTS:")
    print(f"{'-'*80}")
    print(f"{'Rank':<5} {'Attorney Name':<50} {'Clients':<10}")
    print(f"{'-'*80}")
    
    for rank, (attorney, count) in enumerate(sorted(attorney_case_count.items(), 
                                                     key=lambda x: x[1], 
                                                     reverse=True)[:30], 1):
        # Truncate long names
        attorney_name = attorney[:48] if len(attorney) > 48 else attorney
        print(f"{rank:<5} {attorney_name:<50} {count:<10}")
    
    print(f"\n\nTOP 10 ATTORNEYS WITH CLIENT DETAILS:")
    print(f"{'-'*80}")
    
    for rank, (attorney, count) in enumerate(sorted(attorney_case_count.items(), 
                                                     key=lambda x: x[1], 
                                                     reverse=True)[:10], 1):
        clients = attorneys_clients[attorney]
        print(f"\n{rank}. {attorney}")
        print(f"   Total Clients: {count}")
        print(f"   Case IDs: {', '.join(sorted(list(clients))[:5])}")
        if len(clients) > 5:
            print(f"   ... and {len(clients) - 5} more cases")

else:
    print("\nNo attorney data found in case files.")
    print("\nThis might be because:")
    print("  - Attorney information is embedded in docket entries, not a separate field")
    print("  - Checking docket entries for attorney names...")
    
    # Try extracting from docket
    attorneys_in_docket = defaultdict(int)
    
    for case_file in sorted(OCTOBER_FILES):
        try:
            with open(case_file) as f:
                data = json.load(f)
                docket = data.get('docket', [])
                
                for entry in docket:
                    desc = entry.get('Description', '')
                    if 'attorney' in desc.lower() or 'counsel' in desc.lower():
                        # Extract potential attorney names
                        attorneys_in_docket[desc[:60]] += 1
        except:
            pass
    
    if attorneys_in_docket:
        print(f"\n\nDOCKET ENTRIES MENTIONING ATTORNEYS (Top 20):")
        print(f"{'-'*80}")
        for rank, (desc, count) in enumerate(sorted(attorneys_in_docket.items(), 
                                                      key=lambda x: x[1], 
                                                      reverse=True)[:20], 1):
            print(f"{rank}. {desc}: {count} entries")

print(f"\n{'='*80}\n")
