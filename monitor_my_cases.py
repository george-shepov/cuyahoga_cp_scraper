#!/usr/bin/env python3
"""
Automated Case Monitoring & Print Version Scraper
Monitors your court cases, saves print versions (HTML + PDF), detects changes
Runs frequently to catch updates as they happen
"""
import asyncio
import json
import hashlib
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from playwright.async_api import async_playwright, Page, Browser

# Configuration
BASE_URL = "https://cpdocket.cp.cuyahogacounty.us"
CASES_DIR = Path("/home/shepov/Documents/2- Cuyahoga County Court")
CHECK_INTERVAL_SECONDS = 300  # 5 minutes default
RAPID_CHECK_SECONDS = 60      # 1 minute when changes detected


class CaseMonitor:
    """Monitors court cases for changes"""

    def __init__(self, case_id: str, case_type: str):
        self.case_id = case_id
        self.case_type = case_type  # "CRIMINAL" or "DOMESTIC"
        self.case_dir = CASES_DIR / case_id
        self.changes_detected = False
        self.last_hashes = {}

        # Create case directory structure
        self.tabs = self._get_tabs_for_case_type()
        for tab in self.tabs:
            (self.case_dir / tab).mkdir(parents=True, exist_ok=True)

    def _get_tabs_for_case_type(self) -> List[str]:
        """Get tab names based on case type"""
        if self.case_type == "CRIMINAL":
            return [
                "Case Summary",
                "Defendant",
                "Documents",
                "Docket",
                "Cost",
                "Attorney"
            ]
        elif self.case_type == "DOMESTIC":
            return [
                "Case Summary",
                "Parties",
                "Documents",
                "Image",
                "Docket",
                "Service",
                "Costs",
                "All"
            ]
        else:
            return ["Case Summary", "Docket"]

    def _compute_file_hash(self, content: bytes) -> str:
        """Compute SHA256 hash of content"""
        return hashlib.sha256(content).hexdigest()

    def _load_last_hash(self, tab_name: str) -> Optional[str]:
        """Load last saved hash for a tab"""
        hash_file = self.case_dir / tab_name / ".last_hash"
        if hash_file.exists():
            return hash_file.read_text().strip()
        return None

    def _save_hash(self, tab_name: str, content_hash: str):
        """Save hash for a tab"""
        hash_file = self.case_dir / tab_name / ".last_hash"
        hash_file.write_text(content_hash)

    def _should_save_file(self, tab_name: str, content: bytes) -> bool:
        """Check if content has changed and should be saved"""
        current_hash = self._compute_file_hash(content)
        last_hash = self._load_last_hash(tab_name)

        if last_hash is None or current_hash != last_hash:
            self._save_hash(tab_name, current_hash)
            return True
        return False

    def _get_timestamp_prefix(self) -> str:
        """Get timestamp prefix for filenames"""
        return datetime.now().strftime("%m-%d-%Y")

    async def save_page_as_html(self, page: Page, tab_name: str) -> Optional[Path]:
        """Save page HTML if changed"""
        try:
            content = await page.content()
            content_bytes = content.encode('utf-8')

            if not self._should_save_file(tab_name, content_bytes):
                print(f"  ↔ {tab_name}: No changes detected")
                return None

            timestamp = self._get_timestamp_prefix()
            page_title = await page.title()
            filename = f"{timestamp} {page_title}.html"
            filepath = self.case_dir / tab_name / filename

            filepath.write_text(content)
            print(f"  ✓ {tab_name}: Saved HTML ({len(content_bytes)} bytes)")
            self.changes_detected = True
            return filepath

        except Exception as e:
            print(f"  ✗ {tab_name}: Error saving HTML: {e}")
            return None

    async def save_page_as_pdf(self, page: Page, tab_name: str) -> Optional[Path]:
        """Save page as PDF if changed"""
        try:
            # Generate PDF
            pdf_bytes = await page.pdf(
                format='Letter',
                print_background=True,
                margin={'top': '0.5in', 'right': '0.5in', 'bottom': '0.5in', 'left': '0.5in'}
            )

            if not self._should_save_file(tab_name + "_PDF", pdf_bytes):
                print(f"  ↔ {tab_name}: No PDF changes detected")
                return None

            timestamp = self._get_timestamp_prefix()
            page_title = await page.title()
            filename = f"{timestamp} {page_title}.pdf"
            filepath = self.case_dir / tab_name / filename

            filepath.write_bytes(pdf_bytes)
            print(f"  ✓ {tab_name}: Saved PDF ({len(pdf_bytes)} bytes)")
            self.changes_detected = True
            return filepath

        except Exception as e:
            print(f"  ✗ {tab_name}: Error saving PDF: {e}")
            return None


async def check_for_tos(page: Page) -> bool:
    """Check if we're on the TOS page"""
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
        url = page.url
        html = await page.content()
        return "TOS.aspx" in url or "Site Terms of Service" in html or "Clerk of Courts Site Terms" in html
    except:
        return False


