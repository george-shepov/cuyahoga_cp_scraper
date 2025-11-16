# QUICK REFERENCE - What To Do Next

## YOU: Run This Command

```bash
python3 main.py scrape --discover-years --output-dir ./out
```

**That's it.** Let it run for 3-4 hours.

---

## WHAT HAPPENS AUTOMATICALLY

1. ✓ Finds all 2025 cases, downloads them
2. ✓ Finds all 2024 cases, downloads them
3. ✓ Finds all 2023 cases, downloads them
4. ✓ Saves to: `out/2025/`, `out/2024/`, `out/2023/`

---

## WHEN IT'S DONE

Tell me:
```
"Download finished, ready for analysis"
```

---

## THEN I'LL RUN

```bash
python3 extraction_enhanced.py
```

And we'll find where those public defenders are! 🔍

---

## YOU CAN MONITOR

While it runs, watch the terminal:
```
[cyan]Processing case 2024-700000...[/cyan]
[green]✓ Completed case 700000 (45.2KB)[/green]
  └─ Attorneys: 2 entries
```

Look for:
- ✓ Cases with attorney data (should see some!)
- ✓ Any error messages
- ✓ Overall progress

---

## IF IT STOPS

Press Ctrl+C and run the same command again:
```bash
python3 main.py scrape --discover-years --output-dir ./out
```

It'll resume from where it left off. ✓

---

## FILES WE'VE PREPARED

| What | Where | Status |
|------|-------|--------|
| Attorney extraction script | `extraction_enhanced.py` | ✓ Ready |
| 2025 analysis | `enhanced_extraction_results.json` | ✓ Done |
| Instructions | `DOWNLOAD_INSTRUCTIONS.md` | ✓ Ready |
| Full summary | `STATUS_SUMMARY.md` | ✓ Ready |

---

**You're good to go!** 🚀

