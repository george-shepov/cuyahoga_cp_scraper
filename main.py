
import asyncio, json, os, re, time, argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import aiohttp
import aiofiles

from pydantic import BaseModel, field_validator
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from tenacity import retry, stop_after_attempt, wait_fixed

from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout

# Try to import statistics and dashboard modules
try:
    from statistics import generate_yearly_report, CaseDataAnalyzer
    from dashboard import generate_html_dashboard
except ImportError:
    generate_yearly_report = None
    CaseDataAnalyzer = None
    generate_html_dashboard = None

BASE_URL = os.getenv("BASE_URL", "https://cpdocket.cp.cuyahogacounty.gov")

# Optional: toned-down delays by default
DEFAULT_DELAY = max(300, int(os.getenv("DELAY_MS", "800")))  # 0.3–0.8s polite delay

console = Console()

class Cfg(BaseModel):
    headless: bool = False if os.getenv("HEADLESS", "false").lower() == "false" else True
    case_category: str = os.getenv("CASE_CATEGORY", "CRIMINAL")
    year: int = int(os.getenv("YEAR", "2025"))
    start_number: int = int(os.getenv("START_NUMBER", "706402"))
    direction: str = os.getenv("DIRECTION", "both")  # up|down|both
    limit: int = int(os.getenv("LIMIT", "100"))
    delay_ms: int = int(os.getenv("DELAY_MS", "1250"))
    output_dir: str = os.getenv("OUTPUT_DIR", "./out")
    resume: bool = False
    download_pdfs: bool = False if os.getenv("DOWNLOAD_PDFS", "false").lower() == "false" else True
    pdf_cases: List[str] = []  # Specific cases to download PDFs for

    @field_validator("direction")
    @classmethod
    def _dir(cls, v):
        if v not in {"up", "down", "both"}:
            raise ValueError("direction must be up|down|both")
        return v

async def kv_from_table(page: Page, table_selector: str) -> Dict[str, Any]:
    data = {}
    rows = page.locator(f"{table_selector} tr")
    count = await rows.count()
    for i in range(count):
        cells = rows.nth(i).locator("td")
        if await cells.count() >= 2:
            k_text = await cells.nth(0).inner_text()
            v_text = await cells.nth(1).inner_text()
            k = k_text.strip()
            v = v_text.strip()
            if k:
                data[k] = v
    return data
async def grid_from_table(page: Page, table_selector: str) -> List[Dict[str, Any]]:
    out = []
    headers = []
    thead = page.locator(f"{table_selector} thead tr th")
    if await thead.count() == 0:
        thead = page.locator(f"{table_selector} tr").first.locator("th")
    for i in range(await thead.count()):
        header_text = await thead.nth(i).inner_text()
        headers.append(header_text.strip() or f"col{i+1}")
    rows = page.locator(f"{table_selector} tbody tr")
    if await rows.count() == 0:
        rows = page.locator(f"{table_selector} tr").locator("xpath=./following-sibling::tr")
    for r in range(await rows.count()):
        row = rows.nth(r)
        cols = row.locator("td")
        rec = {}
        for c in range(await cols.count()):
            key = headers[c] if c < len(headers) else f"col{c+1}"
            cell_text = await cols.nth(c).inner_text()
            rec[key] = cell_text.strip()
        if rec:
            out.append(rec)
    return out


async def check_current_page(page: Page) -> str:
    """Check what page we're currently on and return the page type"""
    await page.wait_for_load_state("domcontentloaded", timeout=10000)
    url = page.url
    html = await page.content()
    
    console.print(f"[blue]Current URL: {url}[/blue]")
    
    if "TOS.aspx" in url or "Site Terms of Service" in html or "Clerk of Courts Site Terms" in html:
        return "tos"
    elif "Search.aspx" in url:
        if "CRIMINAL SEARCH BY CASE" in html:
            return "search"
        else:
            return "search_initial"  # Search page but need to select criminal
    elif "CR_CaseInformation" in url:
        return "case_info"
    elif "error" in html.lower() or "no cases found" in html.lower():
        return "error"
    else:
        return "unknown"

async def ensure_past_tos(page: Page):
    """Ensure we get past the TOS page - keep trying until we're not on TOS"""
    max_attempts = 5
    for attempt in range(max_attempts):
        page_type = await check_current_page(page)
        
        if page_type != "tos":
            console.print(f"[green]Successfully past TOS, on page type: {page_type}[/green]")
            return
            
        console.print(f"[magenta]On TOS page (attempt {attempt + 1}/{max_attempts}) - accepting terms…[/magenta]")
        html = await page.content()
        
        selectors = [
            "input[name*='btnYes']",  # The exact TOS button
            "input[type='submit'][value='Yes']",
            "a:has-text('I Agree')", "a:has-text('Agree')", "a:has-text('Continue')",
            "button:has-text('I Agree')", "button:has-text('Agree')", "button:has-text('Continue')",
            "input[type='submit'][value*='Agree']",
            "input[type='submit'][value*='Continue']",
        ]
        
        clicked = False
        for sel in selectors:
            loc = page.locator(sel)
            if await loc.count() > 0:
                try:
                    console.print(f"[green]Found TOS button: {sel}[/green]")
                    # Wait for navigation to complete after clicking
                    async with page.expect_navigation(timeout=15000):
                        await loc.first.click()
                    clicked = True
                    console.print("[green]TOS button clicked and navigation completed[/green]")
                    break
                except Exception as e:
                    console.print(f"[yellow]Failed to click {sel}: {e}[/yellow]")
                    continue
        
        if not clicked:
            console.print("[red]Could not find an Accept/Continue control on TOS page.[/red]")
            (Path("out") / "debug_tos.html").write_text(html, encoding="utf-8")
            raise RuntimeError("Stuck on TOS page; manual intervention required.")
        
        # Wait a bit before checking again
        await page.wait_for_load_state("networkidle", timeout=10000)
    
    # If we get here, we failed to get past TOS
    raise RuntimeError(f"Failed to get past TOS page after {max_attempts} attempts")

