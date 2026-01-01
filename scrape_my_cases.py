#!/usr/bin/env python3
"""
Scrape My Specific Cases
Scrapes the predefined list of cases from my_cases.json
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any
import time

def load_cases(config_file: str = "my_cases.json") -> List[Dict[str, Any]]:
    """Load cases from configuration file"""
    config_path = Path(__file__).parent / config_file

    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, 'r') as f:
        config = json.load(f)

    return config.get('cases', [])


def scrape_case(case: Dict[str, Any]) -> bool:
    """Scrape a single case"""
    case_id = case['case_id']
    year = case['year']
    number = case['number']
    download_pdfs = case.get('download_pdfs', False)

    print(f"\n{'='*80}")
    print(f"Scraping: {case_id}")
    print(f"Description: {case.get('description', 'No description')}")
    print(f"Year: {year}, Number: {number}")
    print(f"Download PDFs: {download_pdfs}")
    print(f"{'='*80}\n")

    # Build command
    cmd = [
        "python3", "main.py", "scrape",
        "--year", str(year),
        "--start", str(number),
        "--limit", "1",
        "--headless"
    ]

    if download_pdfs:
        cmd.append("--download-pdfs")

    # Run scraper
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"\n✓ Successfully scraped {case_id}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Failed to scrape {case_id}: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Error scraping {case_id}: {e}")
        return False


def main():
    """Main entry point"""
    print("="*80)
    print("MY CASES SCRAPER")
    print("="*80)

    # Load cases
    cases = load_cases()

    if not cases:
        print("No cases found in configuration file.")
        sys.exit(1)

    print(f"\nFound {len(cases)} case(s) to scrape:")
    for i, case in enumerate(cases, 1):
        print(f"  {i}. {case['case_id']} - {case.get('description', 'No description')}")

    # Scrape each case
    results = []
    for case in cases:
        success = scrape_case(case)
        results.append((case['case_id'], success))

        # Brief delay between cases
        time.sleep(2)

    # Summary
    print("\n" + "="*80)
    print("SCRAPING SUMMARY")
    print("="*80)

    successful = sum(1 for _, success in results if success)
    failed = len(results) - successful

    print(f"\nTotal cases: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    print("\nDetailed results:")
    for case_id, success in results:
        status = "✓" if success else "✗"
        print(f"  {status} {case_id}")

    print("\n" + "="*80)

    # Exit with error code if any failed
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
