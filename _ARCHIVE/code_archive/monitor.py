#!/usr/bin/env python3
"""Monitor scraper progress in real-time"""
import time
import subprocess
from pathlib import Path

while True:
    try:
        # Get resume position
        resume_file = Path("scrape_677500_707148_PARALLEL_resume.txt")
        if resume_file.exists():
            pos = int(resume_file.read_text().strip())
            start = 677500
            end = 707148
            total = end - start + 1
            done = pos - start
            pct = 100 * done / total
            
            # Get file counts
            files_2023 = len(list(Path("out/2023").glob("*.json")))
            files_2024 = len(list(Path("out/2024").glob("*.json")))
            files_2025 = len(list(Path("out/2025").glob("*.json")))
            total_files = files_2023 + files_2024 + files_2025
            
            # Get last few lines of output
            result = subprocess.run(["tail", "-10", "scraper_output.log"], 
                                  capture_output=True, text=True)
            last_lines = result.stdout.strip().split('\n')[-3:]
            
            print(f"\n{'='*80}")
            print(f"📊 SCRAPER PROGRESS")
            print(f"{'='*80}")
            print(f"Position: {pos:,} / {end:,}")
            print(f"Progress: {pct:.1f}% ({done:,} / {total:,})")
            print(f"Files: 2023={files_2023}, 2024={files_2024}, 2025={files_2025}, Total={total_files}")
            print(f"\nRecent Output:")
            for line in last_lines:
                if line.strip():
                    print(f"  {line}")
        else:
            print("Resume file not found yet...")
        
        time.sleep(10)
    except KeyboardInterrupt:
        print("\nMonitoring stopped")
        break
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)