async def accept_tos_if_present(page: Page):
    """Accept TOS if we're on that page"""
    max_attempts = 3

    for attempt in range(max_attempts):
        if not await check_for_tos(page):
            return  # Not on TOS page, we're good

        print(f"  📋 TOS page detected (attempt {attempt + 1}/{max_attempts}), accepting...")

        # Try different button selectors - most specific first
        selectors = [
            "#SheetContentPlaceHolder_btnYes",  # Exact ID from the page
            "input[id*='btnYes']",
            "input[name*='btnYes']",
            "input[type='submit'][value='Yes']",
            "button:has-text('Yes')",
            "a:has-text('I Agree')",
            "button:has-text('Agree')",
        ]

        clicked = False
        for selector in selectors:
            try:
                locator = page.locator(selector)
                count = await locator.count()
                print(f"    Trying selector '{selector}' - found {count} elements")

                if count > 0:
                    print(f"    Clicking '{selector}'...")
                    # Don't wait for navigation - just click and then check
                    await locator.first.click()
                    await asyncio.sleep(2)  # Wait for navigation
                    clicked = True
                    print("  ✓ TOS button clicked")
                    break
            except Exception as e:
                print(f"    ✗ Failed with '{selector}': {e}")
                continue

        if not clicked:
            print("  ⚠ Could not find TOS accept button")
            # Save debug HTML
            html = await page.content()
            debug_file = Path("/tmp/tos_debug.html")
            debug_file.write_text(html)
            print(f"  Debug HTML saved to {debug_file}")
            return

        await page.wait_for_load_state("networkidle", timeout=10000)

    if await check_for_tos(page):
        raise RuntimeError("Still on TOS page after multiple attempts")


async def navigate_to_case(page: Page, case_id: str, case_type: str):
    """Navigate to a specific case"""
    # Go to search page
    await page.goto(f"{BASE_URL}/Search.aspx", wait_until="networkidle", timeout=30000)

    # Check for and handle TOS
    await accept_tos_if_present(page)

    # Small delay to be respectful
    await asyncio.sleep(0.5)

    # Select case type radio button
    if case_type == "CRIMINAL":
        radio_selector = "#SheetContentPlaceHolder_rbCrCase"
    elif case_type == "DOMESTIC":
        # Domestic cases not available online anymore
        print("  ⚠ Domestic cases are not available online")
        print("  Per Federal Law, Domestic Violence cases are blocked from internet access")
        raise ValueError("Domestic cases not accessible via web")
    else:
        raise ValueError(f"Unknown case type: {case_type}")

    print(f"  Clicking radio button for {case_type} search...")
    # Click radio button and wait for postback to complete
    async with page.expect_navigation(timeout=15000):
        await page.click(radio_selector)

    print("  ✓ Radio button selected, form loaded")
    await asyncio.sleep(0.5)  # Brief pause after form loads

    # Parse case ID (e.g., "CR-23-684826-A" -> year=2023, number=684826)
    parts = case_id.split('-')
    year_short = parts[1]  # "23"
    year_full = "20" + year_short if len(year_short) == 2 else year_short
    case_number = parts[2]  # "684826"

    # Fill in search form
    await page.select_option("select[name*='ddlCaseYear']", year_full)
    await asyncio.sleep(0.3)  # Brief pause between actions
    await page.fill("input[name*='txtCaseNum']", case_number)
    await asyncio.sleep(0.3)  # Brief pause before submit
    await page.click("input[type='submit'][value='Search']")
    await page.wait_for_load_state("networkidle", timeout=15000)

    # Check for TOS after search (sometimes redirects)
    await accept_tos_if_present(page)


async def click_tab(page: Page, tab_name: str):
    """Click a specific tab on the case page"""
    try:
        # Small delay before clicking tab to be respectful
        await asyncio.sleep(0.5)

        # Tab link patterns
        tab_selectors = {
            "Case Summary": "a[href*='Summary']",
            "Defendant": "a[href*='Defendant']",
            "Parties": "a[href*='Parties']",
            "Documents": "a[href*='Documents']",
            "Image": "a[href*='Image']",
            "Docket": "a[href*='Docket']",
            "Service": "a[href*='Service']",
            "Cost": "a[href*='Cost']",
            "Costs": "a[href*='Cost']",
            "Attorney": "a[href*='Attorney']",
            "All": "a[href*='All']"
        }

        selector = tab_selectors.get(tab_name)
        if not selector:
            print(f"  ⚠ Unknown tab: {tab_name}")
            return False

        await page.click(selector)
        await page.wait_for_load_state("networkidle", timeout=10000)

        # Check for TOS after clicking tab (can happen randomly)
        await accept_tos_if_present(page)

        return True

    except Exception as e:
        print(f"  ✗ Error clicking tab {tab_name}: {e}")
        return False


