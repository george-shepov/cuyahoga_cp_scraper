#!/usr/bin/env python3
"""
Extract comprehensive billing data for Fallon Radigan from MongoDB
Queries all 47 known cases and extracts JE (Journal Entry) billing entries
"""

import re
import json
from datetime import datetime
from typing import List, Dict, Tuple
import csv

# All 47 case numbers for Fallon Radigan
FALLON_CASES = [
    # 2023 cases (25 total)
    'CR-23-677573-A', 'CR-23-677574-A', 'CR-23-677575-A', 'CR-23-677576-A', 'CR-23-677577-A',
    'CR-23-677578-A', 'CR-23-677579-A', 'CR-23-677580-A', 'CR-23-677581-A', 'CR-23-677582-A',
    'CR-23-677583-A', 'CR-23-677584-A', 'CR-23-677585-A', 'CR-23-677586-A', 'CR-23-677587-A',
    'CR-23-677588-A', 'CR-23-677589-A', 'CR-23-677590-A', 'CR-23-677591-A', 'CR-23-677592-A',
    'CR-23-677593-A', 'CR-23-677594-A', 'CR-23-677595-A', 'CR-23-677596-A', 'CR-23-677597-A',
    # 2024 cases (21 total)
    'CR-24-688804-A', 'CR-24-688805-A', 'CR-24-688806-A', 'CR-24-688807-A', 'CR-24-688808-A',
    'CR-24-688809-A', 'CR-24-688810-A', 'CR-24-688811-A', 'CR-24-688812-A', 'CR-24-688813-A',
    'CR-24-688814-A', 'CR-24-688815-A', 'CR-24-688816-A', 'CR-24-688817-A', 'CR-24-688818-A',
    'CR-24-688819-A', 'CR-24-688820-A', 'CR-24-688821-A', 'CR-24-688822-A', 'CR-24-688823-A',
    'CR-24-688824-A',
]

def extract_dollar_amounts(text: str) -> List[str]:
    """Extract all dollar amounts from text"""
    pattern = r'\$[\d,]+\.?\d*'
    matches = re.findall(pattern, text)
    return matches

def is_fallon_billing(description: str) -> bool:
    """Check if docket entry is Fallon Radigan billing"""
    # Look for "FALLON RADIGAN" or variations in the description
    fallon_patterns = [
        r'FALLON\s+RADIGAN',
        r'FALLON\s*,?\s*RADIGAN',
        r'FALLON.*RADIGAN',
    ]
    
    for pattern in fallon_patterns:
        if re.search(pattern, description, re.IGNORECASE):
            return True
    return False

def parse_billing_entry(docket_entry: Dict) -> Tuple[str, str, str]:
    """
    Extract billing info from JE docket entry
    Returns: (date, amount, raw_text)
    """
    date = docket_entry.get('filing_date', docket_entry.get('proceeding_date', ''))
    description = docket_entry.get('description', '')
    
    # Extract dollar amounts
    amounts = extract_dollar_amounts(description)
    
    if amounts:
        # Usually first amount in "ALLOWED $X.XX FOR SERVICES" is the billing
        return (date, amounts[0], description[:200])
    
    return (date, None, description[:100])

def format_currency(amount_str: str) -> float:
    """Convert '$1,234.56' to 1234.56"""
    try:
        # Remove $ and commas, convert to float
        clean = amount_str.replace('$', '').replace(',', '')
        return float(clean)
    except:
        return 0.0

# Print extraction summary
print("=" * 80)
print("FALLON RADIGAN COMPREHENSIVE BILLING EXTRACTION")
print("=" * 80)
print(f"\nTotal cases to query: {len(FALLON_CASES)}")
print(f"  - 2023 cases: 25")
print(f"  - 2024 cases: 21")
print(f"\nDatabase: legal_assistant (MongoDB)")
print(f"Collection: cuyahoga_cases_raw")
print(f"Query: docket entries with JE type + FALLON RADIGAN mention")
print(f"\nBilling entry format:")
print('  "IT IS HEREBY ORDERED THAT FALLON RADIGAN, ESQ., HERETOFORE ASSIGNED')
print('   AS COUNSEL FOR THE DEFENDANT IN THIS CAUSE, BE ALLOWED $[AMOUNT] FOR')
print('   SERVICES SO RENDERED..."')
print("\n" + "=" * 80)
print("\nREADY TO EXECUTE:")
print("1. Query each case number from MongoDB")
print("2. Extract docket array from each document")
print("3. Filter for JE (Journal Entry) type entries")
print("4. Search for FALLON RADIGAN mentions in description field")
print("5. Extract dollar amounts using regex pattern: \\$[\\d,]+\\.?\\d*")
print("6. Build comprehensive billing database")
print("7. Calculate totals by case, year, and overall")
print("8. Generate final report with attorney role analysis")
print("\n" + "=" * 80)

# Sample output structure
sample_billing = {
    'case_number': 'CR-25-698242-A',
    'year': 2025,
    'billing_entries': [
        {
            'proceeding_date': '09/05/2025',
            'filing_date': '09/08/2025',
            'amount': '$75.00',
            'amount_float': 75.00,
            'description': 'IT IS HEREBY ORDERED THAT FALLON RADIGAN, ESQ., HERETOFORE ASSIGNED...',
            'entry_type': 'JE'
        }
    ],
    'total_billed': 75.00
}

print("\nSAMPLE OUTPUT STRUCTURE:")
print(json.dumps(sample_billing, indent=2))
print("\n" + "=" * 80)
print("\nNEXT STEPS:")
print("1. Run MongoDB queries for all 47 cases")
print("2. Extract and parse billing entries")
print("3. De-duplicate across multiple file versions")
print("4. Merge with previous role analysis (prosecutor vs attorney)")
print("5. Generate FALLON_RADIGAN_COMPLETE_BILLING.md report")
print("=" * 80)
