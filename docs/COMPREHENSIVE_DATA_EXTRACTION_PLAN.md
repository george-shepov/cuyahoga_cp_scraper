# Comprehensive Data Extraction Plan
## Cuyahoga CP Scraper - Complete Data Capture Strategy

### Current State Analysis (Based on CR-25-706402-A)

#### ✅ **Working Extraction**
- Summary tab: Case info, defendant info, charges table, case actions, bond info
- Docket tab: All docket entries with PDF links
- Defendant tab: Single defendant information
- PDFs: All docket documents downloaded successfully

#### ❌ **Missing/Broken Extraction**

1. **Costs Tab** - `costs: []` (empty)
   - **Available Data**: 
     - Standard Fees (LEGAL RESEARCH, COURT SPECIAL PROJECTS FUND, CRIME STOPPERS, COMPUTER FEE, CLERK FEE)
     - WRIT FEE entries
     - Amounts, dates, payment status
   - **Issue**: Context destruction during tab navigation causes extraction failure
   - **Fix Required**: Robust retry logic with proper wait times

2. **Co-Defendants** - Not tracked separately
   - **Available Data**: `Co-Defendants: N/A` field in Summary tab
   - **Need**: Parse this field, link to other case numbers when present
   - **Multi-defendant cases exist** - need to track ALL defendants per case

3. **Judge Tracking** - Limited
   - **Currently Captured**: Only current assigned judge ("ARRAIGNMENT ROOM")
   - **Missing**:
     - Judge assignment history (changes during case lifecycle)
     - Final verdict/disposition per judge
     - Judge's ruling on each motion
   - **Need**: Historical timeline of judge assignments from docket entries

4. **Charge Dispositions** - Incomplete
   - **Currently Captured**: Charge type, statute, description
   - **Missing**: Disposition column ("DISMISSED", "GUILTY", "NOT GUILTY", "PLEA BARGAIN")
   - **Need**: Parse disposition from charges table, track verdict per charge

5. **Attorney Information** - Partial
   - **Currently Captured**: Attorney names from Attorney tab
   - **Missing**:
     - **Party affiliation** (Defense vs Prosecution)
     - **Prosecutor information** (State of Ohio attorneys)
     - **Attorney assignment dates**
     - **Attorney role** (Lead, Co-counsel, Appointed, Retained)
   - **Need**: Enhanced attorney extraction with party classification

6. **Case Outcomes** - No tracking
   - **Need**: Structured outcome data:
     - Final case status (CONVICTED, DISMISSED, ACQUITTED, PENDING)
     - Sentence information (if convicted)
     - Plea deal details
     - Appeal status

### Required Data Structure Enhancements

#### 1. **Costs Array** (Currently empty)
```json
"costs": [
  {
    "date": "10/17/2025",
    "type": "SF",
    "description": "LEGAL RESEARCH",
    "amount": "$20.00",
    "paid": "$0.00",
    "balance": "$20.00",
    "payment_date": null
  },
  {
    "date": "10/17/2025",
    "type": "SF",
    "description": "COURT SPECIAL PROJECTS FUND",
    "amount": "$5.00",
    "paid": "$0.00",
    "balance": "$5.00"
  }
]
```

#### 2. **Co-Defendants** (New field)
```json
"co_defendants": [
  {
    "name": "John Doe",
    "case_number": "CR-25-706403-A",
    "relationship": "Co-defendant"
  }
],
"is_multi_defendant_case": false
```

#### 3. **Judge History** (Enhanced from single field)
```json
"judge_history": [
  {
    "judge_name": "ARRAIGNMENT ROOM",
    "assigned_date": "10/16/2025",
    "assignment_type": "Initial",
    "current": true
  },
  {
    "judge_name": "Hon. Jane Smith",
    "assigned_date": "11/17/2025",
    "assignment_type": "Reassignment",
    "current": false,
    "reason": "Post-arraignment assignment"
  }
],
"current_judge": "ARRAIGNMENT ROOM",
"final_judge": null  // Judge who issued final ruling
```

#### 4. **Charge Dispositions** (Enhanced existing charges)
```json
"charges": [
  {
    "type": "INDICT",
    "statute": "2925.11.A",
    "charge_description": "DRUG POSSESSION",
    "disposition": null,  // GUILTY, NOT GUILTY, DISMISSED, NOLLE PROSEQUI
    "disposition_date": null,
    "plea": null,  // GUILTY, NOT GUILTY, NO CONTEST
    "verdict": null,  // If went to trial
    "sentence": null  // If convicted
  }
]
```

#### 5. **Attorneys** (Enhanced tracking)
```json
"attorneys": [
  {
    "name": "John Smith",
    "party": "Defense",  // Defense, Prosecution, State
    "role": "Lead Defense Counsel",
    "type": "Retained",  // Retained, Public Defender, Appointed
    "contact": "123 Main St, Cleveland OH 44114, (216) 555-1234",
    "assigned_date": "10/16/2025",
    "withdrawn_date": null,
    "bar_number": null
  },
  {
    "name": "Michael O'Malley",
    "party": "Prosecution",
    "role": "Prosecuting Attorney",
    "office": "Cuyahoga County Prosecutor",
    "contact": null,
    "assigned_date": "10/16/2025"
  }
]
```

