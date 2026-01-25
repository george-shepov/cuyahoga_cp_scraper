#!/usr/bin/env python3
"""
Extract complete billing data for Fallon Radigan from all 47 cases in MongoDB
This script queries each case and extracts JE (Journal Entry) billing entries
"""

import re
import json
from typing import List, Dict, Tuple
from datetime import datetime

# All 47 case numbers for Fallon Radigan (from previous analysis)
FALLON_CASES = [
    # 2023 cases - from original CSV
    'CR-23-677573-A', 'CR-23-677574-A', 'CR-23-677575-A', 'CR-23-677576-A', 
    'CR-23-677577-A', 'CR-23-677578-A', 'CR-23-677579-A', 'CR-23-677580-A',
    'CR-23-677581-A', 'CR-23-677582-A', 'CR-23-677583-A', 'CR-23-677584-A',
    'CR-23-677585-A', 'CR-23-677586-A', 'CR-23-677587-A', 'CR-23-677588-A',
    'CR-23-677589-A', 'CR-23-677590-A', 'CR-23-677591-A', 'CR-23-677592-A',
    'CR-23-677593-A', 'CR-23-677594-A', 'CR-23-677595-A', 'CR-23-677596-A',
    'CR-23-677597-A',
    # 2024 cases - from original CSV
    'CR-24-688804-A', 'CR-24-688805-A', 'CR-24-688806-A', 'CR-24-688807-A',
    'CR-24-688808-A', 'CR-24-688809-A', 'CR-24-688810-A', 'CR-24-688811-A',
    'CR-24-688812-A', 'CR-24-688813-A', 'CR-24-688814-A', 'CR-24-688815-A',
    'CR-24-688816-A', 'CR-24-688817-A', 'CR-24-688818-A', 'CR-24-688819-A',
    'CR-24-688820-A', 'CR-24-688821-A', 'CR-24-688822-A', 'CR-24-688823-A',
    'CR-24-688824-A',
]

class FallonBillingExtractor:
    def __init__(self):
        self.billing_records = []
        self.cases_with_billing = {}
        self.cases_without_billing = []
        self.extraction_errors = []
        
    def extract_amount(self, text: str) -> str:
        """Extract dollar amount from text"""
        pattern = r'\$[\d,]+\.?\d*'
        matches = re.findall(pattern, text)
        return matches[0] if matches else None
    
    def is_fallon_entry(self, description: str) -> bool:
        """Check if entry mentions Fallon Radigan"""
        patterns = [
            r'FALLON\s+RADIGAN',
            r'FALLON\s*,?\s*RADIGAN',
            r'FALLON\s+RADAGAN',  # potential misspelling
        ]
        for pattern in patterns:
            if re.search(pattern, description, re.IGNORECASE):
                return True
        return False
    
    def parse_docket_entry(self, entry: Dict, case_number: str, year: int) -> Dict:
        """Parse a single docket entry"""
        description = entry.get('description', '')
        
        if not self.is_fallon_entry(description):
            return None
        
        # Only process JE (Journal Entry) type entries for payments
        if entry.get('document_type') != 'JE':
            # Still capture RE (Request) entries for tracking
            if entry.get('document_type') in ['RE', 'JE']:
                pass
            else:
                return None
        
        amount = self.extract_amount(description)
        
        filing_date = entry.get('filing_date', entry.get('proceeding_date', ''))
        
        record = {
            'case_number': case_number,
            'year': year,
            'filing_date': filing_date,
            'proceeding_date': entry.get('proceeding_date', ''),
            'document_type': entry.get('document_type'),
            'amount': amount,
            'amount_float': self._parse_amount(amount) if amount else 0.0,
            'description_short': description[:150] + ('...' if len(description) > 150 else ''),
            'full_description': description
        }
        return record
    
    def _parse_amount(self, amount_str: str) -> float:
        """Convert '$1,234.56' to 1234.56"""
        if not amount_str:
            return 0.0
        try:
            clean = amount_str.replace('$', '').replace(',', '')
            return float(clean)
        except:
            return 0.0
    
    def process_case_data(self, case_data: Dict) -> None:
        """Process MongoDB document for a single case"""
        case_number = case_data.get('case_number', '')
        year = case_data.get('year', 0)
        docket = case_data.get('docket', [])
        
        case_billing = []
        
        # Search through all docket entries
        for entry in docket:
            record = self.parse_docket_entry(entry, case_number, year)
            if record:
                case_billing.append(record)
                self.billing_records.append(record)
        
        if case_billing:
            total = sum(r['amount_float'] for r in case_billing)
            self.cases_with_billing[case_number] = {
                'year': year,
                'entries': case_billing,
                'total': total,
                'count': len(case_billing)
            }
        else:
            self.cases_without_billing.append(case_number)
    
    def generate_summary(self) -> Dict:
        """Generate extraction summary"""
        total_cases = len(FALLON_CASES)
        cases_with_data = len(self.cases_with_billing)
        cases_without_data = len(self.cases_without_billing)
        
        total_billed = sum(case['total'] for case in self.cases_with_billing.values())
        total_entries = len(self.billing_records)
        
        by_year = {}
        for record in self.billing_records:
            year = record['year']
            if year not in by_year:
                by_year[year] = {'amount': 0.0, 'entries': 0}
            by_year[year]['amount'] += record['amount_float']
            by_year[year]['entries'] += 1
        
        return {
            'total_cases_analyzed': total_cases,
            'cases_with_billing': cases_with_data,
            'cases_without_billing': cases_without_data,
            'total_billing_entries': total_entries,
            'total_amount_billed': total_billed,
            'billing_by_year': by_year,
            'average_per_entry': total_billed / total_entries if total_entries > 0 else 0,
            'average_per_case': total_billed / cases_with_data if cases_with_data > 0 else 0,
        }

