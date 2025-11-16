#!/usr/bin/env python3
"""
Analysis script for October 2025 cases from Cuyahoga County docket
"""
import json
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime

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
print(f"OCTOBER 2025 CUYAHOGA COUNTY CASES - COMPREHENSIVE ANALYSIS")
print(f"{'='*80}\n")

print(f"Total Cases Found: {len(OCTOBER_FILES)}\n")

# Analyze each case
case_data = []
judges = defaultdict(int)
charges = defaultdict(int)
defendants_dict = defaultdict(int)
status_counts = defaultdict(int)
agencies = defaultdict(int)
races = defaultdict(int)
genders = defaultdict(int)
ages = defaultdict(int)

for case_file in sorted(OCTOBER_FILES):
    try:
        with open(case_file) as f:
            data = json.load(f)
            metadata = data.get('metadata', {})
            summary = data.get('summary', {}).get('fields', {})
            defendant = data.get('defendant', {})
            
            case_num = metadata.get('case_number_formatted', 'N/A')
            case_id = metadata.get('case_id', 'N/A')
            judge = summary.get('Judge Name:', 'Unassigned')
            status = summary.get('Status:', 'UNKNOWN')
            defendant_name = summary.get('Name:', 'Unknown')
            dob = summary.get('Date of Birth:', 'N/A')
            race = summary.get('Race:', 'N/A')
            sex = summary.get('Sex:', 'N/A')
            agency = summary.get('Arresting Agency:', 'N/A')
            
            # Parse charges
            charge_table = summary.get('embedded_table_0', {})
            if isinstance(charge_table, dict) and charge_table.get('format') == 'csv':
                csv_data = charge_table.get('data', '')
                if csv_data and 'Charge Description' in csv_data:
                    lines = csv_data.split('\r\n')
                    if len(lines) > 1:
                        charge_desc = lines[1].split(',')[2] if len(lines[1].split(',')) > 2 else 'N/A'
                        charges[charge_desc] += 1
            
            if judge and judge != 'Unassigned':
                judges[judge] += 1
            status_counts[status] += 1
            defendants_dict[defendant_name] += 1
            agencies[agency] += 1
            races[race] += 1
            genders[sex] += 1
            
            case_data.append({
                'number': case_num,
                'case_id': case_id,
                'judge': judge,
                'status': status,
                'defendant': defendant_name,
                'dob': dob,
                'race': race,
                'sex': sex,
                'agency': agency,
                'file': str(case_file)
            })
    except Exception as e:
        pass

# Print results
print(f"\nCHARGES (Top 15):")
print(f"{'-'*60}")
for charge, count in sorted(charges.items(), key=lambda x: x[1], reverse=True)[:15]:
    pct = (count / len(OCTOBER_FILES)) * 100
    print(f"  {charge}: {count:4d} ({pct:5.1f}%)")

print(f"\n\nASSIGNED JUDGES (Top 15):")
print(f"{'-'*60}")
for judge, count in sorted(judges.items(), key=lambda x: x[1], reverse=True)[:15]:
    pct = (count / len(OCTOBER_FILES)) * 100
    print(f"  {judge}: {count:4d} ({pct:5.1f}%)")

print(f"\n\nCASE STATUS:")
print(f"{'-'*60}")
for status, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True):
    pct = (count / len(OCTOBER_FILES)) * 100
    print(f"  {status}: {count:4d} ({pct:5.1f}%)")

print(f"\n\nARRESTING AGENCIES (Top 10):")
print(f"{'-'*60}")
for agency, count in sorted(agencies.items(), key=lambda x: x[1], reverse=True)[:10]:
    pct = (count / len(OCTOBER_FILES)) * 100
    print(f"  {agency}: {count:4d} ({pct:5.1f}%)")

print(f"\n\nRACES:")
print(f"{'-'*60}")
for race, count in sorted(races.items(), key=lambda x: x[1], reverse=True):
    pct = (count / len(OCTOBER_FILES)) * 100
    print(f"  {race}: {count:4d} ({pct:5.1f}%)")

print(f"\n\nGENDER:")
print(f"{'-'*60}")
for gender, count in sorted(genders.items(), key=lambda x: x[1], reverse=True):
    pct = (count / len(OCTOBER_FILES)) * 100
    print(f"  {gender}: {count:4d} ({pct:5.1f}%)")

print(f"\n\nTOP DEFENDANTS (Top 10):")
print(f"{'-'*60}")
for defendant, count in sorted(defendants_dict.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"  {defendant}: {count}")

print(f"\n\nSAMPLE CASES (First 20):")
print(f"{'-'*80}")
for i, case in enumerate(case_data[:20], 1):
    print(f"{i:2d}. {case['case_id']} - {case['number']}")
    print(f"    Defendant: {case['defendant']}")
    print(f"    Judge: {case['judge']}")
    print(f"    Status: {case['status']}")
    print(f"    Agency: {case['agency']}")
    print(f"    Race/Sex: {case['race']}/{case['sex']}")
    print()

print(f"\n{'='*80}")
print(f"Analysis Complete - {len(OCTOBER_FILES)} cases processed")
print(f"{'='*80}\n")
