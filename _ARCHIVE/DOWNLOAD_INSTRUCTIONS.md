# DOWNLOAD 2023 & 2024 DATA - Instructions

## Quick Start

You have two options:

### OPTION 1: Fast (Auto-Discover Year Ranges)
```bash
# This will automatically discover all cases for 2025, 2024, 2023
# Then download them all
python3 main.py scrape --discover-years --output-dir ./out
```

**Time:** ~3-4 hours total (1+ hour per year)  
**Result:** `out/2023/`, `out/2024/`, `out/2025/` filled with *.json files

### OPTION 2: Manual Control (2023 Only)
```bash
# Just download 2023 data
python3 main.py scrape --year 2023 --start 684826 --limit 400 --direction both --output-dir ./out
```

**Time:** ~1-2 hours  
**Result:** `out/2023/` with ~400 case files

---

## What Each Option Does

### --discover-years
- ✓ Finds the start and end case numbers for each year automatically
- ✓ Probes backward/forward to find case boundaries
- ✓ Processes ALL cases in each year (not just a sample)
- ✓ More comprehensive but slower

**Recommended if:** You want ALL cases for multi-year comparison

### --year 2023 --start 684826 --limit 400
- ✓ Manually targets year 2023
- ✓ Starts at case number 684826 (reference point)
- ✓ Searches both up and down 200 cases (--direction both)
- ✓ Faster, can run multiple times with different ranges

**Recommended if:** You want to control what gets downloaded

---

## Expected Results

### After Download Completes

Directory structure:
```
out/
├── 2025/          (already have ~530 cases)
│   ├── 2025-706402_*.json
│   ├── 2025-706403_*.json
│   └── ...
├── 2024/          (NEW ~300-400 cases)
│   ├── 2024-700000_*.json
│   ├── 2024-700001_*.json
│   └── ...
└── 2023/          (NEW ~150-200 cases)
    ├── 2023-684826_*.json
    ├── 2023-684827_*.json
    └── ...
```

### What We'll Do After

```bash
# Run enhanced extraction on all 3 years
python3 extraction_enhanced.py

# Generates:
# - 2023_attorneys_results.json
# - 2024_attorneys_results.json
# - 2025_attorneys_results.json (already have)

# Then analyze attorney patterns across years
```

---

## Monitoring Download Progress

While it's running, you'll see:
```
[cyan]Processing case 2024-700000...[/cyan]
[green]✓ Completed case 700000 (45.2KB)[/green]
  └─ Summary: 28 fields | Docket: 12 entries | Costs: 8 entries | Defendant: 15 fields | Attorneys: 2 entries

[cyan]Processing case 2024-700001...[/cyan]
...
```

### Key Info to Watch For:
- **Attorneys: X entries** - How many attorneys found in that case
- **Size (KB)** - File size (larger = more data)
- **Errors section** - If any extraction failed

---

## If Download Gets Interrupted

Both options support resuming:

```bash
# Auto-discover mode resume
python3 main.py scrape --discover-years --output-dir ./out
# ^ Automatically resumes from last completed case

# Manual mode resume (automatic too)
python3 main.py scrape --year 2023 --start 684826 --limit 400 --output-dir ./out
# ^ Checks .last_number file in out/2023/
```

---

## My Recommendation

**START WITH THIS:**
```bash
python3 main.py scrape --discover-years --output-dir ./out
```

**Why:**
- Gets ALL cases for each year (not just a sample)
- Automatic discovery means no guessing on ranges
- Once done, we have complete 3-year dataset
- Perfect for finding those public defenders you mentioned

**Expected runtime:** 3-4 hours (depends on internet speed & server delays)

---

## Next Steps After Download

Once download finishes:

1. **Tell me:** "2023, 2024 data downloaded"
2. **I'll run:** `python3 extraction_enhanced.py`
3. **We'll get:** Comparative attorney statistics across all 3 years
4. **Then analyze:** Where are the public defenders? Why not in 2025?

---

## Questions?

- **How long does it take per case?** ~5-10 seconds (includes 1.25s server delay per case)
- **Can I cancel mid-download?** Yes - just Ctrl+C. It'll resume where you left off
- **Will it overwrite existing 2025 data?** No - safe to run, uses separate files per case
- **How much disk space needed?** ~200-300MB total for all 3 years