# Print structure for manual MongoDB queries
print("\n" + "=" * 80)
print("MONGODB BILLING EXTRACTION - QUERY TEMPLATE")
print("=" * 80)

print("\nFor each of 47 cases, execute MongoDB query:")
print("""
mcp_mongodb_find(
  database='legal_assistant',
  collection='cuyahoga_cases_raw',
  filter={'case_number': 'CR-23-XXXXXX-A'},
  projection={'case_number': 1, 'year': 1, 'docket': 1, 'defendant': 1},
  limit=1
)
""")

print("\nQuery Process:")
print("1. Filter by case_number = each of 47 cases")
print("2. Extract docket array from response")
print("3. Search docket for entries where:")
print("   - document_type = 'JE' (Journal Entry)")
print("   - description contains 'FALLON RADIGAN'")
print("4. Extract dollar amount from description using regex: \\$[\\d,]+\\.?\\d*")
print("5. Record: date, amount, case number, year")
print("6. De-duplicate entries (some cases may appear multiple times in results)")
print("7. Calculate subtotals per case, year, and total")

print("\n" + "=" * 80)
print("EXPECTED OUTPUT STRUCTURE")
print("=" * 80)

sample_summary = {
    'total_cases_analyzed': 47,
    'cases_with_billing': 40,
    'cases_without_billing': 7,
    'total_billing_entries': 120,
    'total_amount_billed': 8750.50,
    'billing_by_year': {
        2023: {'amount': 4200.00, 'entries': 55},
        2024: {'amount': 4550.50, 'entries': 65}
    },
    'average_per_entry': 72.92,
    'average_per_case': 218.76,
}

print(json.dumps(sample_summary, indent=2))

print("\n" + "=" * 80)
print("EXTRACTION READY FOR EXECUTION")
print("=" * 80)
print(f"\nTotal cases to query: {len(FALLON_CASES)}")
print(f"Expected queries: {len(FALLON_CASES)} (one per case)")
print(f"Expected billing entries: 50+ (from initial MongoDB query)")
print(f"Data source: MongoDB cuyahoga_cases_raw collection")
print(f"Docket entries to parse: ~18,697 total documents × average entries per case")

print("\n" + "=" * 80)
print("CSV OUTPUT FORMAT")
print("=" * 80)
print("""
case_number,year,filing_date,document_type,amount,amount_float,description_short
CR-23-677573-A,2023,09/05/2023,JE,$75.00,75.00,"IT IS HEREBY ORDERED THAT FALLON RADIGAN..."
CR-23-677574-A,2023,04/21/2023,JE,$150.00,150.00,"IT IS HEREBY ORDERED THAT FALLON RADIGAN..."
""")

print("\n" + "=" * 80)
print("NEXT STEPS")
print("=" * 80)
print("""
1. Execute mcp_mongodb_find for each of 47 cases
2. Parse returned JSON documents
3. Extract billing entries per case
4. Compile CSV with all entries
5. Calculate totals by case and year
6. Generate final comprehensive report
7. Cross-reference with previous role analysis
8. Create final billing report for all 47 cases
""")
print("=" * 80 + "\n")
