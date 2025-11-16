# 2023 FULL YEAR DOWNLOAD - STATUS & INSTRUCTIONS

## Current Status
- **Improved scraper**: Fixed widget wait logic (15 retries instead of 5)
- **Known case range**: CR-23-684797 to CR-23-684848 (50+ cases)
- **Strategy**: Sequential download starting from 684700, with "both" direction to probe up/down

## To Monitor Progress:
```bash
# Simple file count
ls -1 out/2023/*.json | wc -l

# With details
cd /home/shepov/Documents/Source/PublicDocket/cuyahoga_cp_scraper
python3 monitor_progress.py

# Or watch the log
tail -f 2023_download.log
```

## To Start Fresh Download:
```bash
cd /home/shepov/Documents/Source/PublicDocket/cuyahoga_cp_scraper

# Clean up
rm -rf out/2023/*.json browser_data

# Start download (no limit - will probe until year boundary found)
timeout 7200 python3 main.py scrape --year 2023 --start 684823 --direction up --delay-ms 1000 2>&1 | tee 2023_download_up.log &

# Then start probing downward  
timeout 7200 python3 main.py scrape --year 2023 --start 684823 --direction down --delay-ms 1000 2>&1 | tee 2023_download_down.log &
```

## Expected Coverage
- Based on earlier 654-file download: 50+ unique cases in range 684797-684848
- Cases likely go higher (up to ~685100+) and lower (down to ~684500-)
- Full year probably 200-400+ unique cases

## Cool Progress Bar Command:
```bash
while true; do
  count=$(ls out/2023/*.json 2>/dev/null | wc -l)
  echo "📊 Files: $count  $(date)"
  sleep 10
done
```
