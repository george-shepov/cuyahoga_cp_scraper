#!/usr/bin/env python3
"""Quick test of monitor navigation"""
import asyncio
from playwright.async_playwright import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            print("1. Going to Search page...")
            await page.goto("https://cpdocket.cp.cuyahogacounty.gov/Search.aspx",
                          wait_until="networkidle", timeout=30000)

            print("2. Checking for TOS...")
            url = page.url
            if "TOS.aspx" in url:
                print("   On TOS page, clicking Yes button...")
                await page.click("#SheetContentPlaceHolder_btnYes")
                await asyncio.sleep(2)
                print(f"   After TOS click, URL: {page.url}")

            print("3. Clicking CRIMINAL SEARCH BY CASE radio button...")
            print(f"   Current URL: {page.url}")

            # Wait for navigation after clicking radio button
            async with page.expect_navigation(timeout=15000):
                await page.click("#SheetContentPlaceHolder_rbCrCase")

            print(f"   After radio click, URL: {page.url}")

            print("4. Filling in case search form...")
            await asyncio.sleep(1)

            # Fill year and case number
            await page.select_option("select[name*='ddlCaseYear']", "2023")
            await asyncio.sleep(0.5)

            await page.fill("input[name*='txtCaseNum']", "684826")
            await asyncio.sleep(0.5)

            print("5. Clicking Search button...")
            await page.click("input[type='submit'][value='Search']")
            await page.wait_for_load_state("networkidle", timeout=15000)

            print(f"6. Final URL: {page.url}")
            print("✓ Test completed!")

            await asyncio.sleep(5)  # Keep browser open for a bit

        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test())
