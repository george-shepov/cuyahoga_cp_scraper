#!/bin/bash
# Monitor the parallel scraper progress

while true; do
    clear
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║         PARALLEL SCRAPER PROGRESS MONITOR                      ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Current position
    if [ -f scrape_677500_707148_PARALLEL_resume.txt ]; then
        POS=$(cat scrape_677500_707148_PARALLEL_resume.txt)
        echo "📍 Current Position: Case $POS / 707148"
        PROGRESS=$((100 * (POS - 677500) / (707148 - 677500)))
        echo "📊 Progress: $PROGRESS%"
    else
        echo "📍 Starting..."
    fi
    
    echo ""
    echo "📁 Files on Disk:"
    for YEAR in 2023 2024 2025; do
        COUNT=$(find out/$YEAR -name "*.json" -type f 2>/dev/null | wc -l)
        echo "  $YEAR: $COUNT files"
    done
    
    TOTAL=$(find out -name "*.json" -type f 2>/dev/null | wc -l)
    echo "  TOTAL: $TOTAL files"
    
    echo ""
    echo "⏱️  Recently Created (last 5 min):"
    RECENT=$(find out -name "*.json" -type f -mmin -5 | wc -l)
    echo "  $RECENT files"
    
    echo ""
    echo "📋 Last 8 lines of log:"
    tail -8 scraper.log
    
    echo ""
    echo "🔄 Refreshing in 10 seconds... (Press Ctrl+C to exit)"
    sleep 10
done
