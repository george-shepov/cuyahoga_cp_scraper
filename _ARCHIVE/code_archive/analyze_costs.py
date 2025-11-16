#!/usr/bin/env python3
"""
Calculate total costs from October 2025 cases
"""
import json
import re
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
print(f"OCTOBER 2025 CUYAHOGA COUNTY CASES - COST ANALYSIS")
print(f"{'='*80}\n")

print(f"Total Cases Found: {len(OCTOBER_FILES)}\n")

# Track costs
total_cost = 0.0
cases_with_costs = 0
cost_breakdown = defaultdict(float)
individual_costs = []

for case_file in sorted(OCTOBER_FILES):
    try:
        with open(case_file) as f:
            data = json.load(f)
            metadata = data.get('metadata', {})
            case_id = metadata.get('case_id', 'N/A')
            case_num = metadata.get('case_number_formatted', 'N/A')
            
            # Get costs
            costs_data = data.get('costs', [])
            
            if costs_data and isinstance(costs_data, list):
                case_total = 0.0
                cost_items = []
                
                for cost_entry in costs_data:
                    if isinstance(cost_entry, dict):
                        # Look for amount in various possible fields
                        amount_str = cost_entry.get('col2') or \
                                    cost_entry.get('amount') or \
                                    cost_entry.get('Amount') or \
                                    cost_entry.get('Total') or \
                                    ''
                        
                        # Extract description
                        desc = cost_entry.get('col1') or \
                              cost_entry.get('description') or \
                              cost_entry.get('Description') or \
                              'Unknown'
                        
                        # Parse dollar amount
                        if amount_str:
                            # Remove $ and commas, convert to float
                            amount_clean = re.sub(r'[\$,]', '', str(amount_str).strip())
                            try:
                                amount = float(amount_clean)
                                case_total += amount
                                cost_items.append((desc, amount))
                                cost_breakdown[desc] += amount
                            except ValueError:
                                pass
                
                if case_total > 0:
                    cases_with_costs += 1
                    total_cost += case_total
                    individual_costs.append({
                        'case_id': case_id,
                        'case_num': case_num,
                        'total': case_total,
                        'items': cost_items
                    })
    except Exception as e:
        pass

print(f"Cases with Cost Information: {cases_with_costs}\n")
print(f"{'='*80}")
print(f"GRAND TOTAL OF ALL COSTS: ${total_cost:,.2f}")
print(f"{'='*80}\n")

if cases_with_costs > 0:
    avg_cost = total_cost / cases_with_costs
    print(f"Average Cost per Case: ${avg_cost:,.2f}\n")

print(f"\nCOST BREAKDOWN BY TYPE (Top 15):")
print(f"{'-'*80}")
for desc, amount in sorted(cost_breakdown.items(), key=lambda x: x[1], reverse=True)[:15]:
    desc_short = desc[:50] if len(desc) > 50 else desc
    pct = (amount / total_cost * 100) if total_cost > 0 else 0
    print(f"  {desc_short:<50} ${amount:>12,.2f}  ({pct:>5.1f}%)")

print(f"\n\nTOP 20 MOST EXPENSIVE CASES:")
print(f"{'-'*80}")
print(f"{'Rank':<5} {'Case ID':<18} {'Case #':<12} {'Total Cost':<12}")
print(f"{'-'*80}")

for rank, case in enumerate(sorted(individual_costs, key=lambda x: x['total'], reverse=True)[:20], 1):
    print(f"{rank:<5} {case['case_id']:<18} {case['case_num']:<12} ${case['total']:>10,.2f}")

print(f"\n\nSAMPLE COST DETAILS (Cases with highest costs):")
print(f"{'-'*80}")

for rank, case in enumerate(sorted(individual_costs, key=lambda x: x['total'], reverse=True)[:5], 1):
    print(f"\n{rank}. {case['case_id']} - {case['case_num']}")
    print(f"   Total: ${case['total']:,.2f}")
    print(f"   Cost Items:")
    for desc, amount in case['items']:
        desc_short = desc[:60] if len(desc) > 60 else desc
        print(f"     - {desc_short:<60} ${amount:>10,.2f}")

print(f"\n{'='*80}")
print(f"Analysis Complete")
print(f"{'='*80}\n")
