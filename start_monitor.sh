#!/bin/bash
# Start the case monitoring system

cd /home/shepov/dev/scrapers/criminal/cuyahoga_cp_scraper

echo "================================================================================================"
echo "CASE MONITORING SYSTEM - STARTING"
echo "================================================================================================"
echo ""
echo "This will monitor your cases continuously and save print versions when changes are detected."
echo ""
echo "Options:"
echo "  1. Single check (run once and exit)"
echo "  2. Continuous monitoring (check every 5 minutes, faster when changes detected)"
echo "  3. Rapid monitoring (check every 1 minute)"
echo ""

read -p "Choose mode (1/2/3): " mode

case $mode in
    1)
        echo "Running single check..."
        python3 monitor_my_cases.py
        ;;
    2)
        echo "Starting continuous monitoring (5 min interval)..."
        python3 monitor_my_cases.py --continuous
        ;;
    3)
        echo "Starting rapid monitoring (1 min interval)..."
        python3 monitor_my_cases.py --continuous --interval 60 --rapid 30
        ;;
    *)
        echo "Invalid option. Running single check..."
        python3 monitor_my_cases.py
        ;;
esac