async def accept_terms_if_present(page: Page):
    """Legacy function - now just calls ensure_past_tos"""
    await ensure_past_tos(page)

async def navigate_to_search(page: Page):
    """Navigate to search page with comprehensive page checking"""
    max_attempts = 5
    
    for attempt in range(max_attempts):
        console.print(f"[yellow]Navigating to Search.aspx (attempt {attempt + 1}/{max_attempts})…[/yellow]")
        
        try:
            await page.goto(f"{BASE_URL}/Search.aspx", wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            console.print(f"[red]Failed to navigate: {e}[/red]")
            continue
        
        # Check what page we landed on
        page_type = await check_current_page(page)
        
        if page_type == "tos":
            console.print("[magenta]Landed on TOS page - handling…[/magenta]")
            await ensure_past_tos(page)
            # After TOS, try to go to search again
            await page.goto(f"{BASE_URL}/Search.aspx", wait_until="domcontentloaded", timeout=30000)
            page_type = await check_current_page(page)
        
        if page_type in ["search", "search_initial"]:
            console.print("[green]Successfully reached Search.aspx[/green]")
            break
        else:
            console.print(f"[red]Not on search page, got page type: {page_type}[/red]")
            if attempt == max_attempts - 1:
                raise RuntimeError(f"Cannot reach Search.aspx after {max_attempts} attempts. Final page type: {page_type}")
            continue

    # Now ensure we're on the criminal search form
    console.print("[yellow]Selecting: CRIMINAL SEARCH BY CASE…[/yellow]")
    
    # Always try to select criminal search - check if the radio button exists
    rb = page.locator("#SheetContentPlaceHolder_rbCrCase")
    rb_count = await rb.count()
    console.print(f"[blue]Found {rb_count} criminal search radio buttons[/blue]")
    
    if rb_count > 0:
        # Try to click/select the criminal radio button
        try:
            console.print("[green]Clicking criminal search radio button[/green]")
            # Use the JavaScript click handler that's on the element
            await page.evaluate("""
                () => {
                  const rb = document.querySelector('#SheetContentPlaceHolder_rbCrCase');
                  if (rb) { 
                    rb.checked = true; 
                    rb.click(); // This should trigger the postback
                  }
                }
            """)
            
            # Wait for the postback to complete
            await page.wait_for_load_state("networkidle", timeout=10000)
            console.print("[green]Criminal search radio button activated[/green]")
            
        except Exception as e:
            console.print(f"[yellow]Failed to click radio button: {e}[/yellow]")
            # Fallback: try direct postback
            await page.evaluate("""
                () => {
                  const rb = document.querySelector('#SheetContentPlaceHolder_rbCrCase');
                  if (rb && window.__doPostBack) { 
                    rb.checked = true; 
                    __doPostBack('ctl00$SheetContentPlaceHolder$rbCrCase','');
                  }
                }
            """)
            await page.wait_for_load_state("networkidle", timeout=10000)

        # Wait for UpdatePanel to expose widgets (retry a few times)
        widgets_ok = False
        for attempt in range(5):
            try:
                console.print(f"[blue]Checking for form widgets (attempt {attempt + 1})...[/blue]")
                year_select = page.locator("select[name*='ddlCaseYear']")
                case_input = page.locator("input[name*='txtCaseNum']")
                
                year_count = await year_select.count()
                case_count = await case_input.count()
                
                console.print(f"[blue]Year select: {year_count}, Case input: {case_count}[/blue]")
                
                if year_count > 0 and case_count > 0:
                    widgets_ok = True
                    break
                else:
                    await page.wait_for_load_state("networkidle", timeout=3000)
                    # Check if we got redirected back to TOS
                    if await check_current_page(page) == "tos":
                        console.print("[magenta]Redirected back to TOS during form setup![/magenta]")
                        await ensure_past_tos(page)
                        return  # Start over
                        
            except Exception as e:
                console.print(f"[yellow]Widget check failed: {e}[/yellow]")
                await page.wait_for_load_state("networkidle", timeout=3000)

        if not widgets_ok:
            current_html = await page.content()
            (Path("out")/"debug_search_no_widgets.html").write_text(current_html, encoding="utf-8")
            console.print("[red]Search widgets not visible after selecting 'CRIMINAL SEARCH BY CASE'.[/red]")
            console.print("[blue]Saved current page state to debug_search_no_widgets.html[/blue]")
            raise RuntimeError("Search widgets not visible after selecting 'CRIMINAL SEARCH BY CASE'.")
    else:
        console.print("[red]No criminal search radio button found![/red]")
        current_html = await page.content()
        (Path("out")/"debug_no_radio.html").write_text(current_html, encoding="utf-8")
        raise RuntimeError("Criminal search radio button not found on page.")

    console.print("[green]Search form ready[/green]")


async def search_case(page: Page, year: int, number: int) -> Optional[str]:
    await navigate_to_search(page)

    # Double-check we're still on the search page before filling fields
    if await check_current_page(page) == "tos":
        console.print("[magenta]Redirected to TOS after navigate_to_search![/magenta]")
        await ensure_past_tos(page)
        await navigate_to_search(page)

    # Fill fields with detailed logging
    console.print(f"[cyan]Filling form: Year={year}, Case={number:06d}[/cyan]")
    
    # Try to fill case category
    try:
        category_select = page.locator("select[name*='CaseCategory']")
        if await category_select.count() > 0:
            await category_select.select_option(label="CRIMINAL")
            console.print("[green]Selected CRIMINAL category[/green]")
        else:
            console.print("[yellow]No CaseCategory select found[/yellow]")
    except Exception as e:
        console.print(f"[yellow]Failed to select category: {e}[/yellow]")
    
    # Check page again before filling year
    if await check_current_page(page) == "tos":
        console.print("[magenta]Redirected to TOS while filling form![/magenta]")
        await ensure_past_tos(page)
        await navigate_to_search(page)
        # Re-fill the category since we lost state
        try:
            category_select = page.locator("select[name*='CaseCategory']")
            if await category_select.count() > 0:
                await category_select.select_option(label="CRIMINAL")
                console.print("[green]Re-selected CRIMINAL category after TOS[/green]")
        except Exception as e:
            console.print(f"[yellow]Failed to re-select category: {e}[/yellow]")
    
    # Fill year
    try:
        year_select = page.locator("select[name*='ddlCaseYear']")
        if await year_select.count() > 0:
            await year_select.select_option(label=str(year))
            console.print(f"[green]Selected year: {year}[/green]")
        else:
            console.print("[red]No year select found![/red]")
    except Exception as e:
        console.print(f"[red]Failed to select year: {e}[/red]")
    
    # Fill case number
    try:
        case_input = page.locator("input[name*='txtCaseNum']")
        if await case_input.count() > 0:
            await case_input.fill(f"{number:06d}")
            console.print(f"[green]Filled case number: {number:06d}[/green]")
            
            # Verify the value was set
            filled_value = await case_input.input_value()
            console.print(f"[blue]Verified case number field value: '{filled_value}'[/blue]")
        else:
            console.print("[red]No case number input found![/red]")
    except Exception as e:
        console.print(f"[red]Failed to fill case number: {e}[/red]")

    # Submit with visibility checks and fallbacks
    console.print("[yellow]Submitting search…[/yellow]")
    
    # Final check before submitting
    if await check_current_page(page) == "tos":
        console.print("[magenta]Redirected to TOS before submit![/magenta]")
        await ensure_past_tos(page)
        return None  # Give up on this case
    
    # Save the current form state for debugging
    current_html = await page.content()
    (Path("out") / "debug_before_submit.html").write_text(current_html, encoding="utf-8")
    console.print("[blue]Saved form state before submit to debug_before_submit.html[/blue]")
    
    # Try multiple submission strategies
    clicked = False
    submit_selectors = [
        "input[name*='btnSubmitCase']",
        "input[type='submit'][value*='Submit']", 
        "input[type='submit'][value*='Search']",
        "button:has-text('Submit')", 
        "button:has-text('Search')",
        "input[id*='Submit']",
        "input[id*='Search']"
    ]
    
    for sel in submit_selectors:
        btn = page.locator(sel)
        count = await btn.count()
        console.print(f"[blue]Checking selector '{sel}': found {count} elements[/blue]")
        
        if count > 0:
            try:
                console.print(f"[green]Attempting to click: {sel}[/green]")
                # Try to wait for navigation after clicking
                async with page.expect_navigation(timeout=20000):
                    await btn.first.click()
                clicked = True
                console.print(f"[green]Successfully clicked and navigated with: {sel}[/green]")
                break
            except Exception as e:
                console.print(f"[yellow]Failed to click {sel}: {e}[/yellow]")
                continue
    
    if not clicked:
        console.print("[yellow]No submit button worked, trying Enter key on case number field[/yellow]")
        try:
            case_input = page.locator("input[name*='txtCaseNum']")
            if await case_input.count() > 0:
                async with page.expect_navigation(timeout=20000):
                    await case_input.press("Enter")
                console.print("[green]Successfully submitted with Enter key[/green]")
                clicked = True
        except Exception as e:
            console.print(f"[red]Enter key submission failed: {e}[/red]")
    
    if not clicked:
        # Last resort: try JavaScript form submission
        console.print("[yellow]Trying JavaScript form submission[/yellow]")
        try:
            await page.evaluate("""
                () => {
                    const forms = document.forms;
                    for (let i = 0; i < forms.length; i++) {
                        const form = forms[i];
                        if (form.action && form.action.includes('Search.aspx')) {
                            form.submit();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
            clicked = True
            console.print("[green]Successfully submitted with JavaScript[/green]")
        except Exception as e:
            console.print(f"[red]JavaScript submission failed: {e}[/red]")
    
    if not clicked:
        (Path("out")/"debug_no_submit.html").write_text(current_html, encoding="utf-8")
        raise RuntimeError("Could not find any way to submit the search form.")

    # Wait for response and check what page we got
    await page.wait_for_load_state("domcontentloaded", timeout=15000)
    
    # Check if we got redirected to TOS after submit
    page_type = await check_current_page(page)
    if page_type == "tos":
        console.print("[magenta]Redirected to TOS after submit - case search failed[/magenta]")
        return None
    
    # Save the response for debugging
    response_html = await page.content()
    (Path("out") / "debug_after_submit.html").write_text(response_html, encoding="utf-8")
    console.print("[blue]Saved response after submit to debug_after_submit.html[/blue]")
    
    # Check for various error conditions
    if "No cases found matching criteria" in response_html or "ERROR: No cases found" in response_html:
        console.print("[red]No cases found for this search.[/red]")
        return None
    
    # Check if we're still on search page
    current_url = page.url
    console.print(f"[blue]URL after submit: {current_url}[/blue]")
    
    if "Search.aspx" in current_url:
        console.print("[red]Still on search page after submit![/red]")
        # Look for any error messages or validation issues
        error_patterns = [
            "required", "invalid", "error", "must", "cannot", "please"
        ]
        for pattern in error_patterns:
            if pattern.lower() in response_html.lower():
                console.print(f"[red]Found potential error message containing '{pattern}'[/red]")
        
        (Path("out")/"debug_stuck_on_search.html").write_text(response_html, encoding="utf-8")
        console.print("[red]Submitted, but still stuck on search page — saving debug_stuck_on_search.html[/red]")
        return None

    # Prefer waiting for a recognizable URL/pattern
    # Summary/Docket/Costs/Defendant/Attorney all use q=… token. Accept if it appears.
    try:
        await page.wait_for_url(re.compile(r".*CR_CaseInformation_.*q=.*"), timeout=12000)
        console.print("[green]Successfully reached case information page[/green]")
    except:
        console.print("[yellow]Timeout waiting for case info URL pattern[/yellow]")

    # Extract a case-id looking token
    m = re.search(r"CR-\d{2}-\d{6}-[A-Z]", response_html)
    if m:
        console.print(f"[green]Found case ID: {m.group(0)}[/green]")
        return m.group(0)

    console.print("[yellow]No case ID found in response[/yellow]")
    return None

async def open_tab(page: Page, tab_name: str):
    link = page.get_by_role("link", name=re.compile(tab_name, re.I))
    if await link.count() > 0:
        await link.first.click()
        await page.wait_for_load_state("load")
    else:
        url = page.url
        if "q=" in url:
            token = url.split("q=")[-1]
            mapping = {
                "summary": "CR_CaseInformation_Summary.aspx",
                "docket": "CR_CaseInformation_Docket.aspx",
                "costs": "CR_CaseInformation_Costs.aspx",
                "defendant": "CR_CaseInformation_Defendant.aspx",
                "attorney": "CR_CaseInformation_Attorney.aspx",
            }
            key = tab_name.lower()
            if key in mapping:
                await page.goto(f"{BASE_URL}/{mapping[key]}?q={token}", wait_until="load")

    # Confirm the table appears; if not, log loudly and continue
    try:
        await page.wait_for_selector("table", timeout=12000)
    except:
        console.print(f"[red]'{tab_name}' tab did not render a table — saving debug.[/red]")
        (Path("out")/f"debug_no_table_{tab_name.lower()}.html").write_text(await page.content(), encoding="utf-8")

# Removed save_html function - HTML content now stored in JSON structure
async def extract_summary(page: Page) -> Dict[str, Any]:
    html = await page.content()
    case_id = None
    m = re.search(r"(CR-\d{2}-\d{6}-[A-Z])", html)
    if m:
        case_id = m.group(1)
    data = {"case_id": case_id}
    kv = await kv_from_table(page, "table")
    if kv:
        data["fields"] = kv
    return data

async def extract_docket(page: Page) -> List[Dict[str, Any]]:
    return await grid_from_table(page, "table")

async def extract_docket_with_pdfs(page: Page) -> List[Dict[str, Any]]:
    """Extract docket entries and include PDF download links"""
    docket_entries = []
    
    # Look for the docket table
    table = page.locator("table.gridview, table#SheetContentPlaceHolder_caseDocket_gvDocketInformation")
    
    if await table.count() == 0:
        console.print("[yellow]No docket table found[/yellow]")
        return await grid_from_table(page, "table")
    
    # Get all rows except header
    rows = table.locator("tr").nth(1).locator("~ tr")  # Skip header row
    
    for i in range(await rows.count()):
        row = rows.nth(i)
        cells = row.locator("td")
        
        if await cells.count() >= 6:  # Expected columns
            entry = {
                "proceeding_date": (await cells.nth(0).inner_text()).strip(),
                "filing_date": (await cells.nth(1).inner_text()).strip(),
                "docket_party": (await cells.nth(2).inner_text()).strip(),
                "docket_type": (await cells.nth(3).inner_text()).strip(),
                "docket_description": (await cells.nth(4).inner_text()).strip(),
                "pdf_link": None,
                "pdf_filename": None
            }
            
            # Check for PDF link in the last column
            image_cell = cells.nth(5)
            pdf_link = image_cell.locator("a[href*='DisplayImageList.aspx']")
            
            if await pdf_link.count() > 0:
                href = await pdf_link.get_attribute("href")
                if href:
                    entry["pdf_link"] = href
                    # Create a filename from the date and type
                    safe_date = entry["filing_date"].replace("/", "-")
                    safe_type = re.sub(r'[^\w\-]', '_', entry["docket_type"])
                    entry["pdf_filename"] = f"{safe_date}_{safe_type}_{i+1}.pdf"
            
            docket_entries.append(entry)
    
    return docket_entries

async def download_pdf_with_playwright(page: Page, pdf_link: str, output_path: Path, filename: str) -> bool:
    """Download a PDF file using the authenticated Playwright browser session"""
    try:
        console.print(f"[blue]Downloading PDF: {filename}[/blue]")
        
        # Navigate to the PDF link using the same authenticated session
        full_url = f"{BASE_URL}/{pdf_link}" if not pdf_link.startswith("http") else pdf_link
        
        # Create a new page for the PDF download to avoid interfering with main page
        context = page.context
        pdf_page = await context.new_page()
        
        try:
            response = await pdf_page.goto(full_url, timeout=30000)
            
            if response and response.status == 200:
                content_type = response.headers.get('content-type', '').lower()
                
                if 'pdf' in content_type or 'application/pdf' in content_type:
                    # Get the PDF content
                    pdf_content = await response.body()
                    
                    # Save to file
                    output_file = output_path / filename
                    async with aiofiles.open(output_file, 'wb') as f:
                        await f.write(pdf_content)
                    
                    file_size = output_file.stat().st_size
                    console.print(f"[green]✓ Downloaded {filename} ({file_size/1024:.1f}KB)[/green]")
                    return True
                else:
                    console.print(f"[yellow]⚠ {filename}: Not a PDF (content-type: {content_type})[/yellow]")
                    # Save the HTML content for debugging
                    html_content = await pdf_page.content()
                    debug_file = output_path / f"{filename}.html"
                    debug_file.write_text(html_content, encoding='utf-8')
                    console.print(f"[blue]Saved error page to {debug_file}[/blue]")
                    return False
            else:
                status = response.status if response else "No response"
                console.print(f"[red]✗ Failed to download {filename}: HTTP {status}[/red]")
                return False
                
        finally:
            await pdf_page.close()
            
    except Exception as e:
        console.print(f"[red]✗ Error downloading {filename}: {e}[/red]")
        return False

async def download_case_pdfs(page: Page, docket_entries: List[Dict[str, Any]], case_id: str, 
                           pdf_dir: Path) -> Dict[str, Any]:
    """Download all PDFs for a case using the authenticated browser session"""
    pdf_info = {
        "total_pdfs": 0,
        "downloaded": 0,
        "failed": 0,
        "files": []
    }
    
    # Create case-specific PDF directory
    case_pdf_dir = pdf_dir / case_id
    case_pdf_dir.mkdir(parents=True, exist_ok=True)
    
    pdf_entries = [entry for entry in docket_entries if entry.get("pdf_link")]
    pdf_info["total_pdfs"] = len(pdf_entries)
    
    if not pdf_entries:
        console.print(f"[yellow]No PDFs found for case {case_id}[/yellow]")
        return pdf_info
    
    console.print(f"[cyan]Found {len(pdf_entries)} PDFs for case {case_id}[/cyan]")
    
    for entry in pdf_entries:
        pdf_link = entry["pdf_link"]
        filename = entry["pdf_filename"]
        
        success = await download_pdf_with_playwright(page, pdf_link, case_pdf_dir, filename)
        
        if success:
            pdf_info["downloaded"] += 1
            pdf_info["files"].append({
                "filename": filename,
                "filing_date": entry["filing_date"],
                "docket_type": entry["docket_type"],
                "status": "downloaded"
            })
        else:
            pdf_info["failed"] += 1
            pdf_info["files"].append({
                "filename": filename,
                "filing_date": entry["filing_date"],
                "docket_type": entry["docket_type"],
                "status": "failed"
            })
        
        # Polite delay between downloads
        await asyncio.sleep(1.0)
    
    return pdf_info

async def extract_costs(page: Page) -> List[Dict[str, Any]]:
    return await grid_from_table(page, "table")

async def extract_defendant(page: Page) -> Dict[str, Any]:
    return await kv_from_table(page, "table")

async def extract_attorneys(page: Page) -> List[Dict[str, Any]]:
    return await grid_from_table(page, "table")

def next_numbers(start: int, direction: str, limit: int):
    up = list(range(start, start + limit)) if direction in ("up", "both") else []
    down = list(range(start - 1, max(0, start - limit) - 1, -1)) if direction in ("down", "both") else []
    seq = []
    for i in range(limit):
        if i < len(up): seq.append(up[i])
        if i < len(down): seq.append(down[i])
    seen, out = set(), []
    for n in seq:
        if n not in seen and 0 <= n <= 999999:
            seen.add(n); out.append(n)
    return out

def load_resume_state(path: Path):
    if path.exists():
        try:
            return int(path.read_text().strip())
        except:
            return None
    return None

def save_resume_state(path: Path, number: int):
    path.write_text(str(number))

def polite_delay(delay_ms: int):
    """Sleep for the specified number of milliseconds to be polite to the server."""
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)

@retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
async def snapshot_case(page, year: int, number: int, out_root: Path, delay_ms: int, 
                       download_pdfs: bool = False, case_id_filter: Optional[List[str]] = None) -> Dict[str, Any]:
    console.print(f"[cyan]>>> Working case {year}-{number:06d}[/cyan]")
    
    # Create comprehensive case data structure
    case_data: Dict[str, Any] = {
        "metadata": {
            "year": year,
            "number": number,
            "case_number_formatted": f"{year}-{number:06d}",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "scraper_version": "1.0.0",
            "source_url": "https://cpdocket.cp.cuyahogacounty.gov"
        },
        "summary": {},
        "docket": [],
        "costs": [],
        "defendant": {},
        "attorneys": [],
        "errors": [],
        "html_snapshots": {},
        "pdf_info": None
    }
    
    try:
        case_id = await search_case(page, year, number)
        polite_delay(DEFAULT_DELAY)
        
        if not case_id:
            console.print(f"[bright_black]{year}-{number:06d}: no case (error page or stuck on search).[/bright_black]")
            case_data["metadata"]["exists"] = False
            case_data["metadata"]["case_id"] = None
            case_data["errors"].append({
                "type": "case_not_found",
                "message": "No case found matching search criteria",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            return case_data
            
        case_data["metadata"]["exists"] = True
        case_data["metadata"]["case_id"] = case_id
        console.print(f"[green]Found case: {case_id}[/green]")

        # Extract Summary
        try:
            await open_tab(page, "Summary")
            case_data["html_snapshots"]["summary"] = await page.content()
            case_data["summary"] = await extract_summary(page)
            console.print("[green]✓ Summary extracted[/green]")
        except Exception as e:
            console.print(f"[red]✗ Summary extraction failed: {e}[/red]")
            case_data["errors"].append({
                "type": "summary_extraction_error",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        polite_delay(DEFAULT_DELAY)

        # Extract Docket
        try:
            await open_tab(page, "Docket")
            case_data["html_snapshots"]["docket"] = await page.content()
            
            # Use PDF-aware extraction if downloading PDFs, otherwise use regular extraction
            if download_pdfs and (not case_id_filter or case_id in case_id_filter):
                case_data["docket"] = await extract_docket_with_pdfs(page)
                console.print(f"[green]✓ Docket extracted with PDF links ({len(case_data['docket'])} entries)[/green]")
                
                # Download PDFs if requested
                try:
                    pdf_dir = out_root / "pdfs"
                    pdf_info = await download_case_pdfs(page, case_data["docket"], case_id, pdf_dir)
                    case_data["pdf_info"] = pdf_info
                    console.print(f"[green]✓ PDFs: {pdf_info['downloaded']}/{pdf_info['total_pdfs']} downloaded[/green]")
                except Exception as pdf_error:
                    console.print(f"[red]✗ PDF download failed: {pdf_error}[/red]")
                    case_data["errors"].append({
                        "type": "pdf_download_error",
                        "message": str(pdf_error),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
            else:
                case_data["docket"] = await extract_docket(page)
                console.print(f"[green]✓ Docket extracted ({len(case_data['docket'])} entries)[/green]")
                
        except Exception as e:
            console.print(f"[red]✗ Docket extraction failed: {e}[/red]")
            case_data["errors"].append({
                "type": "docket_extraction_error",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        polite_delay(DEFAULT_DELAY)

        # Extract Costs
        try:
            await open_tab(page, "Costs")
            case_data["html_snapshots"]["costs"] = await page.content()
            case_data["costs"] = await extract_costs(page)
            console.print(f"[green]✓ Costs extracted ({len(case_data['costs'])} entries)[/green]")
        except Exception as e:
            console.print(f"[red]✗ Costs extraction failed: {e}[/red]")
            case_data["errors"].append({
                "type": "costs_extraction_error",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        polite_delay(DEFAULT_DELAY)

        # Extract Defendant
        try:
            await open_tab(page, "Defendant")
            case_data["html_snapshots"]["defendant"] = await page.content()
            case_data["defendant"] = await extract_defendant(page)
            console.print("[green]✓ Defendant extracted[/green]")
        except Exception as e:
            console.print(f"[red]✗ Defendant extraction failed: {e}[/red]")
            case_data["errors"].append({
                "type": "defendant_extraction_error",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        polite_delay(DEFAULT_DELAY)

        # Extract Attorneys
        try:
            await open_tab(page, "Attorney")
            case_data["html_snapshots"]["attorneys"] = await page.content()
            case_data["attorneys"] = await extract_attorneys(page)
            console.print(f"[green]✓ Attorneys extracted ({len(case_data['attorneys'])} entries)[/green]")
        except Exception as e:
            console.print(f"[red]✗ Attorneys extraction failed: {e}[/red]")
            case_data["errors"].append({
                "type": "attorneys_extraction_error",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        polite_delay(DEFAULT_DELAY)

    except Exception as e:
        console.print(f"[red]✗ Critical error during case processing: {e}[/red]")
        case_data["errors"].append({
            "type": "critical_processing_error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        case_data["metadata"]["exists"] = False

    return case_data

async def find_year_start(page: Page, year: int, reference_case: int) -> int:
    """Find the starting case number for a given year by probing backward"""
    console.print(f"[cyan]🔍 Finding start of year {year} (reference: {reference_case:06d})[/cyan]")
    
    # Start by checking progressively larger gaps backward
    test_gaps = [5000, 4000, 3000, 2000, 1000, 500]
    last_found = None
    
    for gap in test_gaps:
        test_case = max(1, reference_case - gap)
        console.print(f"[blue]Testing case {year}-{test_case:06d} (gap -{gap})[/blue]")
        
        case_id = await search_case(page, year, test_case)
        polite_delay(DEFAULT_DELAY)
        
        if case_id:
            console.print(f"[green]✓ Found case {case_id}[/green]")
            last_found = test_case
        else:
            console.print(f"[yellow]✗ No case found at {year}-{test_case:06d}[/yellow]")
            break
    
    if last_found is None:
        console.print(f"[red]No cases found for year {year}, using reference case {reference_case}[/red]")
        return reference_case
    
    # Now narrow down by binary search between last_found and last_found + gap
    console.print(f"[cyan]🎯 Narrowing down start of {year} around case {last_found:06d}[/cyan]")
    
    # Binary search to find the exact start
    low = max(1, last_found - 100)  # Go back a bit more
    high = last_found + 200        # Go forward a bit
    
    # Find the first case that exists
    start_case = last_found
    for probe in range(low, high):
        case_id = await search_case(page, year, probe)
        polite_delay(DEFAULT_DELAY // 2)  # Faster probing
        
        if case_id:
            start_case = probe
            console.print(f"[green]🎯 Found year {year} starts at case {start_case:06d} ({case_id})[/green]")
            break
    
    return start_case

async def find_year_end(page: Page, year: int, start_case: int) -> int:
    """Find the ending case number for a given year by probing forward"""
    console.print(f"[cyan]🔍 Finding end of year {year} (starting from: {start_case:06d})[/cyan]")
    
    # Probe forward in larger chunks to find where cases stop
    current = start_case
    last_found = start_case
    gap = 1000
    
    while gap >= 10:
        probe = current + gap
        if probe > 999999:  # Max case number
            break
            
        console.print(f"[blue]Testing case {year}-{probe:06d} (gap +{gap})[/blue]")
        case_id = await search_case(page, year, probe)
        polite_delay(DEFAULT_DELAY // 2)
        
        if case_id:
            console.print(f"[green]✓ Found case {case_id}[/green]")
            last_found = probe
            current = probe
        else:
            console.print(f"[yellow]✗ No case found at {year}-{probe:06d}[/yellow]")
            # Reduce gap and try smaller increments
            gap = gap // 2
            if gap < 10:
                break
    
    # Fine-tune the end by checking case by case from last_found
    console.print(f"[cyan]🎯 Fine-tuning end of {year} from case {last_found:06d}[/cyan]")
    
    end_case = last_found
    for probe in range(last_found, min(last_found + 100, 999999)):
        case_id = await search_case(page, year, probe)
        polite_delay(DEFAULT_DELAY // 3)
        
        if case_id:
            end_case = probe
        else:
            # Stop at first gap - might be the end
            break
    
    console.print(f"[green]🎯 Year {year} appears to end around case {end_case:06d}[/green]")
    return end_case

async def run():
    ap = argparse.ArgumentParser(description="Cuyahoga County Court Docket Scraper & Analytics")
    
    subparsers = ap.add_subparsers(dest="command", help="Command to execute")
    
    # Scraper command
    scraper = subparsers.add_parser("scrape", help="Scrape court docket data")
    scraper.add_argument("--year", type=int, default=int(os.getenv("YEAR", "2025")))
    scraper.add_argument("--start", type=int, default=int(os.getenv("START_NUMBER", "706402")))
    scraper.add_argument("--limit", type=int, default=int(os.getenv("LIMIT", "100")))
    scraper.add_argument("--direction", choices=["up","down","both"], default=os.getenv("DIRECTION","both"))
    scraper.add_argument("--output-dir", default=os.getenv("OUTPUT_DIR","./out"))
    scraper.add_argument("--delay-ms", type=int, default=int(os.getenv("DELAY_MS","1250")))
    scraper.add_argument("--headless", action="store_true")
    scraper.add_argument("--resume", action="store_true")
    scraper.add_argument("--download-pdfs", action="store_true", help="Download PDF files from docket entries")
    scraper.add_argument("--pdf-cases", nargs="*", help="Specific case IDs to download PDFs for (e.g., CR-25-706402-A)")
    scraper.add_argument("--discover-years", action="store_true", help="Discover and scrape full years (2025, 2024, 2023)")
    scraper.add_argument("--reference-case", type=int, default=706402, help="Reference case number to start discovery from")
    
    # Statistics command
    stats_cmd = subparsers.add_parser("stats", help="Generate statistics and analysis for downloaded data")
    stats_cmd.add_argument("--year", type=int, default=2025, help="Year to analyze")
    stats_cmd.add_argument("--data-dir", default="./out", help="Directory with downloaded case data")
    stats_cmd.add_argument("--limit", type=int, default=None, help="Limit number of cases to analyze")
    stats_cmd.add_argument("--html", action="store_true", help="Generate HTML dashboard")
    
    # Default to scrape if no command given
    if len([arg for arg in __import__('sys').argv if not arg.startswith('-')]) == 1:
        ap.set_defaults(command="scrape")
    
    args = ap.parse_args()
    
    # Route to appropriate command
    if args.command == "stats":
        if generate_yearly_report is None:
            console.print("[red]Error: statistics module not available. Install matplotlib, pandas, seaborn.[/red]")
            return
        
        console.rule(f"[bold cyan]📊 Generating Year {args.year} Statistics[/bold cyan]")
        generate_yearly_report(Path(args.data_dir), args.year, limit=args.limit)
        
        # Generate HTML dashboard if requested
        if args.html and CaseDataAnalyzer and generate_html_dashboard:
            analyzer = CaseDataAnalyzer(Path(args.data_dir))
            cases = analyzer.load_cases(args.year, limit=args.limit)
            if cases:
                stats = analyzer.analyze_year(cases)
                output_dir = Path("./statistics_output") / str(args.year)
                output_dir.mkdir(parents=True, exist_ok=True)
                dashboard_file = output_dir / "index.html"
                generate_html_dashboard(stats, dashboard_file)
                console.print(f"[green]✅ Dashboard available at: {dashboard_file}[/green]")
        return
    
    # Otherwise, run scraper
    if args.command != "scrape":
        args = ap.parse_args(["scrape"])  # Default to scrape

    # Set up PDF downloading for your specific cases
    pdf_cases = args.pdf_cases or ["CR-25-706402-A", "CR-23-684826-A"]
    
    cfg = Cfg(
        headless=(True if args.headless else (False if os.getenv("HEADLESS","false").lower()=="false" else True)),
        year=args.year, start_number=args.start, direction=args.direction, limit=args.limit,
        output_dir=args.output_dir, delay_ms=args.delay_ms, resume=args.resume,
        download_pdfs=args.download_pdfs, pdf_cases=pdf_cases
    )

    # Determine years to process
    if args.discover_years:
        years_to_process = [2025, 2024, 2023]
        console.rule(f"[bold]🚀 Cuyahoga CP Full Year Discovery[/bold]")
        console.print(f"[cyan]Years to discover and scrape: {', '.join(map(str, years_to_process))}[/cyan]")
        console.print(f"[cyan]Reference case for discovery: {args.reference_case:06d}[/cyan]")
        console.print(f"[cyan]PDF download enabled for: {', '.join(pdf_cases)}[/cyan]")
    else:
        years_to_process = [cfg.year]

        # Single year mode setup will be done after browser launch

    async with async_playwright() as p:
        # Use persistent context with user data directory for authenticated session
        user_data_dir = Path("./browser_data")
        user_data_dir.mkdir(exist_ok=True)
        
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=cfg.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ],
            viewport={"width": 1920, "height": 1080},
        )
        page = context.pages[0] if context.pages else await context.new_page()

        # SPEED: block heavy resources (images, media, fonts)
        await page.route("**/*", lambda route: route.abort()
                         if route.request.resource_type in {"image", "media", "font"}
                         else route.continue_())

        # Start tracing for debugging
        try:
            await context.tracing.start(screenshots=True, snapshots=True, sources=True)
        except:
            pass

        # Setup directories for single year mode
        out_dir = Path(cfg.output_dir) / str(cfg.year)
        out_dir.mkdir(parents=True, exist_ok=True)
        resume_file = out_dir / ".last_number"
        
        # Generate targets for single year mode
        if args.discover_years:
            targets = []  # Not used in discovery mode but keep for type safety
        else:
            # Setup single year mode
            if cfg.resume:
                n = load_resume_state(resume_file)
                if n is not None:
                    cfg.start_number = n

            targets = next_numbers(cfg.start_number, cfg.direction, cfg.limit)
            
            # Display plan
            console.rule(f"[bold]Cuyahoga CP Scraper[/bold]  year={cfg.year} start={cfg.start_number} direction={cfg.direction} limit={cfg.limit}")
            table = Table(title="Run Plan")
            table.add_column("#"); table.add_column("Case Number")
            for idx, num in enumerate(targets, 1):
                table.add_row(str(idx), f"{cfg.year}-{num:06d}")
            console.print(table)
        
        # Process years
        if args.discover_years:
            # Year discovery mode
            await process_full_years(page, years_to_process, args.reference_case, 
                                   cfg.output_dir, cfg.delay_ms, cfg.download_pdfs, cfg.pdf_cases)
        else:
            # Single year/range mode  
            await process_case_range(page, cfg.year, targets, out_dir, resume_file,
                                   cfg.delay_ms, cfg.download_pdfs, cfg.pdf_cases)
        
        # Stop tracing before closing
        try:
            trace_dir = Path(cfg.output_dir)
            trace_dir.mkdir(parents=True, exist_ok=True)
            await context.tracing.stop(path=str((trace_dir / "trace.zip").resolve()))
        except:
            pass
        
        await context.close()

    console.print(f"[green]Done.[/green] Output at: {cfg.output_dir}")

async def process_case_range(page: Page, year: int, targets: List[int], out_dir: Path, 
                           resume_file: Path, delay_ms: int, download_pdfs: bool, pdf_cases: List[str]):
    """Process a specific range of case numbers for a single year"""
    processed = 0
    with Progress() as progress:
        task = progress.add_task("Scraping", total=len(targets))
        for num in targets:
            # Create timestamped filename for the JSON output
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            case_filename = f"{year}-{num:06d}_{timestamp}.json"
            case_filepath = out_dir / case_filename
            
            try:
                console.print(f"[cyan]Processing case {year}-{num:06d}...[/cyan]")
                case_data = await snapshot_case(page, year, num, out_dir, delay_ms, 
                                               download_pdfs, pdf_cases)
                
                # Save the comprehensive JSON file
                case_filepath.write_text(
                    json.dumps(case_data, indent=2, ensure_ascii=False), 
                    encoding="utf-8"
                )
                
                # Log success with file info
                file_size = case_filepath.stat().st_size
                file_size_kb = file_size / 1024
                console.print(f"[green]✓ Completed case {num:06d} ({file_size_kb:.1f}KB) -> {case_filename}[/green]")
                
                # Log extraction summary
                if case_data["metadata"]["exists"]:
                    summary_items = [
                        f"Summary: {len(case_data['summary'])} fields",
                        f"Docket: {len(case_data['docket'])} entries", 
                        f"Costs: {len(case_data['costs'])} entries",
                        f"Defendant: {len(case_data['defendant'])} fields",
                        f"Attorneys: {len(case_data['attorneys'])} entries"
                    ]
                    if case_data["errors"]:
                        summary_items.append(f"Errors: {len(case_data['errors'])}")
                    console.print(f"[blue]  └─ {' | '.join(summary_items)}[/blue]")
                
            except Exception as e:
                console.print(f"[red]✗ Failed case {num:06d}: {str(e)}[/red]")
                
                # Create error case data
                error_case_data = {
                    "metadata": {
                        "year": year,
                        "number": num,
                        "case_number_formatted": f"{year}-{num:06d}",
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "scraper_version": "1.0.0",
                        "exists": False,
                        "case_id": None
                    },
                    "summary": {},
                    "docket": [],
                    "costs": [],
                    "defendant": {},
                    "attorneys": [],
                    "errors": [{
                        "type": "critical_scraper_error",
                        "message": str(e),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }],
                    "html_snapshots": {}
                }
                
                case_filepath.write_text(
                    json.dumps(error_case_data, indent=2, ensure_ascii=False), 
                    encoding="utf-8"
                )
                
            processed += 1
            save_resume_state(resume_file, num)
            progress.update(task, advance=1)

async def process_full_years(page: Page, years: List[int], reference_case: int, 
                           output_dir: str, delay_ms: int, download_pdfs: bool, pdf_cases: List[str]):
    """Discover and process full years of cases"""
    year_ranges = {}
    
    # Discover ranges for each year
    for year in years:
        console.rule(f"[bold]🔍 DISCOVERING YEAR {year}[/bold]")
        
        # Find start and end of year
        if year == 2025:
            # Use reference case for 2025
            start_case = await find_year_start(page, year, reference_case)
        elif year == 2024:
            # Use case number slightly before 2025 start as reference
            start_case = await find_year_start(page, year, reference_case - 10000)
        else:  # 2023
            # Use case number from 2023 reference (684826)
            start_case = await find_year_start(page, year, 684826)
        
        end_case = await find_year_end(page, year, start_case)
        year_ranges[year] = (start_case, end_case)
        
        total_cases = end_case - start_case + 1
        console.print(f"[green]📊 Year {year}: Cases {start_case:06d} to {end_case:06d} ({total_cases:,} total)[/green]")
    
    # Process each year
    for year in years:
        start_case, end_case = year_ranges[year]
        
        console.rule(f"[bold]📥 SCRAPING YEAR {year}[/bold]")
        console.print(f"[cyan]Processing cases {start_case:06d} to {end_case:06d}[/cyan]")
        
        # Create year output directory
        year_dir = Path(output_dir) / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        resume_file = year_dir / ".last_number"
        
        # Check for resume
        resume_case = load_resume_state(resume_file)
        if resume_case and resume_case > start_case:
            start_case = resume_case
            console.print(f"[yellow]🔄 Resuming from case {start_case:06d}[/yellow]")
        
        # Generate list of all cases for this year
        all_cases = list(range(start_case, end_case + 1))
        
        # Process all cases in this year
        await process_case_range(page, year, all_cases, year_dir, resume_file,
                               delay_ms, download_pdfs, pdf_cases)
        
        console.print(f"[green]✅ Completed year {year}[/green]")

if __name__ == "__main__":
    asyncio.run(run())
