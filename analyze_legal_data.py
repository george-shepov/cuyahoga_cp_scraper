#!/usr/bin/env python3

import json
import os
import sqlite3
from collections import defaultdict, Counter
import csv

# Connect to the database
conn = sqlite3.connect('out/cases.db')
cursor = conn.cursor()

# Get all case IDs and their JSON paths
cursor.execute("SELECT case_id, example_json_path FROM cases")
cases = cursor.fetchall()

# Data structures to store our findings
judges_cases: defaultdict[str, list[str]] = defaultdict(list)
attorneys_cases: defaultdict[str, list[str]] = defaultdict(list)
prosecutors_cases: defaultdict[str, list[str]] = defaultdict(list)
case_outcomes: defaultdict[str, Counter[str]] = defaultdict(Counter)
attorney_success_rates: defaultdict[str, dict[str, int]] = defaultdict(
    lambda: {"guilty": 0, "not_guilty": 0, "dismissed": 0, "other": 0}
)
prosecutor_success_rates: defaultdict[str, dict[str, int]] = defaultdict(
    lambda: {"guilty": 0, "not_guilty": 0, "dismissed": 0, "other": 0}
)

# Process each case
for i, (case_id, json_path) in enumerate(cases):
    # Print progress
    if i % 1000 == 0:
        print(f"Processing case {i}/{len(cases)}: {case_id} - analyze_legal_data.py:33")
    
    # Skip if JSON file doesn't exist
    if not os.path.exists(json_path):
        print(f"Warning: JSON file not found for case {case_id}: {json_path} - analyze_legal_data.py:37")
        continue
    
    # Read the JSON file
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading JSON for case {case_id}: {e} - analyze_legal_data.py:45")
        continue
    
    # Extract judge information
    judge = data.get("summary", {}).get("current_judge")
    if judge:
        judges_cases[judge].append(case_id)
    
    # Extract attorney information
    attorneys = data.get("attorneys", [])
    for attorney in attorneys:
        name = attorney.get("name")
        party = attorney.get("party")
        role = attorney.get("role")
        
        if name and party == "Defense":
            attorneys_cases[name].append(case_id)
            # Calculate defense attorney success rates
            charges = data.get("summary", {}).get("charges", [])
            for charge in charges:
                disposition = charge.get("disposition", "")
                if disposition is not None:
                    disposition = disposition.upper()
                    if "GUILTY" in disposition:
                        attorney_success_rates[name]["guilty"] += 1
                    elif "NOT GUILTY" in disposition:
                        attorney_success_rates[name]["not_guilty"] += 1
                    elif "DISMISS" in disposition or "NOLLE" in disposition:
                        attorney_success_rates[name]["dismissed"] += 1
                    else:
                        attorney_success_rates[name]["other"] += 1
                else:
                    attorney_success_rates[name]["other"] += 1
                    
        elif name and party == "Prosecution":
            prosecutors_cases[name].append(case_id)
            # Calculate prosecutor success rates
            charges = data.get("summary", {}).get("charges", [])
            for charge in charges:
                disposition = charge.get("disposition", "")
                if disposition is not None:
                    disposition = disposition.upper()
                    if "GUILTY" in disposition:
                        prosecutor_success_rates[name]["guilty"] += 1
                    elif "NOT GUILTY" in disposition:
                        prosecutor_success_rates[name]["not_guilty"] += 1
                    elif "DISMISS" in disposition or "NOLLE" in disposition:
                        prosecutor_success_rates[name]["dismissed"] += 1
                    else:
                        prosecutor_success_rates[name]["other"] += 1
                else:
                    prosecutor_success_rates[name]["other"] += 1

# Close database connection
conn.close()

# Write results to CSV files
print("Writing results to CSV files... - analyze_legal_data.py:102")

# Judges analysis
with open('judges_analysis.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Judge Name', 'Number of Cases', 'Notable Patterns'])
    for judge, cases_list in judges_cases.items():
        writer.writerow([judge, len(cases_list), ""])

# Attorneys analysis
with open('attorneys_analysis.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Attorney Name', 'Number of Cases', 'Guilty', 'Not Guilty', 'Dismissed', 'Other', 'Success Rate'])
    for attorney, cases_list in attorneys_cases.items():
        stats = attorney_success_rates[attorney]
        total = sum(stats.values())
        success_rate = (stats["not_guilty"] + stats["dismissed"]) / total if total > 0 else 0
        writer.writerow([
            attorney, 
            len(cases_list), 
            stats["guilty"], 
            stats["not_guilty"], 
            stats["dismissed"], 
            stats["other"], 
            f"{success_rate:.2%}"
        ])

# Prosecutors analysis
with open('prosecutors_analysis.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Prosecutor Name', 'Number of Cases', 'Guilty', 'Not Guilty', 'Dismissed', 'Other', 'Conviction Rate'])
    for prosecutor, cases_list in prosecutors_cases.items():
        stats = prosecutor_success_rates[prosecutor]
        total = sum(stats.values())
        conviction_rate = stats["guilty"] / total if total > 0 else 0
        writer.writerow([
            prosecutor, 
            len(cases_list), 
            stats["guilty"], 
            stats["not_guilty"], 
            stats["dismissed"], 
            stats["other"], 
            f"{conviction_rate:.2%}"
        ])

print("Analysis complete. Results saved to: - analyze_legal_data.py:147")
print("judges_analysis.csv - analyze_legal_data.py:148")
print("attorneys_analysis.csv - analyze_legal_data.py:149")
print("prosecutors_analysis.csv - analyze_legal_data.py:150")