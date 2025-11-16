# Cuyahoga County Investigation - Multi-Year Expansion Plan

## Phase 1: Data Organization (Immediate)

### Directory Structure Setup

```
out/
├── 2023/              (NEW - to be populated)
├── 2024/              (NEW - to be populated)
├── 2025/              (EXISTING - 530 files, deduped to 443 cases)
```

**Status:** Ready to create

### File Organization Strategy

**Current State:**
- All 530 files in `out/2025/` directory
- Filenames format: `2025-XXXXXX_YYYYMMDD_HHMMSS.json`
- First number (2025) indicates filing year
- Actual data may span multiple years

**Proposed Approach:**
1. Keep 2025 files where they are
2. Create empty `out/2023/` and `out/2024/` directories
3. When downloading 2023/2024 data:
   - Save directly to `out/2023/` and `out/2024/`
   - Use same naming convention (year-based)
   - Script will auto-detect year from glob pattern

**Glob Pattern Ready:** `out/*/202[345]*.json` (already in investigation_v2_deduped.py)

---

## Phase 2: Script Enhancement (Ready to Deploy)

### Current Capabilities

**investigation_v2_deduped.py** already supports:

```python
# Multi-year analysis with filtering
results_2025 = analyze_all_cases(year_filter=2025)
results_2024 = analyze_all_cases(year_filter=2024)
results_2023 = analyze_all_cases(year_filter=2023)

# Combined multi-year
results_all = analyze_all_cases(year_filter=None)  # All years
```

### What's Needed

1. **Directory verification** - Ensure `out/2023/` and `out/2024/` exist before analysis
2. **Year-by-year reporting** - Generate separate JSON results for each year
3. **Comparative analysis** - Identify patterns across years
4. **Deduplication across years** - Handle co-defendants spanning multiple years (if any)

---

## Phase 3: Download Strategy (Planning)

### Download Options

**Option A: Download All at Once** (Recommended)
- Pros: Complete dataset faster, consistent methodology, easier deduplication
- Cons: Large volume initially
- Timeline: 1-2 hours depending on network
- Effort: Low (same scraper code, just different years)

**Option B: Download Incrementally**
- Pros: Manageable data chunks, can validate year-by-year
- Cons: Longer total time, risk of incomplete datasets
- Timeline: 3-4 hours spread over time
- Effort: Medium (need to verify each year completes)

**Recommendation:** **Option A** - Download all years together to ensure comprehensive coverage and consistent data quality

### Download Timeline

If downloading:
1. 2023 data: ~150-200 cases expected (older data, smaller year)
2. 2024 data: ~300-400 cases expected (complete year)
3. 2025 data: 443 unique cases (already deduped)
4. **Total: ~900-1000 cases** for comprehensive analysis

---

## Phase 4: Analysis Roadmap

### Tier 1: Essential (High Priority - After downloads complete)

**4.1 Multi-Year Trend Analysis**
```
- Indictment rate by year (Has it increased/decreased?)
- Racial representation by year (Is disparity growing?)
- Judge concentration by year (Different judges handling different years?)
- Charge types by year (Drug/violence trend?)
```
**Impact:** Identify systemic trends over time
**Effort:** 30 minutes (script modifications)
**Output:** Comparative tables showing year-over-year changes

**4.2 Deduplication Validation Across Years**
```
- Check for co-defendants spanning multiple years
- Validate that co-defendant tracking works across year boundaries
- Compare deduplication ratios (is 16.4% consistent across years?)
```
**Impact:** Ensure data quality maintained
**Effort:** 20 minutes (validation script)
**Output:** Co-defendant statistics by year

**4.3 Attorney Data Extraction** (Currently 0 attorneys in JSON)
```
- Parse html_snapshots["attorneys"] field
- Extract attorney names, firms, PD vs private counsel
- Link to case outcomes
```
**Impact:** Reveal representation patterns (who defends whom?)
**Effort:** 45 minutes (HTML parsing + extraction)
**Output:** Attorney database with 400+ records

---

### Tier 2: Important (Medium Priority - Secondary focus)

**4.4 Judge-Specific Deep Dives**
```
- Conviction rate by judge (who indicts most aggressively?)
- Case processing time by judge (who moves fast vs slow?)
- Racial representation in each judge's docket
```
**Impact:** Identify judicial bias patterns
**Effort:** 60 minutes (judge correlation analysis)
**Output:** Judge performance metrics sorted by racial fairness

**4.5 Charge Disparity Analysis**
```
- Drug charges: Why is racial distribution different?
- Violence charges: Different patterns by race?
- Weapons charges: Enforcement patterns?
```
**Impact:** Understand charging strategy bias
**Effort:** 60 minutes (charge categorization deep-dive)
**Output:** Charge-by-charge racial breakdown

**4.6 Temporal Analysis Enhanced**
```
- Days to indictment by judge (not just overall)
- Temporal patterns by charge type
- Seasonal variations (summer vs winter arrests?)
```
**Impact:** Identify temporal bias mechanisms
**Effort:** 45 minutes (temporal segmentation)
**Output:** Time-based trend analysis