async def monitor_case(browser: Browser, case_id: str, case_type: str):
    """Monitor a single case and save all tabs"""
    print(f"\n{'='*80}")
    print(f"Monitoring: {case_id} ({case_type})")
    print(f"{'='*80}")

    monitor = CaseMonitor(case_id, case_type)
    page = await browser.new_page()

    try:
        # Navigate to the case
        await navigate_to_case(page, case_id, case_type)

        # Process each tab
        for tab_name in monitor.tabs:
            print(f"\n{tab_name}:")

            # Click tab
            if not await click_tab(page, tab_name):
                continue

            # Wait a bit for content to load
            await asyncio.sleep(1)

            # Save HTML
            await monitor.save_page_as_html(page, tab_name)

            # Save PDF
            await monitor.save_page_as_pdf(page, tab_name)

        print(f"\n{'='*80}")
        if monitor.changes_detected:
            print(f"✅ CHANGES DETECTED in {case_id}")
        else:
            print(f"⚪ No changes in {case_id}")
        print(f"{'='*80}")

        return monitor.changes_detected

    except Exception as e:
        print(f"\n✗ Error monitoring {case_id}: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await page.close()


async def monitor_all_cases(cases: List[Dict[str, Any]], continuous: bool = False):
    """Monitor all configured cases"""
    async with async_playwright() as p:
        # Run headless when in background, with display when interactive
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )

        try:
            iteration = 0
            consecutive_errors = 0
            max_consecutive_errors = 3

            while True:
                iteration += 1
                print(f"\n\n{'#'*80}")
                print(f"# MONITORING ITERATION #{iteration}")
                print(f"# Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"# Cases: {len(cases)}")
                print(f"{'#'*80}\n")

                any_changes = False
                iteration_had_errors = False

                for case in cases:
                    case_id = case['case_id']
                    case_type = case['case_type']

                    try:
                        changes = await monitor_case(browser, case_id, case_type)
                        any_changes = any_changes or changes
                    except Exception as e:
                        print(f"\n⚠ Error processing {case_id}: {e}")
                        iteration_had_errors = True
                        # Don't continue to next case immediately after error
                        await asyncio.sleep(5)  # Wait 5 seconds before next case

                    # Brief delay between cases to be respectful
                    await asyncio.sleep(2)

                # Track consecutive errors to avoid hammering server
                if iteration_had_errors:
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        backoff_time = 60 * consecutive_errors  # Increase wait time
                        print(f"\n⚠ Multiple consecutive errors ({consecutive_errors})")
                        print(f"   Backing off for {backoff_time} seconds to be respectful...")
                        await asyncio.sleep(backoff_time)
                else:
                    consecutive_errors = 0  # Reset on success

                if not continuous:
                    break

                # Adjust check interval based on whether changes were detected
                if any_changes:
                    interval = RAPID_CHECK_SECONDS
                    print(f"\n⚡ Changes detected! Checking again in {interval} seconds...")
                else:
                    interval = CHECK_INTERVAL_SECONDS
                    print(f"\n⏰ No changes. Next check in {interval} seconds...")

                await asyncio.sleep(interval)

        finally:
            await browser.close()


def main():
    """Main entry point"""
    import argparse

    global CHECK_INTERVAL_SECONDS, RAPID_CHECK_SECONDS

    parser = argparse.ArgumentParser(description="Monitor court cases for changes")
    parser.add_argument("--continuous", "-c", action="store_true",
                       help="Run continuously (default: single check)")
    parser.add_argument("--interval", "-i", type=int, default=CHECK_INTERVAL_SECONDS,
                       help=f"Check interval in seconds (default: {CHECK_INTERVAL_SECONDS})")
    parser.add_argument("--rapid", "-r", type=int, default=RAPID_CHECK_SECONDS,
                       help=f"Rapid check interval when changes detected (default: {RAPID_CHECK_SECONDS})")

    args = parser.parse_args()

    CHECK_INTERVAL_SECONDS = args.interval
    RAPID_CHECK_SECONDS = args.rapid

    # Load cases from my_cases.json
    config_file = Path(__file__).parent / "my_cases.json"
    with open(config_file, 'r') as f:
        config = json.load(f)

    # Convert case format
    cases = []
    for case in config['cases']:
        case_id = case['case_id']
        # Determine case type from prefix
        if case_id.startswith('CR-'):
            case_type = "CRIMINAL"
        elif case_id.startswith('DR-'):
            case_type = "DOMESTIC"
        else:
            case_type = "UNKNOWN"

        cases.append({
            'case_id': case_id,
            'case_type': case_type
        })

    # Add domestic case
    cases.append({
        'case_id': 'DR-25-403973',
        'case_type': 'DOMESTIC'
    })

    print(f"{'='*80}")
    print(f"CASE MONITORING SYSTEM")
    print(f"{'='*80}")
    print(f"Mode: {'CONTINUOUS' if args.continuous else 'SINGLE CHECK'}")
    print(f"Cases to monitor: {len(cases)}")
    for case in cases:
        print(f"  - {case['case_id']} ({case['case_type']})")
    print(f"Check interval: {CHECK_INTERVAL_SECONDS}s")
    print(f"Rapid interval: {RAPID_CHECK_SECONDS}s")
    print(f"Output directory: {CASES_DIR}")
    print(f"{'='*80}\n")

    # Run monitoring
    asyncio.run(monitor_all_cases(cases, continuous=args.continuous))


if __name__ == "__main__":
    main()