#### 6. **Case Outcome** (New section)
```json
"outcome": {
  "final_status": "PENDING",  // PENDING, CONVICTED, DISMISSED, ACQUITTED, PLEA BARGAIN
  "disposition_date": null,
  "disposing_judge": null,
  "plea_deal": null,
  "sentence": {
    "incarceration": null,
    "probation": null,
    "fines": null,
    "restitution": null,
    "community_service": null
  },
  "appeal_filed": false,
  "appeal_case_number": null
}
```

### Implementation Priority

#### Phase 1: Fix Broken Extraction (Immediate)
1. ✅ **Fix Costs extraction**
   - Add retry logic with longer waits
   - Handle context destruction gracefully
   - Parse costs table into structured array

2. ✅ **Parse Co-Defendants field**
   - Extract from Summary tab
   - Parse case numbers if linked
   - Flag multi-defendant cases

#### Phase 2: Enhanced Data Capture (High Priority)
3. ✅ **Extract Charge Dispositions**
   - Parse disposition column from charges table
   - Track plea vs verdict
   - Capture sentence information

4. ✅ **Enhance Attorney Tracking**
   - Classify Defense vs Prosecution
   - Extract prosecutor from case title or attorney tab
   - Parse attorney roles and types

#### Phase 3: Historical/Analytical Data (Medium Priority)
5. ✅ **Judge History Tracking**
   - Parse judge assignments from docket
   - Track reassignments with reasons
   - Identify final/disposing judge

6. ✅ **Case Outcome Structure**
   - Parse final status from docket
   - Extract sentence details
   - Track appeals

#### Phase 4: Analytics & Reporting (Future)
7. **Attorney Performance Metrics**
   - Win/Loss ratio per attorney
   - Case types handled
   - Average case duration
   - Conviction rate (for prosecutors)
   - Acquittal/dismissal rate (for defense)

8. **Judge Analytics**
   - Conviction rates by judge
   - Average sentences by judge and charge type
   - Motion grant/denial rates
   - Case disposition times

9. **Prosecutor Office Tracking**
   - Conviction rates by prosecutor
   - Plea bargain vs trial rates
   - Charge reduction patterns

### Technical Implementation Notes

#### Costs Extraction Fix
```python
async def extract_costs_with_retry(page: Page) -> List[Dict[str, Any]]:
    """Extract costs with robust retry and context recovery"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Wait for table to be fully loaded
            await page.wait_for_selector("table.gridview", state="visible", timeout=10000)
            await asyncio.sleep(1.0)  # Additional stabilization
            
            costs = await grid_from_table(page, "table.gridview")
            if costs:
                return costs
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(2.0)
                continue
            else:
                console.print(f"[yellow]⚠ Costs extraction failed after {max_retries} attempts: {str(e)[:100]}[/yellow]")
                return []
    return []
```

#### Co-Defendant Parsing
```python
def parse_co_defendants(summary_fields: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse co-defendants from summary co-defendants field"""
    co_def_text = summary_fields.get("Co-Defendants:", "N/A")
    if co_def_text == "N/A" or not co_def_text:
        return []
    
    # Parse linked case numbers
    # Format: <a href='...'>CR-25-123456-A</a>, <a href='...'>CR-25-123457-A</a>
    case_numbers = re.findall(r'(CR-\d{2}-\d{6}-[A-Z])', co_def_text)
    
    return [{"case_number": cn, "relationship": "Co-defendant"} for cn in case_numbers]
```

#### Attorney Party Classification
```python
def classify_attorney_party(attorney_name: str, case_title: str) -> str:
    """Classify attorney as Defense or Prosecution"""
    attorney_lower = attorney_name.lower()
    
    # Prosecution indicators
    if any(x in attorney_lower for x in ["prosecutor", "o'malley", "state of ohio"]):
        return "Prosecution"
    
    # Defense is default for listed attorneys
    return "Defense"
```

### Testing Strategy

1. **Test on known multi-defendant case**
2. **Test on case with disposition/verdict**
3. **Test on case with multiple judge assignments**
4. **Test on case with full cost ledger**
5. **Validate PDF downloads for all test cases**

### Success Criteria

- ✅ 100% costs captured when costs tab has data
- ✅ All co-defendants tracked in multi-defendant cases
- ✅ Judge assignment history complete
- ✅ Charge dispositions captured
- ✅ Attorney party affiliation classified
- ✅ Case outcomes structured and parseable
- ✅ Analytics queries can be run on collected data

### Future Enhancements

1. **Machine Learning Integration**
   - Predict case outcomes based on charges, judge, attorney
   - Identify patterns in plea bargains
   - Flag unusual sentencing

2. **Network Analysis**
   - Attorney collaboration networks
   - Judge-attorney interaction patterns
   - Prosecutor assignment patterns

3. **Temporal Analysis**
   - Case processing time trends
   - Judge assignment evolution
   - Attorney career tracking

---

**Created**: 2025-11-16  
**Status**: Planning Phase  
**Next Action**: Implement Phase 1 fixes