---

### Tier 3: Optional (Lower Priority - Long-term research)

**4.7 Bond Analysis**
```
- Bond amounts by race (equal protection?)
- Bond type (cash, personal, ROR) by defendant characteristics
- Bond violation rates
```
**Effort:** 90 minutes (bond data extraction + analysis)

**4.8 Recidivism Analysis**
```
- Repeat defendants in dataset (if cases span multiple years)
- Charge escalation patterns
- Time between cases
```
**Effort:** 120 minutes (defendant linking across cases)

**4.9 Geographic Analysis**
```
- Arrests by ZIP code
- Correlation with racial demographics by area
- Over-policing patterns by neighborhood
```
**Effort:** 90 minutes (GIS/mapping work)

---

## Phase 5: Implementation Checklist

### Pre-Download Tasks

- [ ] Create `out/2023/` directory
- [ ] Create `out/2024/` directory
- [ ] Verify script can find files in all three year directories
- [ ] Test `year_filter` parameter with existing 2025 data

### Download Phase

- [ ] Download 2023 cases (target: ~150-200 files)
- [ ] Download 2024 cases (target: ~300-400 files)
- [ ] Verify files landed in correct directories
- [ ] Quick spot-check: Open 1-2 files from each year to verify structure

### Post-Download Tasks

- [ ] Run deduplication on 2023 files
- [ ] Run deduplication on 2024 files
- [ ] Generate year-specific results JSON
- [ ] Compare deduplication ratios across years
- [ ] Generate comparative analysis report

### Analysis Phase

- [ ] Extract attorney data from all years
- [ ] Run judge-specific analysis per year
- [ ] Generate trend analysis (2023 → 2024 → 2025)
- [ ] Create executive summary comparing years

---

## Phase 6: Expected Findings

### Hypotheses to Test

1. **Systemic Pattern Consistency**
   - Is 84% indictment rate consistent across years?
   - Is ~61% Black defendant representation consistent?
   - Hypothesis: Pattern is structural, not anomalous to 2025

2. **Temporal Trends**
   - Has indictment factory pattern worsened over time?
   - Have racial disparities grown/shrunk?
   - Are judge assignments changing?
   - Hypothesis: Disparities likely increasing (systemic)

3. **Judge Rotation**
   - Do same judges appear across years?
   - Is ARRAIGNMENT ROOM always 66% of cases?
   - Do individual judges maintain consistent conviction rates?
   - Hypothesis: Concentration in ARRAIGNMENT ROOM is structural

4. **Charge Evolution**
   - Have drug charges increased as % of total?
   - Do violent crime charges stay consistent?
   - Hypothesis: Drug war enforcement increasing

---

## Files Ready to Use

### Scripts

1. **investigation_v2_deduped.py**
   - ✓ Already supports `year_filter` parameter
   - ✓ Already finds files across directories: `out/*/202[345]*.json`
   - ✓ Ready to run on multi-year data without modification

2. **Enhanced version needed**
   - Multi-year comparative reporting
   - Year-over-year trend analysis
   - Consolidated executive summary

### Next Script to Create

**investigation_v3_multiyear.py**
```python
# Proposed features:
- Generate separate JSON for each year
- Comparative statistics (year-over-year changes)
- Trend analysis (3-year arc)
- Attorney extraction from html_snapshots
- Judge-specific metrics by year
```

---

## Immediate Next Steps

1. **Create directories**
   ```bash
   mkdir -p out/2023
   mkdir -p out/2024
   ```

2. **Verify script readiness**
   ```bash
   python3 investigation_v2_deduped.py
   # Should work with current 2025 data
   ```

3. **Plan download timing**
   - Set aside 2-3 hours for download
   - Best time: Off-peak hours (evening/weekend)
   - Use case docket filters if available

4. **Prepare attorney extraction**
   - Design HTML parser for html_snapshots
   - Test on 10-20 cases
   - Refine extraction logic

---

## Success Metrics

After multi-year expansion, we should have:

✓ **Data Coverage:** 900-1000 unique cases across 3 years
✓ **Data Quality:** Consistent deduplication ratio (~15-20% co-defendants)
✓ **Temporal Pattern:** Clear 2023 → 2024 → 2025 trend
✓ **Systemic Bias Confirmation:** Same patterns across all years
✓ **Attorney Database:** 400+ attorney records with representation type
✓ **Judge Metrics:** Individual judge performance scored by fairness
✓ **Constitutional Concerns:** Multiple supporting evidence points

---

## Questions for User

Before proceeding with downloads, please clarify:

1. **Download Timing:** When should we download 2023/2024 data?
2. **Attorney Focus:** High priority to extract attorney names/firms?
3. **Judge Deep-Dive:** Focus on comparing judges across years?
4. **Report Format:** What format for final multi-year report? (PDF, HTML, markdown?)
5. **Data Scope:** Any constraints on how far back (2020?) or other years?

---

Generated: 2025-01-09  
Status: **READY FOR NEXT PHASE**
