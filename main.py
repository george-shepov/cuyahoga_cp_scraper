
import asyncio, json, os, re, time, argparse, csv, io, fcntl
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, field_validator
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, SpinnerColumn
from rich.panel import Panel
from rich.markdown import Markdown
from tenacity import retry, stop_after_attempt, wait_fixed

from playwright.async_api import async_playwright, Page, Playwright, TimeoutError as PWTimeout

# Try to import statistics and dashboard modules (optional)
generate_yearly_report = None
CaseDataAnalyzer = None
generate_html_dashboard = None

try:
    from statistics import generate_yearly_report, CaseDataAnalyzer
except (ImportError, ModuleNotFoundError):
    generate_yearly_report = None
    CaseDataAnalyzer = None

try:
    from dashboard import generate_html_dashboard
except (ImportError, ModuleNotFoundError):
    generate_html_dashboard = None

BASE_URL = os.getenv("BASE_URL", "https://cpdocket.cp.cuyahogacounty.gov")

# Optional: toned-down delays by default
DEFAULT_DELAY = max(300, int(os.getenv("DELAY_MS", "800")))  # 0.3–0.8s polite delay

console = Console()

# Watchdog / stagnation controls (seconds and max consecutive no-save events)
STAGNATION_TIMEOUT = int(os.getenv("STAGNATION_TIMEOUT", "300"))  # 5 minutes
STAGNATION_MAX_NO_SAVE = int(os.getenv("STAGNATION_MAX_NO_SAVE", "50"))

class Cfg(BaseModel):
    headless: bool = False  # Set to False to see browser in action (can measure load times)
    case_category: str = os.getenv("CASE_CATEGORY", "CRIMINAL")
    year: int = int(os.getenv("YEAR", "2025"))
    start_number: int = int(os.getenv("START_NUMBER", "706402"))
    direction: str = os.getenv("DIRECTION", "both")  # up|down|both
    limit: int = int(os.getenv("LIMIT", "100"))
    delay_ms: int = int(os.getenv("DELAY_MS", "300"))  # Start fast: 300ms
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


def parse_embedded_table_to_csv(cell_text: str) -> str:
    """Convert tab-separated table data in a cell to CSV format.
    Input: "Header1\tHeader2\tHeader3\nRow1Col1\tRow1Col2\tRow1Col3\nRow2Col1\tRow2Col2\tRow2Col3"
    Output: CSV string with proper escaping
    """
    import csv
    import io
    
    if not cell_text or '\t' not in cell_text or '\n' not in cell_text:
        return cell_text
    
    try:
        lines = cell_text.strip().split('\n')
        rows = [line.split('\t') for line in lines]
        
        # Write to CSV in memory
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        writer.writerows(rows)
        return output.getvalue().strip()
    except Exception:
        # If parsing fails, return original
        return cell_text


def _stats_file_for_out_dir(year_dir: Path) -> Path:
    """Return the global stats.json path for the given year directory.
    year_dir is expected to be like ./out/2025; this returns ./out/stats.json
    """
    return year_dir.parent / "stats.json"


def increment_year_counter(year_dir: Path, year: int):
    """Atomically increment the counter for `year` in out/stats.json.

    Uses an exclusive flock and fsync to reduce race conditions when multiple
    scraper workers run concurrently. If anything fails we silently continue
    (we don't want counting to crash the scraper), but we try to be robust.
    """
    stats_path = _stats_file_for_out_dir(year_dir)
    # Ensure parent exists
    stats_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Open for read/write and create if missing
        with open(stats_path, "a+", encoding="utf-8") as f:
            # Acquire exclusive lock
            try:
                fcntl.flock(f, fcntl.LOCK_EX)
            except Exception:
                pass

            # Read existing content
            f.seek(0)
            try:
                content = f.read()
                data = json.loads(content) if content.strip() else {}
            except Exception:
                data = {}

            key = str(year)
            # If stats file had no entry for this year, seed it from existing
            # number of json files we already have for the year directory so
            # counters remain consistent with filesystem state.
            if key not in data:
                try:
                    existing = len(list(year_dir.glob("*.json")))
                except Exception:
                    existing = 0
                data[key] = int(existing)

            # Now increment for the newly saved file
            data[key] = int(data.get(key, 0)) + 1

            # Write back
            f.seek(0)
            f.truncate()
            f.write(json.dumps(data, indent=2))
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass

            # Release lock
            try:
                fcntl.flock(f, fcntl.LOCK_UN)
            except Exception:
                pass
    except Exception:
        # Don't let stats updating break scraping
        return


async def kv_from_table(page: Page, table_selector: str) -> Dict[str, Any]:
    """Extract key-value data from table with context destruction recovery.
    Embedded tab-separated tables are converted to CSV format and stored in parent dict."""
    data = {}
    try:
        # Get row count safely - this is where context destruction happens
        try:
            rows = page.locator(f"{table_selector} tr")
            count = await rows.count()
        except Exception:
            # Context destroyed during count - return empty dict gracefully
            return data
        
        table_counter = 0
        for i in range(count):
            try:
                # Re-fetch fresh row reference each time
                rows_fresh = page.locator(f"{table_selector} tr")
                try:
                    fresh_count = await rows_fresh.count()
                except Exception:
                    # Context destroyed mid-iteration
                    break
                
                if i >= fresh_count:
                    break
                
                row = rows_fresh.nth(i)
                cells = row.locator("td")
                cell_count = await cells.count()
                
                if cell_count >= 2:
                    try:
                        k_text = await cells.nth(0).inner_text()
                        v_text = await cells.nth(1).inner_text()
                        k = k_text.strip()
                        v = v_text.strip()
                        
                        # Check if this is an embedded table (tab-separated data)
                        if (k and '\t' in k and '\n' in k):
                            # Key is an embedded table - convert to CSV
                            csv_data = parse_embedded_table_to_csv(k)
                            data[f"embedded_table_{table_counter}"] = {
                                "format": "csv",
                                "data": csv_data
                            }
                            table_counter += 1
                        elif (v and '\t' in v and '\n' in v):
                            # Value is an embedded table - convert to CSV
                            csv_data = parse_embedded_table_to_csv(v)
                            data[f"embedded_table_{table_counter}"] = {
                                "format": "csv",
                                "data": csv_data
                            }
                            table_counter += 1
                        elif k:
                            # Normal key-value pair
                            data[k] = v
                    except Exception:
                        # Cell extraction failed - continue
                        pass
            except Exception:
                # Row extraction failed - try to continue
                if len(data) == 0:
                    continue
                break
    except Exception as e:
        # Top-level exception - just return what we got
        pass
    
    return data


async def capture_printer_pdfs_on_page(page: Page, out_root: Path, case_id: str, case_data: Dict[str, Any]):
    """Find printer-friendly links on the current page and save them as PDFs.
    Appends saved file paths to case_data['printer_pdfs'] and records errors in case_data['errors'].
    """
    try:
        print_hrefs = set()

        try:
            loc = page.locator("a[href*='isprint=Y']")
            cnt = await loc.count()
            for i in range(cnt):
                h = await loc.nth(i).get_attribute('href')
                if h:
                    print_hrefs.add(h)
        except Exception:
            pass

        try:
            loc2 = page.locator("a[id*='printer']")
            cnt2 = await loc2.count()
            for ii in range(cnt2):
                h = await loc2.nth(ii).get_attribute('href')
                if h:
                    print_hrefs.add(h)
        except Exception:
            pass

        try:
            loc3 = page.locator("a:has-text('Printer Friendly')")
            cnt3 = await loc3.count()
            for ii in range(cnt3):
                h = await loc3.nth(ii).get_attribute('href')
                if h:
                    print_hrefs.add(h)
        except Exception:
            pass

        if print_hrefs:
            pdf_dir = out_root / 'pdfs' / case_id
            pdf_dir.mkdir(parents=True, exist_ok=True)
            case_data.setdefault('printer_pdfs', [])
            idx = 0
            for href in sorted(print_hrefs):
                if href.startswith('http'):
                    url = href
                elif href.startswith('/'):
                    url = f"{BASE_URL}{href}"
                else:
                    url = f"{BASE_URL}/{href}"

                ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                pdf_name = f"{case_id}_printer_{idx}_{ts}.pdf"
                pdf_path = pdf_dir / pdf_name
                try:
                    await page.goto(url, wait_until='networkidle', timeout=30000)
                    await asyncio.sleep(1.0)
                    pdf_bytes = await page.pdf(format='Letter', print_background=True)
                    pdf_path.write_bytes(pdf_bytes)
                    case_data['printer_pdfs'].append(str(pdf_path))
                    idx += 1
                except Exception as epp:
                    case_data.setdefault('errors', [])
                    case_data['errors'].append({
                        'type': 'printer_pdf_error',
                        'message': f'Failed to capture printer PDF {href}: {epp}',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
    except Exception as e:
        console.print(f"[yellow]⚠ capture_printer_pdfs_on_page failed: {str(e)[:160]}[/yellow]")
async def grid_from_table(page: Page, table_selector: str) -> List[Dict[str, Any]]:
    """
    Extract table data with context destruction recovery.
    """
    out = []
    headers = []
    
    try:
        # Extract headers - with safe count
        try:
            thead = page.locator(f"{table_selector} thead tr th")
            thead_count = await thead.count()
            if thead_count == 0:
                thead = page.locator(f"{table_selector} tr").first.locator("th")
                thead_count = await thead.count()
        except Exception:
            # Context destroyed or table not found
            return out
        
        for i in range(thead_count):
            try:
                header_text = await thead.nth(i).inner_text()
                headers.append(header_text.strip() or f"col{i+1}")
            except Exception:
                break
        
        # Extract rows - with safe count
        try:
            rows = page.locator(f"{table_selector} tbody tr")
            row_count = await rows.count()
            if row_count == 0:
                rows = page.locator(f"{table_selector} tr:not(:first-child)")
                row_count = await rows.count()
        except Exception:
            # Context destroyed - return partial results
            return out
        
        for r in range(row_count):
            try:
                # Re-fetch fresh row reference each time
                rows_fresh = page.locator(f"{table_selector} tbody tr")
                if await rows_fresh.count() == 0:
                    rows_fresh = page.locator(f"{table_selector} tr:not(:first-child)")
                
                if r >= await rows_fresh.count():
                    break
                
                row = rows_fresh.nth(r)
                cols = row.locator("td")
                rec = {}
                
                for c in range(await cols.count()):
                    key = headers[c] if c < len(headers) else f"col{c+1}"
                    try:
                        cell_text = await cols.nth(c).inner_text()
                        rec[key] = cell_text.strip()
                    except Exception:
                        rec[key] = ""
                
                if rec:
                    out.append(rec)
            except Exception:
                # If row extraction fails, try to continue or exit gracefully
                if len(out) == 0:
                    raise
                break
    
    except Exception as e:
        if len(out) == 0:
            raise Exception(f"Table extraction failed: {e}")
    
    return out


async def check_current_page(page: Page) -> str:
    """Check what page we're currently on and return the page type"""
    url = page.url
    html = ""

    # Pages can still be navigating when checked; retry briefly before classifying.
    for _ in range(5):
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
            url = page.url
            html = await page.content()
            break
        except Exception:
            await asyncio.sleep(0.5)
    
    console.print(f"[blue]Current URL: {url}[/blue] - main.py:310")
    
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


def is_runtime_error_page_html(html: str) -> bool:
    """Detect ASP.NET runtime error pages returned by the court site."""
    if not html:
        return False

    h = html.lower()
    markers = [
        "server error in '/' application",
        "<title>runtime error</title>",
        "<!-- web.config configuration file -->",
        'customerrors mode="off"',
        'customerrors mode="remoteonly"',
        "an application error occurred on the server",
    ]
    return any(marker in h for marker in markers)


def docket_entries_look_like_runtime_error(entries: List[Dict[str, Any]]) -> bool:
    """Detect when parsed docket rows are actually runtime error snippets."""
    if not entries:
        return False

    blob = "\n".join(" ".join(str(v) for v in row.values() if v) for row in entries)
    return is_runtime_error_page_html(blob)

async def ensure_past_tos(page: Page):
    """Ensure we get past the TOS page - keep trying until we're not on TOS"""
    max_attempts = 5
    for attempt in range(max_attempts):
        page_type = await check_current_page(page)
        
        if page_type != "tos":
            console.print(f"[green]Successfully past TOS, on page type: {page_type}[/green] - main.py:333")
            return
            
        console.print(f"[magenta]On TOS page (attempt {attempt + 1}/{max_attempts})  accepting terms…[/magenta] - main.py:336")
        try:
            html = await page.content()
        except Exception:
            html = ""
        
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
                    console.print(f"[green]Found TOS button: {sel}[/green] - main.py:353")
                    # Wait for navigation to complete after clicking
                    async with page.expect_navigation(timeout=15000):
                        await loc.first.click()
                    clicked = True
                    console.print("[green]TOS button clicked and navigation completed[/green] - main.py:358")
                    break
                except Exception as e:
                    console.print(f"[yellow]Failed to click {sel}: {e}[/yellow] - main.py:361")
                    continue
        
        if not clicked:
            console.print("[red]Could not find an Accept/Continue control on TOS page.[/red] - main.py:365")
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
        console.print(f"[yellow]Navigating to Search.aspx (attempt {attempt + 1}/{max_attempts})…[/yellow] - main.py:384")
        
        try:
            await page.goto(f"{BASE_URL}/Search.aspx", wait_until="networkidle", timeout=30000)
        except Exception as e:
            console.print(f"[red]Failed to navigate: {e}[/red] - main.py:389")
            continue
        
        # Check what page we landed on
        page_type = await check_current_page(page)
        
        if page_type == "tos":
            console.print("[magenta]Landed on TOS page  handling…[/magenta] - main.py:396")
            await ensure_past_tos(page)
            # After TOS, try to go to search again
            try:
                await page.goto(f"{BASE_URL}/Search.aspx", wait_until="networkidle", timeout=30000)
            except:
                pass
            page_type = await check_current_page(page)
        
        if page_type in ["search", "search_initial"]:
            console.print("[green]Successfully reached Search.aspx[/green] - main.py:406")
            
            # Now ensure we're on the criminal search form
            console.print("[yellow]Selecting: CRIMINAL SEARCH BY CASE…[/yellow] - main.py:409")
            
            # Retry loop for criminal search selection - handle TOS redirects
            for select_attempt in range(3):
                # Find the radio button
                rb = page.locator("#SheetContentPlaceHolder_rbCrCase")
                rb_count = await rb.count()
                console.print(f"[blue]Found {rb_count} criminal search radio buttons[/blue] - main.py:416")
                
                if rb_count == 0:
                    console.print("[red]No criminal search radio button found![/red] - main.py:419")
                    raise RuntimeError("Criminal search radio button not found on page.")
                
                try:
                    console.print("[green]Clicking criminal search radio button[/green] - main.py:423")
                    
                    # Click the label to trigger postback
                    label = page.locator("label[for='SheetContentPlaceHolder_rbCrCase']")
                    await label.click()
                    
                    console.print("[blue]Waiting for UpdatePanel postback...[/blue] - main.py:429")
                    await page.wait_for_load_state("networkidle", timeout=20000)
                    
                except Exception as e:
                    console.print(f"[yellow]Label click failed: {e}[/yellow] - main.py:433")
                    # Try JavaScript fallback
                    await page.evaluate("""
                        () => {
                          const rb = document.querySelector('#SheetContentPlaceHolder_rbCrCase');
                          if (rb && window.__doPostBack) { 
                            rb.checked = true; 
                            __doPostBack('ctl00$SheetContentPlaceHolder$rbCrCase','');
                          }
                        }
                    """)
                    await page.wait_for_load_state("networkidle", timeout=20000)
                
                # Check for form widgets
                widgets_found = False
                for widget_attempt in range(10):
                    # Check if redirected to TOS
                    if await check_current_page(page) == "tos":
                        console.print("[magenta]Redirected to TOS, handling and retrying...[/magenta]")
                        await ensure_past_tos(page)
                        await page.goto(f"{BASE_URL}/Search.aspx", wait_until="networkidle", timeout=20000)
                        break  # Go back to radio button retry
                    
                    year_select = page.locator("select[name*='ddlCaseYear']")
                    case_input = page.locator("input[name*='txtCaseNum']")
                    
                    if await year_select.count() > 0 and await case_input.count() > 0:
                        console.print("[green]✓ Form widgets found![/green]")
                        widgets_found = True
                        break
                    
                    await page.wait_for_load_state("networkidle", timeout=3000)
                    await page.wait_for_timeout(300)
                
                if widgets_found:
                    console.print("[green]Search form ready[/green]")
                    return  # Success!
                elif select_attempt < 2:
                    console.print("[yellow]Widgets not found, retrying radio button selection...[/yellow]")
                    continue
                else:
                    raise RuntimeError("Search widgets not visible after 3 attempts")
            
            break  # Successfully navigated
        else:
            console.print(f"[red]Not on search page, got page type: {page_type}[/red] - main.py:339")
            if attempt == max_attempts - 1:
                raise RuntimeError(f"Cannot reach Search.aspx after {max_attempts} attempts. Final page type: {page_type}")
            continue
    
    # Duplicate code removed - now handled in navigate_to_search above


async def detect_year_from_case_number(page: Page, number: int) -> Optional[int]:
    """
    Auto-detect the year for a case number by searching without year specification
    and extracting it from the case ID format (e.g., CR-23-678533-A -> 2023)
    """
    console.print(f"[cyan]🔍 Auto-detecting year for case {number:06d}...[/cyan]")
    
    await navigate_to_search(page)
    
    # Fill category
    try:
        category_select = page.locator("select[name*='CaseCategory']")
        if await category_select.count() > 0:
            await category_select.select_option(label="CRIMINAL")
    except Exception as e:
        console.print(f"[yellow]Failed to select category: {e}[/yellow]")
    
    # Skip year selection - leave it blank or on default
    console.print("[blue]Skipping year selection to search across all years[/blue]")
    
    # Fill case number only
    try:
        case_input = page.locator("input[name*='txtCaseNum']")
        if await case_input.count() > 0:
            await case_input.fill(f"{number:06d}")
            console.print(f"[green]Filled case number: {number:06d}[/green]")
    except Exception as e:
        console.print(f"[red]Failed to fill case number: {e}[/red]")
        return None
    
    # Submit the search
    try:
        submit_selectors = [
            "input[name*='btnSubmitCase']",
            "input[type='submit'][value*='Submit']",
        ]
        
        clicked = False
        for sel in submit_selectors:
            btn = page.locator(sel)
            if await btn.count() > 0:
                try:
                    async with page.expect_navigation(timeout=20000):
                        await btn.first.click()
                    clicked = True
                    break
                except:
                    continue
        
        if not clicked:
            console.print("[red]Could not submit search form[/red]")
            return None
            
        await page.wait_for_load_state("domcontentloaded", timeout=15000)
        
    except Exception as e:
        console.print(f"[red]Failed to submit: {e}[/red]")
        return None
    
    # Check the result page for the case ID format
    try:
        page_content = await page.content()
        
        # Look for case ID pattern: CR-YY-NNNNNN-A
        # The year is in 2-digit format (23 = 2023, 24 = 2024, 25 = 2025)
        case_id_pattern = re.compile(r'CR-(\d{2})-' + str(number).zfill(6))
        match = case_id_pattern.search(page_content)
        
        if match:
            year_2digit = int(match.group(1))
            # Convert 2-digit year to 4-digit
            full_year = 2000 + year_2digit
            console.print(f"[green]✓ Detected year: {full_year} (from case ID pattern)[/green]")
            return full_year
        
        # Alternative: look for the case link text directly
        case_link_pattern = re.compile(r'CR-(\d{2})-\d{6}-[A-Z]')
        matches = case_link_pattern.findall(page_content)
        
        if matches:
            year_2digit = int(matches[0])
            full_year = 2000 + year_2digit
            console.print(f"[green]✓ Detected year: {full_year} (from case link)[/green]")
            return full_year
        
        console.print("[yellow]⚠ Could not find year in case ID format[/yellow]")
        return None
        
    except Exception as e:
        console.print(f"[red]Error detecting year: {e}[/red]")
        return None


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

    # If we landed on the search-results list page, open the first case link first.
    if "CaseSearchList.aspx" in current_url:
        try:
            first_case_link = page.locator("a[href*='CR_CaseInformation_Summary.aspx?q=']").first
            if await first_case_link.count() > 0:
                await first_case_link.click()
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
                response_html = await page.content()
                current_url = page.url
                console.print("[green]Opened first case from search list[/green]")
        except Exception as e:
            console.print(f"[yellow]Could not open first case from list: {str(e)[:120]}[/yellow]")

    # Prefer waiting for a recognizable URL/pattern
    # Summary/Docket/Costs/Defendant/Attorney all use q=… token. Accept if it appears.
    try:
        await page.wait_for_url(re.compile(r".*CR_CaseInformation_.*q=.*"), timeout=12000)
        console.print("[green]Successfully reached case information page[/green]")
    except Exception:
        console.print("[yellow]Timeout waiting for case info URL pattern[/yellow]")

    # Extract a case-id looking token
    m = re.search(r"CR-\d{2}-\d{6}-[A-Z]", response_html)
    if m:
        console.print(f"[green]Found case ID: {m.group(0)}[/green]")
        return m.group(0)

    console.print("[yellow]No case ID found in response[/yellow]")
    return None

async def open_tab(page: Page, tab_name: str):
    tab_lower = tab_name.lower()

    # We already land on Summary after search submit.
    if tab_lower == "summary":
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass
        return

    postback_target = {
        "docket": "ctl00$SheetContentPlaceHolder$caseHeader$lbDocket",
        "costs": "ctl00$SheetContentPlaceHolder$caseHeader$lbCosts",
        "defendant": "ctl00$SheetContentPlaceHolder$caseHeader$lbDefendant",
        "attorney": "ctl00$SheetContentPlaceHolder$caseHeader$lbAttorney",
    }

    async def go_to_tab() -> None:
        target = postback_target.get(tab_lower)
        if target:
            await page.evaluate(
                """
                (eventTarget) => {
                    if (typeof window.__doPostBack === 'function') {
                        window.__doPostBack(eventTarget, '');
                    }
                }
                """,
                target,
            )
            try:
                await page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                try:
                    await page.wait_for_load_state("load", timeout=15000)
                except Exception:
                    await page.wait_for_load_state("domcontentloaded", timeout=15000)
            return

        # Last-resort fallback for unexpected markup changes.
        link = page.get_by_role("link", name=re.compile(tab_name, re.I))
        if await link.count() > 0:
            await link.first.click()
            try:
                await page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                await page.wait_for_load_state("load", timeout=15000)

    await go_to_tab()

    # Some tabs render slowly; poll for stable non-error content before extraction.
    settle_timeout_s = int(os.getenv("TAB_SETTLE_TIMEOUT_SECONDS", "45"))
    settle_sleep_s = float(os.getenv("TAB_SETTLE_POLL_SECONDS", "1.5"))
    deadline = time.time() + settle_timeout_s
    saw_runtime_error = False

    while time.time() < deadline:
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass

        try:
            html = await page.content()
        except Exception:
            await asyncio.sleep(settle_sleep_s)
            continue
        is_runtime_error = is_runtime_error_page_html(html)

        if is_runtime_error:
            saw_runtime_error = True
            # Runtime pages are often transient; recover by returning to Summary and re-clicking tab.
            url = page.url
            if "q=" in url and tab_lower in postback_target:
                token = url.split("q=")[-1]
                try:
                    await page.goto(f"{BASE_URL}/CR_CaseInformation_Summary.aspx?q={token}", wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(0.8)
                    await go_to_tab()
                except Exception:
                    pass
            await asyncio.sleep(settle_sleep_s)
            continue

        try:
            if await page.locator("table").count() > 0:
                await asyncio.sleep(1.0)
                return
        except Exception:
            pass

        await asyncio.sleep(settle_sleep_s)

    # Confirm the table appears; if not, log loudly and continue
    console.print(f"[yellow]'{tab_name}' tab did not render a stable table in time — continuing anyway[/yellow]")
    if saw_runtime_error:
        console.print(f"[yellow]'{tab_name}' tab repeatedly showed runtime error while loading[/yellow]")
    (Path("out")/f"debug_no_table_{tab_name.lower()}.html").write_text(await page.content(), encoding="utf-8")

# Removed save_html function - HTML content now stored in JSON structure

def parse_co_defendants(summary_fields: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse co-defendants from summary co-defendants field"""
    co_def_text = summary_fields.get("Co-Defendants:", "N/A")
    if co_def_text == "N/A" or not co_def_text or co_def_text.strip() == "":
        return []
    
    # Parse linked case numbers
    # Format: <a href='...'>CR-25-123456-A</a>, <a href='...'>CR-25-123457-A</a>
    case_numbers = re.findall(r'(CR-\d{2}-\d{6}-[A-Z])', str(co_def_text))
    
    # Also try to extract names if present
    co_defendants = []
    for case_num in case_numbers:
        co_defendants.append({
            "case_number": case_num,
            "relationship": "Co-defendant"
        })
    
    return co_defendants

def parse_charge_disposition(charges_data: Any) -> List[Dict[str, Any]]:
    """Parse charges and extract disposition information"""
    charges = []
    
    # Handle embedded table format
    if isinstance(charges_data, dict) and "embedded_table" in str(charges_data):
        for key, value in charges_data.items():
            if "embedded_table" in key and isinstance(value, dict):
                if value.get("format") == "csv" and "data" in value:
                    import csv
                    from io import StringIO
                    reader = csv.DictReader(StringIO(value["data"]))
                    for row in reader:
                        charge = {
                            "type": (row.get("Type") or "").strip(),
                            "statute": (row.get("Statute") or "").strip(),
                            "charge_description": (row.get("Charge Description") or "").strip(),
                            "disposition": (row.get("Disposition") or "").strip() or None,
                            "disposition_date": None,
                            "plea": None,
                            "verdict": None,
                            "sentence": None
                        }
                        if charge["type"] or charge["statute"]:
                            charges.append(charge)
    
    return charges

def parse_bond_information(summary_fields: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse bond information from summary embedded tables"""
    bonds = []
    
    # Look for embedded tables - iterate all embedded_table_N keys
    for key, value in summary_fields.items():
        if "embedded_table" in key and isinstance(value, dict) and value.get("format") == "csv":
            import csv
            from io import StringIO
            # Check if this table has bond columns
            if "Bond Number" in value.get("data", "") or "Amount" in value.get("data", ""):
                reader = csv.DictReader(StringIO(value["data"]))
                for row in reader:
                    bond = {
                        "bond_number": (row.get("Bond Number") or row.get("Number") or "").strip(),
                        "amount": (row.get("Amount") or "").strip(),
                        "type": (row.get("Type") or "").strip(),
                        "date_set": (row.get("Date Set") or "").strip() or None,
                        "date_posted": (row.get("Date Posted") or "").strip() or None,
                        "posted_by": (row.get("Bondsman/Surety Co.") or row.get("Posted By") or "").strip() or None
                    }
                    if bond["bond_number"] or bond["amount"]:
                        bonds.append(bond)
    
    return bonds

def parse_case_actions(summary_fields: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse case actions/events timeline from summary embedded tables"""
    actions = []
    
    # Look for embedded tables - iterate all embedded_table_N keys
    for key, value in summary_fields.items():
        if "embedded_table" in key and isinstance(value, dict) and value.get("format") == "csv":
            import csv
            from io import StringIO
            # Check if this table has event columns
            if "Event Date" in value.get("data", "") or "Event Description" in value.get("data", ""):
                reader = csv.DictReader(StringIO(value["data"]))
                for row in reader:
                    action = {
                        "date": (row.get("Event Date") or row.get("Date") or "").strip() or None,
                        "event": (row.get("Event Description") or row.get("Event") or row.get("Action") or "").strip()
                    }
                    if action["date"] and action["event"]:
                        actions.append(action)
    
    return actions

def extract_prosecutor_from_docket(docket_entries: List[Dict[str, Any]]) -> Optional[str]:
    """Extract prosecutor name from docket entry text"""
    # Look for patterns like "PROSECUTING ATTORNEY(S) [NAME]", "PROSECUTOR(S) [NAME]", "PROSECUTOR [NAME]"
    for entry in docket_entries:
        # Combine all column values to search, prioritizing description field
        description = entry.get("description", "")
        if not description:
            # Fallback to combining all values
            description = " ".join(str(v) for v in entry.values() if v)
        
        # Pattern: PROSECUTING ATTORNEY(S) [NAME] or PROSECUTOR(S) [NAME]
        matches = re.findall(r'PROSECUT(?:ING ATTORNEY|OR)\(S\)?\s+([A-Z]+(?:\s+[A-Z]+)+)', description, re.IGNORECASE)
        if matches:
            # Return the first match, cleaned up
            name = matches[0].strip()
            # Remove common trailing words
            name = re.sub(r'\s+(PRESENT|IN\s+COURT|ADDRESSES|THE).*$', '', name, flags=re.IGNORECASE).strip()
            # Filter out if too short or contains obviously wrong patterns
            if name and len(name) > 5:
                return name
    
    return None

async def extract_summary(page: Page) -> Dict[str, Any]:
    """Extract the summary section with co-defendants, charges, bonds, and case actions"""
    html = await page.content()
    case_id = None
    m = re.search(r"(CR-\d{2}-\d{6}-[A-Z])", html)
    if m:
        case_id = m.group(1)
    data = {"case_id": case_id}
    try:
        kv = await kv_from_table(page, "table")
        if kv:
            data["fields"] = kv
            
            # Parse co-defendants
            data["co_defendants"] = parse_co_defendants(kv)
            data["is_multi_defendant_case"] = len(data["co_defendants"]) > 0
            
            # Parse charges with dispositions
            charges = parse_charge_disposition(kv)
            if charges:
                data["charges"] = charges
            
            # Parse bond information
            bonds = parse_bond_information(kv)
            if bonds:
                data["bonds"] = bonds
            
            # Parse case actions timeline
            actions = parse_case_actions(kv)
            if actions:
                data["case_actions"] = actions
            
            # Extract current judge
            current_judge = kv.get("Judge Name:", None)
            if current_judge:
                data["current_judge"] = current_judge
                
    except Exception as e:
        console.print(f"[yellow]⚠ Partial summary extraction due to context issue: {str(e)[:100]}[/yellow]")
    return data

async def extract_docket(page: Page) -> List[Dict[str, Any]]:
    """Extract docket table entries using the same approach as extract_docket_with_pdfs"""
    try:
        docket_entries = []

        # Guard against parsing ASP.NET runtime error pages as docket rows.
        html = await page.content()
        if is_runtime_error_page_html(html):
            return []
        
        # Look for the docket table using the specific selectors
        table = page.locator("table.gridview, table#SheetContentPlaceHolder_caseDocket_gvDocketInformation")
        
        if await table.count() == 0:
            # Fallback to generic grid extraction, but reject runtime-error payloads.
            generic_rows = await grid_from_table(page, "table")
            if docket_entries_look_like_runtime_error(generic_rows):
                return []
            return generic_rows
        
        # Get all rows except header (first row is header)
        rows = table.locator("tr").nth(1).locator("~ tr")  # Skip header row
        
        row_count = 0
        try:
            row_count = await rows.count()
        except Exception:
            pass
        
        if row_count == 0:
            # Try alternate selector, but reject runtime-error payloads.
            generic_rows = await grid_from_table(page, "table")
            if docket_entries_look_like_runtime_error(generic_rows):
                return []
            return generic_rows
        
        for i in range(row_count):
            try:
                row = rows.nth(i)
                cells = row.locator("td")
                cell_count = await cells.count()
                
                if cell_count < 2:
                    # Skip rows with too few columns
                    continue
                
                # Extract columns with proper names based on docket format
                # Format: Date | Date | Who | What (DocType) | What (Message) | Additional
                entry = {}
                column_names = ["proceeding_date", "filing_date", "party", "document_type", "description", "additional"]
                for j in range(cell_count):
                    try:
                        cell_text = (await cells.nth(j).inner_text()).strip()
                        col_name = column_names[j] if j < len(column_names) else f"col{j+1}"
                        entry[col_name] = cell_text
                    except Exception:
                        col_name = column_names[j] if j < len(column_names) else f"col{j+1}"
                        entry[col_name] = ""
                
                # Add all non-empty rows (filtering can happen in consumers)
                docket_entries.append(entry)
            except Exception:
                # If a single row fails, continue with next
                continue
        
        if docket_entries_look_like_runtime_error(docket_entries):
            return []
        return docket_entries
    except Exception as e:
        console.print(f"[yellow]⚠ Docket extraction error: {str(e)[:100]}[/yellow]")
        return []

async def extract_docket_with_pdfs(page: Page) -> List[Dict[str, Any]]:
    """Extract docket entries and include PDF download links"""
    docket_entries = []
    
    try:
        # Wait for page to stabilize and ensure we're on the right content
        await asyncio.sleep(1.0)
        await page.wait_for_load_state("domcontentloaded", timeout=10000)

        html = await page.content()
        if is_runtime_error_page_html(html):
            return []
        
        # Look for the docket table
        table = page.locator("table.gridview, table#SheetContentPlaceHolder_caseDocket_gvDocketInformation")
        
        # Wait for table to be present - increased timeout for large dockets
        try:
            await table.first.wait_for(state="visible", timeout=10000)
        except:
            console.print("[yellow]Docket table not visible, trying alternate extraction[/yellow]")
            generic_rows = await grid_from_table(page, "table")
            if docket_entries_look_like_runtime_error(generic_rows):
                return []
            return generic_rows
        
        if await table.count() == 0:
            console.print("[yellow]No docket table found[/yellow]")
            generic_rows = await grid_from_table(page, "table")
            if docket_entries_look_like_runtime_error(generic_rows):
                return []
            return generic_rows
        
        # Get all rows except header
        rows = table.locator("tr").nth(1).locator("~ tr")  # Skip header row
        row_count = await rows.count()
        
        for i in range(row_count):
            try:
                row = rows.nth(i)
                cells = row.locator("td")
                cell_count = await cells.count()
                
                if cell_count >= 6:  # Expected columns
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
            except Exception as row_err:
                console.print(f"[yellow]⚠ Error extracting docket row {i}: {str(row_err)[:80]}[/yellow]")
                continue
        
        if docket_entries_look_like_runtime_error(docket_entries):
            return []
        return docket_entries
        
    except Exception as e:
        console.print(f"[yellow]⚠ Docket extraction with PDFs failed, using fallback: {str(e)[:100]}[/yellow]")
        # Fallback to regular grid extraction
        try:
            return await grid_from_table(page, "table")
        except:
            return []

async def download_pdf_with_playwright(page: Page, pdf_link: str, output_path: Path, filename: str) -> bool:
    """Download a PDF file using the authenticated Playwright browser session
    
    Uses the browser's context.request API to directly fetch the PDF, bypassing
    the embedded viewer entirely.
    """
    try:
        console.print(f"[blue]Downloading PDF: {filename}[/blue]")
        
        # Navigate to the PDF link using the same authenticated session
        full_url = f"{BASE_URL}/{pdf_link}" if not pdf_link.startswith("http") else pdf_link
        
        context = page.context
        
        #Try direct fetch via context.request (uses same cookies/session)
        try:
            response = await context.request.get(full_url, timeout=30000)
            
            if response.status == 200:
                content_type = response.headers.get('content-type', '').lower()
                body = await response.body()
                
                # Check if we got actual PDF
                if body.startswith(b'%PDF'):
                    output_file = output_path / filename
                    output_file.write_bytes(body)
                    file_size = output_file.stat().st_size
                    console.print(f"[green]✓ Downloaded {filename} ({file_size/1024:.1f}KB)[/green]")
                    return True
                
                # If we got HTML instead, it contains an embed element
                # Extract the actual PDF URL from the HTML page using JavaScript
                pdf_page = await context.new_page()
                try:
                    await pdf_page.goto(full_url, wait_until="load", timeout=45000)
                    
                    # Wait for embed element to appear
                    await asyncio.sleep(2.0)
                    
                    # Try to find the actual PDF URL by examining all iframes and checking for PDF content
                    actual_pdf_url = await pdf_page.evaluate("""
                        () => {
                            // Check all embed elements
                            const embeds = document.querySelectorAll('embed[type="application/pdf"]');
                            for (const embed of embeds) {
                                const src = embed.getAttribute('src');
                                if (src && src !== 'about:blank') {
                                    return src;
                                }
                            }
                            
                            // Check iframes
                            const iframes = document.querySelectorAll('iframe');
                            for (const iframe of iframes) {
                                const src = iframe.getAttribute('src');
                                if (src && (src.includes('.pdf') || src.includes('DisplayDoc'))) {
                                    return src;
                                }
                            }
                            
                            // Look for PDF links in page
                            const links = document.querySelectorAll('a[href*=".pdf"], a[href*="DisplayDoc"]');
                            if (links.length > 0) {
                                return links[0].href;
                            }
                            
                            return null;
                        }
                    """)
                    
                    if actual_pdf_url and actual_pdf_url != "about:blank":
                        # Build full URL if needed
                        if not actual_pdf_url.startswith('http'):
                            actual_pdf_url = f"{BASE_URL}/{actual_pdf_url}"
                        
                        # Fetch the actual PDF
                        pdf_response = await context.request.get(actual_pdf_url, timeout=30000)
                        if pdf_response.status == 200:
                            pdf_data = await pdf_response.body()
                            if pdf_data.startswith(b'%PDF'):
                                output_file = output_path / filename
                                output_file.write_bytes(pdf_data)
                                file_size = output_file.stat().st_size
                                console.print(f"[green]✓ Downloaded {filename} ({file_size/1024:.1f}KB)[/green]")
                                return True
                    
                    console.print(f"[yellow]⚠ {filename}: No actual PDF URL found in page[/yellow]")
                    return False
                    
                finally:
                    await pdf_page.close()
            
            # If we reach here, direct request didn't return PDF
            console.print(f"[yellow]⚠ {filename}: Response not a PDF[/yellow]")
            return False
                    
        except Exception as req_err:
            console.print(f"[red]✗ Request error for {filename}: {req_err}[/red]")
            return False
            
    except Exception as e:
        console.print(f"[red]✗ Error downloading {filename}: {e}[/red]")
        return False

async def download_case_pdfs(page: Page, docket_entries: List[Dict[str, Any]], case_id: str, 
                           pdf_dir: Path, sentencing_only: bool = True) -> Dict[str, Any]:
    """Download PDFs for a case using the authenticated browser session
    
    Args:
        page: Playwright page object
        docket_entries: List of docket entries with PDF links
        case_id: Case identifier (e.g., CR-23-684826-A)
        pdf_dir: Base directory for PDF storage
        sentencing_only: If True, only download sentencing/judgment entries (JE). Default True.
    """
    pdf_info = {
        "total_pdfs": 0,
        "downloaded": 0,
        "failed": 0,
        "skipped": 0,
        "files": []
    }
    
    # Create case-specific PDF directory
    case_pdf_dir = pdf_dir / case_id
    case_pdf_dir.mkdir(parents=True, exist_ok=True)
    
    # Filter for PDFs
    pdf_entries = [entry for entry in docket_entries if entry.get("pdf_link")]
    
    # If sentencing_only, filter for JE documents
    if sentencing_only:
        pdf_entries = [
            entry for entry in pdf_entries 
            if entry.get("docket_type", entry.get("document_type", "")).upper() in ("JE", "SENTENCING", "JUDGMENT ENTRY")
        ]
        console.print(f"[cyan]Found {len(pdf_entries)} sentencing PDFs for case {case_id}[/cyan]")
    else:
        console.print(f"[cyan]Found {len(pdf_entries)} PDFs for case {case_id}[/cyan]")
    
    pdf_info["total_pdfs"] = len(pdf_entries)
    
    if not pdf_entries:
        if sentencing_only:
            console.print(f"[blue]ℹ No sentencing PDFs found for case {case_id}[/blue]")
        else:
            console.print(f"[yellow]No PDFs found for case {case_id}[/yellow]")
        return pdf_info
    
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
    """Extract costs table with robust retry and context destruction recovery"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Wait for costs table to be fully loaded and visible
            await page.wait_for_selector("table.gridview", state="visible", timeout=10000)
            await asyncio.sleep(1.5)  # Additional stabilization time
            
            # Verify context is still alive
            await page.evaluate("1")
            
            costs = await grid_from_table(page, "table.gridview")
            if costs:
                return costs
            
            # If no costs found, check for "no costs" message
            content = await page.content()
            if re.search(r'no.*costs.*found|no.*costs.*exist', content, re.I):
                console.print("[dim]No costs present according to page content[/dim]")
                return []
                
        except PWTimeout:
            # No costs table present
            console.print("[dim]No costs table found on page[/dim]")
            return []
        except Exception as e:
            if "context" in str(e).lower() or "destroyed" in str(e).lower():
                if attempt < max_retries - 1:
                    console.print(f"[yellow]⚠ Context destroyed during costs extraction (attempt {attempt+1}/{max_retries}), retrying...[/yellow]")
                    await asyncio.sleep(2.0)
                    # Try to re-open the Costs tab
                    try:
                        await open_tab(page, "Costs")
                        await asyncio.sleep(1.0)
                    except:
                        pass
                    continue
            
            console.print(f"[yellow]⚠ Partial costs extraction due to error: {str(e)[:100]}[/yellow]")
            return []
    
    console.print(f"[yellow]⚠ Costs extraction failed after {max_retries} attempts[/yellow]")
    return []

async def extract_defendant(page: Page) -> Dict[str, Any]:
    """Extract defendant info with context destruction recovery"""
    try:
        return await kv_from_table(page, "table")
    except Exception as e:
        console.print(f"[yellow]⚠ Partial defendant extraction due to context issue: {str(e)[:100]}[/yellow]")
        return {}

def classify_attorney_party(attorney_name: str, case_title: str = "") -> str:
    """Classify attorney as Defense, Prosecution, or State"""
    attorney_lower = attorney_name.lower()
    case_lower = case_title.lower()
    
    # Prosecution indicators
    prosecution_keywords = [
        "prosecutor", "prosecuting attorney", "assistant prosecutor",
        "state of ohio", "o'malley", "michael c. o'malley",
        "asst prosecutor", "asst. prosecutor", "county prosecutor"
    ]
    
    if any(kw in attorney_lower for kw in prosecution_keywords):
        return "Prosecution"
    
    # Check if case title mentions "State of Ohio" - helps identify prosecutors
    if "state of ohio" in case_lower and "assistant" in attorney_lower:
        return "Prosecution"
    
    # Defense is default for listed attorneys not identified as prosecution
    return "Defense"

def extract_attorney_role(attorney_data: Dict[str, Any], contact_info: str = "") -> str:
    """Extract attorney role from available information"""
    contact_lower = contact_info.lower()
    name_lower = attorney_data.get("name", "").lower()
    
    # Role indicators in contact/description
    if "public defender" in contact_lower or "public defender" in name_lower:
        return "Public Defender"
    if "appointed" in contact_lower:
        return "Appointed Counsel"
    if "lead" in contact_lower or "lead" in name_lower:
        return "Lead Counsel"
    if "co-counsel" in contact_lower:
        return "Co-counsel"
    
    # Default
    return "Attorney of Record"

async def extract_attorneys(page: Page, case_title: str = "", docket_entries: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Extract attorney information with party classification - handles ViewState format"""
    attorneys = []
    
    try:
        # Get the page HTML
        html = await page.content()
        
        # Try extracting from span elements with specific IDs first (more reliable)
        # Pattern: SheetContentPlaceHolder_attyInfo_gvAttyInfo_lblName_N
        name_pattern = r'<span id="[^"]*lblName_(\d+)"[^>]*>(.*?)</span>'
        address_pattern = r'<span id="[^"]*lblAddress\d+_(\d+)"[^>]*>(.*?)</span>'
        phone_pattern = r'<span id="[^"]*lblPhone_(\d+)"[^>]*>(.*?)</span>'
        
        # Extract all names, addresses, and phones with their indices
        names = {int(m.group(1)): m.group(2).strip() for m in re.finditer(name_pattern, html)}
        addresses = {}
        for m in re.finditer(address_pattern, html):
            idx = int(m.group(1))
            if idx not in addresses:
                addresses[idx] = []
            addresses[idx].append(m.group(2).strip())
        phones = {int(m.group(1)): m.group(2).strip() for m in re.finditer(phone_pattern, html)}
        
        # Combine data for each attorney by index
        for idx in sorted(names.keys()):
            name = names[idx]
            
            # Build contact info
            contact_parts = []
            if idx in addresses:
                contact_parts.extend(addresses[idx])
            if idx in phones:
                contact_parts.append(phones[idx])
            
            attorney = {
                'name': name,
                'contact': '\n'.join(contact_parts) if contact_parts else None,
                'party': classify_attorney_party(name, case_title),
                'role': 'Attorney of Record',
                'type': 'Retained'
            }
            
            # Try to extract role from contact info
            if contact_parts:
                attorney['role'] = extract_attorney_role(attorney, '\n'.join(contact_parts))
            
            attorneys.append(attorney)
        
        # If pattern matching didn't work, try grid extraction
        if not attorneys:
            try:
                raw_rows = await grid_from_table(page, "table")
            except Exception as e:
                console.print(f"[yellow]⚠ Attorney grid extraction failed: {str(e)[:100]}[/yellow]")
                raw_rows = []

            current_attorney = {}

            for row in raw_rows:
                # Flatten the row values
                row_text = ' '.join([str(v).strip() for v in row.values() if v]).strip()

                # Skip empty rows, headers, and navigation elements
                if not row_text or ('Attorney' in row_text and 'Information' in row_text):
                    continue
                if any(x in row_text for x in ['Case Summary', 'Docket', 'Costs', 'Defendant', 'New Search', 'Post Bond', 'Cuyahoga County', 'Clerk of Courts']):
                    continue

                # Look for attorney name patterns
                if 'Attorney Name' in row_text and 'Address' not in row_text:
                    # Extract just the name
                    if current_attorney and 'name' in current_attorney and current_attorney['name']:
                        # Classify party and role before appending
                        current_attorney['party'] = classify_attorney_party(current_attorney['name'], case_title)
                        current_attorney['role'] = extract_attorney_role(current_attorney, current_attorney.get('contact', ''))
                        current_attorney['type'] = 'Retained'
                        attorneys.append(current_attorney)
                    current_attorney = {}
                    parts = row_text.split('Attorney Name')
                    if len(parts) > 1:
                        name = parts[-1].strip().split('\n')[0].strip()
                        if name and len(name) > 2:
                            current_attorney['name'] = name

                # Look for address/phone
                elif 'Address/Phone' in row_text and current_attorney:
                    parts = row_text.split('Address/Phone')
                    if len(parts) > 1:
                        addr_phone = parts[-1].strip()
                        current_attorney['contact'] = addr_phone

            # Don't forget the last attorney
            if current_attorney and 'name' in current_attorney and current_attorney['name']:
                # Classify party and role
                current_attorney['party'] = classify_attorney_party(current_attorney['name'], case_title)
                current_attorney['role'] = extract_attorney_role(current_attorney, current_attorney.get('contact', ''))
                current_attorney['type'] = 'Retained'  # Default, can be enhanced with more data
                attorneys.append(current_attorney)
    
    except Exception as e:
        console.print(f"[yellow]⚠ Attorney extraction error: {str(e)[:150]}[/yellow]")
    
    # Add prosecutor from case title if not already in list
    if "STATE OF OHIO" in case_title.upper():
        # Check if we already have a prosecutor
        has_prosecutor = any(att.get('party') == 'Prosecution' for att in attorneys)
        if not has_prosecutor:
            # Try to extract actual prosecutor name from docket
            prosecutor_name = None
            if docket_entries:
                prosecutor_name = extract_prosecutor_from_docket(docket_entries)
            
            if prosecutor_name:
                attorneys.append({
                    'name': prosecutor_name,
                    'party': 'Prosecution',
                    'role': 'Assistant Prosecuting Attorney',
                    'type': 'State Attorney',
                    'contact': None,
                    'office': 'Cuyahoga County Prosecutor'
                })
            else:
                # Fallback to generic prosecutor
                attorneys.append({
                    'name': 'Cuyahoga County Prosecutor',
                    'party': 'Prosecution',
                    'role': 'Prosecuting Attorney',
                    'type': 'State Attorney',
                    'contact': None,
                    'office': 'Cuyahoga County Prosecutor'
                })

    # If we found nothing via grid parsing, try a safer HTML fallback that
    #  - returns [] if the page explicitly says "No attorneys found"
    #  - targets only tables likely to contain attorney rows (ids/classes containing atty/attorney/gvAttyInfo)
    #  - parses <tr>/<td> rows and ignores navigation/header links
    if not attorneys:
        try:
            html = await page.content()

            # If page explicitly says there are no attorneys, return empty quickly
            if re.search(r'no\s+attorneys\s+found', html, flags=re.I):
                console.print("[blue]No attorneys present according to page content[/blue]")
                return []

            # Collect table blocks
            table_blocks = re.findall(r'(<table[\s\S]*?</table>)', html, flags=re.I)
            candidate_tables = []

            # Prefer tables specifically mentioning attorney/atty
            for tbl in table_blocks:
                if re.search(r'(atty|attorney|gvAttyInfo|Atty)', tbl, flags=re.I):
                    if re.search(r'no\s+attorneys\s+found', tbl, flags=re.I):
                        continue
                    candidate_tables.append(tbl)

            # If none found, fall back to any gridview table that is not the global nav
            if not candidate_tables:
                for tbl in table_blocks:
                    if 'gridview' in tbl.lower() and not re.search(r'no\s+attorneys\s+found', tbl, flags=re.I):
                        candidate_tables.append(tbl)

            # Parse candidate tables row-by-row, extracting name and contact heuristically
            for tbl in candidate_tables:
                rows = re.findall(r'<tr[\s\S]*?</tr>', tbl, flags=re.I)
                for tr in rows:
                    # Extract all td/th cell contents for the row
                    tds = re.findall(r'<t[dh][^>]*>([\s\S]*?)</t[dh]>', tr, flags=re.I)
                    cells = [re.sub(r'<[^>]+>', ' ', td).strip() for td in tds if td and td.strip()]
                    if not cells:
                        continue

                    # Heuristic: skip rows that are clearly headers or nav links
                    header_like = all(re.search(r'^(Attorney|Name|Address|Phone|No attorneys found|Case Summary|Docket|Costs|Defendant|New Search)$', c.strip(), flags=re.I) or not re.search(r'[A-Za-z]', c) for c in cells)
                    if header_like:
                        continue

                    # Skip rows that are navigation or site chrome
                    if any(x.lower() in cells[0].lower() for x in ['case summary', 'new search', 'docket', 'costs', 'defendant', 'clerk of courts']):
                        continue

                    # Choose first non-empty cell as name, second as contact if present
                    name = cells[0]
                    contact = cells[1] if len(cells) > 1 else ''

                    # Validate name looks reasonable (contains letters and a space)
                    if len(name) > 2 and re.search(r'[A-Za-z]', name):
                        attorneys.append({'name': name, 'contact': contact})

                if attorneys:
                    break

        except Exception as e:
            console.print(f"[yellow]⚠ Attorney HTML fallback failed: {e}[/yellow]")

    # Deduplicate by name
    seen_names = set()
    unique_attorneys = []
    for att in attorneys:
        name = (att.get('name') or '').strip()
        if name and name not in seen_names:
            seen_names.add(name)
            unique_attorneys.append(att)

    return unique_attorneys

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

class CaseTracker:
    """Track all cases sequentially with missing/errored status"""
    def __init__(self, year: int, start: int, end: int, out_dir: Path):
        self.year = year
        self.start = start
        self.end = end
        self.out_dir = out_dir
        self.successes = set()  # Cases that downloaded successfully
        self.missing = set()    # Cases that don't exist (no case found)
        self.errored = set()    # Cases that had errors during download
        self.total_range = end - start + 1
        
    def add_success(self, number: int):
        self.successes.add(number)
        
    def add_missing(self, number: int):
        self.missing.add(number)
        
    def add_error(self, number: int):
        self.errored.add(number)
        
    def save_logs(self):
        """Save missing and errored case logs"""
        logs_dir = self.out_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Save missing cases log
        if self.missing:
            missing_log = logs_dir / f"{self.year}_missing.txt"
            missing_log.write_text(
                "\n".join(f"{self.year}-{n:06d}" for n in sorted(self.missing)) + "\n"
            )
            
        # Save errored cases log
        if self.errored:
            errored_log = logs_dir / f"{self.year}_errored.txt"
            errored_log.write_text(
                "\n".join(f"{self.year}-{n:06d}" for n in sorted(self.errored)) + "\n"
            )
            
    def get_stats(self) -> Dict[str, int]:
        """Return tracking statistics"""
        accounted = len(self.successes) + len(self.missing) + len(self.errored)
        return {
            "total_range": self.total_range,
            "successfully_downloaded": len(self.successes),
            "missing_cases": len(self.missing),
            "errored_cases": len(self.errored),
            "total_accounted": accounted,
            "unaccounted": self.total_range - accounted,
        }

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
        "co_defendants": [],
        "bonds": [],
        "case_actions": [],
        "judge_history": [],
        "outcome": {
            "final_status": "PENDING",
            "disposition_date": None,
            "disposing_judge": None,
            "plea_deal": None,
            "sentence": None,
            "appeal_filed": False,
            "appeal_case_number": None
        },
        "errors": [],
        "html_snapshots": {},
        "pdf_info": None
    }
    
    try:
        # Search with timeout - if search takes too long, skip case
        try:
            case_id = await asyncio.wait_for(search_case(page, year, number), timeout=60.0)
        except asyncio.TimeoutError:
            console.print(f"[red]✗ Case search timeout for {year}-{number:06d} (>60s)[/red]")
            case_data["metadata"]["exists"] = False
            case_data["metadata"]["case_id"] = None
            case_data["errors"].append({
                "type": "case_search_timeout",
                "message": "Search operation exceeded 60 second timeout",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            # Try to recover by going back to search page
            try:
                await navigate_to_search(page)
            except:
                console.print("[yellow]Could not recover to search page after timeout[/yellow]")
            return case_data
            
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
            try:
                await open_tab(page, "Summary")
            except Exception as tab_err:
                console.print(f"[yellow]⚠ Could not open Summary tab, attempting extraction anyway: {str(tab_err)[:80]}[/yellow]")
            
            # Check context is alive before capturing HTML
            try:
                await page.evaluate("1")
                case_data["html_snapshots"]["summary"] = await page.content()
            except Exception:
                case_data["html_snapshots"]["summary"] = "[context_destroyed_during_snapshot]"
            
            summary_data = await extract_summary(page)
            case_data["summary"] = summary_data
            
            # Extract co-defendants from summary
            if "co_defendants" in summary_data:
                case_data["co_defendants"] = summary_data["co_defendants"]
            
            # Extract bonds from summary
            if "bonds" in summary_data:
                case_data["bonds"] = summary_data["bonds"]
            
            # Extract case actions from summary
            if "case_actions" in summary_data:
                case_data["case_actions"] = summary_data["case_actions"]
            
            # Extract current judge and initialize judge history
            if "current_judge" in summary_data and summary_data["current_judge"]:
                case_data["judge_history"].append({
                    "judge_name": summary_data["current_judge"],
                    "assigned_date": None,  # Will try to extract from docket
                    "assignment_type": "Current",
                    "current": True
                })
            
            console.print("[green]✓ Summary extracted[/green]")
        except Exception as e:
            console.print(f"[red]✗ Summary extraction failed: {e}[/red]")
            case_data["errors"].append({
                "type": "summary_extraction_error",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        polite_delay(DEFAULT_DELAY)

        # Capture printer-friendly PDFs for the current tab (Summary)
        try:
            await capture_printer_pdfs_on_page(page, out_root, case_id, case_data)
        except Exception as eprint:
            console.print(f"[yellow]⚠ Printer-friendly PDF capture failed: {str(eprint)[:160]}[/yellow]")
        # Extract Docket
        try:
            try:
                await open_tab(page, "Docket")
                # Give the docket content time to load fully - increased for large dockets (90+ entries)
                await asyncio.sleep(5.0)
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
                # Extra wait for dynamic content/tables to populate
                await page.wait_for_selector("table", timeout=15000)
                # Additional wait for table content to finish rendering (important for large dockets)
                await asyncio.sleep(2.0)
            except Exception as tab_err:
                console.print(f"[yellow]⚠ Could not open Docket tab, attempting extraction anyway: {str(tab_err)[:80]}[/yellow]")
            
            # Check context is alive before capturing HTML
            try:
                await page.evaluate("1")
                case_data["html_snapshots"]["docket"] = await page.content()
            except Exception:
                case_data["html_snapshots"]["docket"] = "[context_destroyed_during_snapshot]"
            
            # Use PDF-aware extraction if downloading PDFs, otherwise use regular extraction
            if download_pdfs and (not case_id_filter or case_id in case_id_filter):
                case_data["docket"] = await extract_docket_with_pdfs(page)
                console.print(f"[green]✓ Docket extracted with PDF links ({len(case_data['docket'])} entries)[/green]")
                
                # Download PDFs if requested (sentencing entries only by default)
                try:
                    pdf_dir = out_root / "pdfs"
                    pdf_info = await download_case_pdfs(page, case_data["docket"], case_id, pdf_dir, sentencing_only=True)
                    case_data["pdf_info"] = pdf_info
                    if pdf_info["downloaded"] > 0:
                        console.print(f"[green]✓ Sentencing PDFs: {pdf_info['downloaded']}/{pdf_info['total_pdfs']} downloaded[/green]")
                    elif pdf_info["total_pdfs"] == 0:
                        console.print(f"[blue]ℹ No sentencing PDFs to download[/blue]")
                    else:
                        console.print(f"[yellow]⚠ PDFs: 0/{pdf_info['total_pdfs']} downloaded (all failed)[/yellow]")
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
        # Capture printer-friendly PDF for Docket tab (if present)
        try:
            await capture_printer_pdfs_on_page(page, out_root, case_id, case_data)
        except Exception as eprint:
            console.print(f"[yellow]⚠ Docket printer capture failed: {str(eprint)[:160]}[/yellow]")

        polite_delay(DEFAULT_DELAY)

        # Extract Costs
        try:
            try:
                await open_tab(page, "Costs")
            except Exception as tab_err:
                console.print(f"[yellow]⚠ Could not open Costs tab, attempting extraction anyway: {str(tab_err)[:80]}[/yellow]")
            
            # Check context is alive before capturing HTML
            try:
                await page.evaluate("1")
                case_data["html_snapshots"]["costs"] = await page.content()
            except Exception:
                case_data["html_snapshots"]["costs"] = "[context_destroyed_during_snapshot]"
            
            case_data["costs"] = await extract_costs(page)
            console.print(f"[green]✓ Costs extracted ({len(case_data['costs'])} entries)[/green]")
        except Exception as e:
            console.print(f"[red]✗ Costs extraction failed: {e}[/red]")
            case_data["errors"].append({
                "type": "costs_extraction_error",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        # Capture printer-friendly PDF for Costs tab (if present)
        try:
            await capture_printer_pdfs_on_page(page, out_root, case_id, case_data)
        except Exception as eprint:
            console.print(f"[yellow]⚠ Costs printer capture failed: {str(eprint)[:160]}[/yellow]")

        polite_delay(DEFAULT_DELAY)

        # Extract Defendant
        try:
            try:
                await open_tab(page, "Defendant")
            except Exception as tab_err:
                console.print(f"[yellow]⚠ Could not open Defendant tab, attempting extraction anyway: {str(tab_err)[:80]}[/yellow]")
            
            # Check context is alive before capturing HTML
            try:
                await page.evaluate("1")
                case_data["html_snapshots"]["defendant"] = await page.content()
            except Exception:
                case_data["html_snapshots"]["defendant"] = "[context_destroyed_during_snapshot]"
            
            case_data["defendant"] = await extract_defendant(page)
            console.print("[green]✓ Defendant extracted[/green]")
        except Exception as e:
            console.print(f"[red]✗ Defendant extraction failed: {e}[/red]")
            case_data["errors"].append({
                "type": "defendant_extraction_error",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        # Capture printer-friendly PDF for Defendant tab (if present)
        try:
            await capture_printer_pdfs_on_page(page, out_root, case_id, case_data)
        except Exception as eprint:
            console.print(f"[yellow]⚠ Defendant printer capture failed: {str(eprint)[:160]}[/yellow]")

        polite_delay(DEFAULT_DELAY)

        # Extract Attorneys
        try:
            try:
                await open_tab(page, "Attorney")
                # Give extra time for attorney page to fully load
                await asyncio.sleep(1.5)
            except Exception as tab_err:
                console.print(f"[yellow]⚠ Could not open Attorney tab, attempting extraction anyway: {str(tab_err)[:80]}[/yellow]")
            
            # Check context is alive before capturing HTML
            try:
                await page.evaluate("1")
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
                case_data["html_snapshots"]["attorneys"] = await page.content()
            except Exception as html_err:
                console.print(f"[yellow]⚠ Attorney HTML snapshot failed: {str(html_err)[:80]}[/yellow]")
                case_data["html_snapshots"]["attorneys"] = "[context_destroyed_during_snapshot]"
            
            # Get case title for attorney classification
            case_title = case_data.get("summary", {}).get("fields", {}).get("Case Title:", "") or ""
            if not case_title:
                # Try to construct from case ID
                case_id = case_data.get("metadata", {}).get("case_id", "")
                if case_id:
                    case_title = f"THE STATE OF OHIO vs. [DEFENDANT]"
            
            case_data["attorneys"] = await extract_attorneys(page, case_title, case_data.get("docket", []))
            console.print(f"[green]✓ Attorneys extracted ({len(case_data['attorneys'])} entries)[/green]")
        except Exception as e:
            console.print(f"[red]✗ Attorneys extraction failed: {e}[/red]")
            case_data["errors"].append({
                "type": "attorneys_extraction_error",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        # Capture printer-friendly PDF for Attorney tab (if present)
        try:
            await capture_printer_pdfs_on_page(page, out_root, case_id, case_data)
        except Exception as eprint:
            console.print(f"[yellow]⚠ Attorney printer capture failed: {str(eprint)[:160]}[/yellow]")

        polite_delay(DEFAULT_DELAY)

    except Exception as e:
        console.print(f"[red]✗ Critical error during case processing: {e}[/red]")
        case_data["errors"].append({
            "type": "critical_processing_error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        case_data["metadata"]["exists"] = False

    # Validate that we got all 5 tabs - if any are missing, flag as incomplete
    if case_data["metadata"]["exists"]:
        validation_issues = []
        required_tabs = ["summary", "docket", "costs", "defendant", "attorneys"]

        missing_tab_snapshots = [
            tab for tab in required_tabs
            if not case_data.get("html_snapshots", {}).get(tab)
            or case_data.get("html_snapshots", {}).get(tab) == "[context_destroyed_during_snapshot]"
        ]
        if missing_tab_snapshots:
            validation_issues.append(f"Missing tab snapshots: {', '.join(missing_tab_snapshots)}")

        runtime_error_tabs = []
        for tab in required_tabs:
            html = case_data.get("html_snapshots", {}).get(tab, "") or ""
            if is_runtime_error_page_html(html):
                runtime_error_tabs.append(tab)
        if runtime_error_tabs:
            validation_issues.append(f"Runtime error page captured for tabs: {', '.join(runtime_error_tabs)}")
        
        # Check Summary (should have fields)
        if not case_data.get("summary", {}).get("fields"):
            validation_issues.append("Summary missing or empty")
        
        # Check Docket (should have entries for active cases)
        if not case_data.get("docket"):
            # Some very old/inactive cases might have no docket, but flag it
            console.print("[yellow]⚠ No docket entries found[/yellow]")
        else:
            docket_text_blob = "\n".join(json.dumps(e, ensure_ascii=False) for e in case_data["docket"])
            if is_runtime_error_page_html(docket_text_blob):
                validation_issues.append("Docket content appears to be runtime/error page instead of real docket rows")

            # Check if we have a sentencing entry (JE = Judgment Entry)
            # Check docket_type, document_type, and Entry fields for compatibility
            has_sentencing = any(
                entry.get("docket_type", entry.get("document_type", "")).upper() in ("JE", "SENTENCING", "JUDGMENT ENTRY") or
                entry.get("Entry", "").upper().startswith(("JE", "SENTENCING", "JUDGMENT ENTRY"))
                for entry in case_data["docket"]
            )
            if has_sentencing:
                je_count = sum(1 for e in case_data["docket"] 
                              if e.get("docket_type", e.get("document_type", "")).upper() in ("JE", "SENTENCING", "JUDGMENT ENTRY") or
                                 e.get("Entry", "").upper().startswith(("JE", "SENTENCING", "JUDGMENT ENTRY")))
                console.print(f"[green]✓ Found {je_count} sentencing entry/entries in docket[/green]")
            else:
                console.print("[blue]ℹ No sentencing entry in docket[/blue]")
        
        # Check Costs (many cases have no costs, so just verify structure exists)
        if "costs" not in case_data:
            validation_issues.append("Costs tab not extracted")
        
        # Check Defendant (should have data)
        if not case_data.get("defendant"):
            validation_issues.append("Defendant data missing")
        
        # Check Attorneys (many cases have no attorneys, so just verify structure exists)
        if "attorneys" not in case_data:
            validation_issues.append("Attorneys tab not extracted")

        extraction_errors = {
            "summary_extraction_error",
            "docket_extraction_error",
            "costs_extraction_error",
            "defendant_extraction_error",
            "attorneys_extraction_error",
        }
        if any(err.get("type") in extraction_errors for err in case_data.get("errors", [])):
            validation_issues.append("One or more tab extraction steps failed")

        case_data["metadata"]["complete_extraction"] = len(validation_issues) == 0
        
        # Log validation issues
        if validation_issues:
            console.print(f"[yellow]⚠ Validation warnings: {', '.join(validation_issues)}[/yellow]")
            case_data["errors"].append({
                "type": "validation_warning",
                "message": "; ".join(validation_issues),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    else:
        case_data["metadata"]["complete_extraction"] = False

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
    scraper.add_argument("--year", type=int, default=None, help="Year of cases (auto-detected if not specified)")
    scraper.add_argument("--start", type=int, default=int(os.getenv("START_NUMBER", "706402")))
    scraper.add_argument("--limit", type=int, default=int(os.getenv("LIMIT", "100")))
    scraper.add_argument("--direction", choices=["up","down","both"], default=os.getenv("DIRECTION","both"))
    scraper.add_argument("--output-dir", default=os.getenv("OUTPUT_DIR","./out"))
    scraper.add_argument("--delay-ms", type=int, default=int(os.getenv("DELAY_MS","1250")))
    scraper.add_argument("--headless", action="store_true")
    scraper.add_argument("--resume", action="store_true")
    scraper.add_argument("--download-pdfs", action="store_true", help="Download PDF files from docket entries")
    scraper.add_argument("--pdf-cases", nargs="*", help="Specific case IDs to download PDFs for (e.g., CR-25-706402-A)")
    scraper.add_argument("--discover-years", action="store_true", help="Discover and scrape full years (default: 2026, 2025, 2024)")
    scraper.add_argument("--years", nargs="+", type=int, help="Years to discover/scrape in order (e.g., --years 2026 2025 2024)")
    scraper.add_argument("--live", action="store_true", help="Run in live collection mode (keep up with new cases for the year)")
    scraper.add_argument("--workers", type=int, default=8, help="Total forward workers (default 8)")
    scraper.add_argument("--repair-workers", type=int, default=1, help="Number of repair workers (default 1)")
    scraper.add_argument("--frontier-interval", type=int, default=300, help="Seconds between frontier checks for new cases (default 300)")
    scraper.add_argument("--max-batch-size", type=int, default=200, help="Max numbers to enqueue per frontier expansion")
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

    global DEFAULT_DELAY
    if hasattr(args, "delay_ms") and args.delay_ms:
        # Ensure command-line --delay-ms actually controls polite pacing.
        DEFAULT_DELAY = max(300, int(args.delay_ms))
    
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
    
    # Handle year auto-detection
    year_to_use = args.year
    
    # Simplified headless logic - if --headless flag is set, use headless mode
    use_headless = args.headless or os.getenv("HEADLESS", "false").lower() == "true"
    
    cfg = Cfg(
        headless=use_headless,
        year=year_to_use if year_to_use else int(os.getenv("YEAR", "2025")),  # Use env default if no year specified
        start_number=args.start, direction=args.direction, limit=args.limit,
        output_dir=args.output_dir, delay_ms=args.delay_ms, resume=args.resume,
        download_pdfs=args.download_pdfs, pdf_cases=pdf_cases
    )

    # Determine years to process
    if args.discover_years:
        years_to_process = args.years if args.years else [2026, 2025, 2024]
        console.rule(f"[bold]🚀 Cuyahoga CP Full Year Discovery[/bold]")
        console.print(f"[cyan]Years to discover and scrape: {', '.join(map(str, years_to_process))}[/cyan]")
        console.print(f"[cyan]Reference case for discovery: {args.reference_case:06d}[/cyan]")
        console.print(f"[cyan]PDF download enabled for: {', '.join(pdf_cases)}[/cyan]")
    else:
        years_to_process = [cfg.year]

        # Single year mode setup will be done after browser launch

    async with async_playwright() as p:
        # If year was not specified, auto-detect it before proceeding
        if year_to_use is None and not args.discover_years:
            console.rule(f"[bold cyan]🔍 Auto-detecting year for case {args.start:06d}[/bold cyan]")
            # Allow using the user's installed Chrome and profile for interactive debugging.
            # If `CHROME_EXECUTABLE` or `CHROME_PROFILE_DIR` is set, launch a persistent
            # context that uses that executable and profile. This lets you use your
            # signed-in Chrome session (cookies, logins) for pages that block headless.
            chrome_exec = os.getenv("CHROME_EXECUTABLE")
            chrome_profile = os.getenv("CHROME_PROFILE_DIR")
            use_persistent = bool(chrome_exec or chrome_profile)

            if use_persistent:
                profile_dir = chrome_profile or str(Path.home() / ".config" / "google-chrome" / "Default")
                console.print(f"[cyan]Launching persistent Chrome context: exe={chrome_exec or 'system default'}, profile={profile_dir}[/cyan]")
                browser = await p.chromium.launch_persistent_context(user_data_dir=profile_dir,
                                                                     executable_path=chrome_exec if chrome_exec else None,
                                                                     headless=cfg.headless)
                page = await browser.new_page()
            else:
                browser = await p.chromium.launch(headless=cfg.headless)
                context = await browser.new_context()
                page = await context.new_page()
            
            try:
                await ensure_past_tos(page)
                detected_year = await detect_year_from_case_number(page, args.start)
                
                if detected_year:
                    cfg.year = detected_year
                    years_to_process = [detected_year]
                    console.print(f"[green]✓ Using auto-detected year: {detected_year}[/green]")
                else:
                    console.print(f"[yellow]⚠ Could not auto-detect year, using default: {cfg.year}[/yellow]")
            except Exception as e:
                console.print(f"[red]Error during year detection: {e}[/red]")
                console.print(f"[yellow]Using default year: {cfg.year}[/yellow]")
            finally:
                await browser.close()
        
        # Setup directories for single year mode
        out_dir = Path(cfg.output_dir) / str(cfg.year)
        out_dir.mkdir(parents=True, exist_ok=True)
        resume_file = out_dir / ".last_number"
        
        if cfg.headless:
            console.print("[green]🚫 Running in HEADLESS mode (no browser windows)[/green]")
        else:
            console.print("[yellow]👁 Running with VISIBLE browser windows[/yellow]")
        
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
            # Year discovery mode - need to create a page for discovery functions
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
            await page.route("**/*", lambda route: route.abort()
                             if route.request.resource_type in {"image", "media", "font"}
                             else route.continue_())
            
            # Pass the Playwright controller `p` along with the discovery page so
            # the full-year processing stage can create new browser contexts.
            await process_full_years(p, page, years_to_process, args.reference_case, 
                                   cfg.output_dir, cfg.delay_ms, cfg.download_pdfs, cfg.pdf_cases,
                                   headless=cfg.headless, workers=max(1, args.workers))
            await context.close()
        else:
            # Single year/range mode or live mode
            if args.live:
                # Live collection mode: keep checking frontier and run multiple workers
                await process_live_mode(p, cfg.year, Path(cfg.output_dir) / str(cfg.year),
                                        resume_file, cfg.delay_ms, cfg.download_pdfs, cfg.pdf_cases,
                                        workers=args.workers, repair_workers=args.repair_workers,
                                        frontier_interval=args.frontier_interval, max_batch_size=args.max_batch_size,
                                        headless=cfg.headless)
            else:
                # Single year/range mode - pass playwright instance for context recovery
                await process_case_range(p, cfg.year, targets, out_dir, resume_file,
                                   cfg.delay_ms, cfg.download_pdfs, cfg.pdf_cases,
                                   headless=cfg.headless, workers=max(1, args.workers))

    console.print(f"[green]Done.[/green] Output at: {cfg.output_dir}")

async def process_case_range(playwright_instance: Playwright, year: int, targets: List[int], out_dir: Path,
                           resume_file: Path, delay_ms: int, download_pdfs: bool, pdf_cases: List[str],
                           headless: bool = True, workers: int = 1):
    """Process a specific range of case numbers for a single year with context recovery and tracking"""
    if workers > 1:
        await process_case_range_parallel(
            playwright_instance, year, targets, out_dir, resume_file,
            delay_ms, download_pdfs, pdf_cases, headless=headless, workers=workers,
        )
        return

    processed = 0
    context_retries = 0
    max_context_retries = 3
    
    # Initialize case tracker - track every sequential number
    year_start = targets[0]
    year_end = targets[-1]
    tracker = CaseTracker(year, year_start, year_end, out_dir)
    
    async def create_context():
        """Create a new persistent browser context"""
        user_data_dir = Path("./browser_data")
        user_data_dir.mkdir(exist_ok=True)
        
        ctx = await playwright_instance.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ],
            viewport={"width": 1920, "height": 1080},
        )
        return ctx
    
    # Create initial context
    try:
        context = await create_context()
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Block heavy resources
        await page.route("**/*", lambda route: route.abort()
                         if route.request.resource_type in {"image", "media", "font"}
                         else route.continue_())
        
        # Warm up context by visiting search page once to handle initial TOS
        console.print("[cyan]⏳ Warming up browser context... (handling initial TOS if needed)[/cyan]")
        try:
            await page.goto(f"{BASE_URL}/Search.aspx", wait_until="networkidle", timeout=20000)
            if await check_current_page(page) == "tos":
                console.print("[magenta]🔔 Initial TOS page detected, accepting terms...[/magenta]")
                await ensure_past_tos(page)
            console.print("[green]✓ Browser context ready[/green]")
        except Exception as warmup_error:
            console.print(f"[yellow]Warmup had an issue (not critical): {warmup_error}[/yellow]")
        
    except Exception as e:
        console.print(f"[red]✗ Failed to create initial browser context: {e}[/red]")
        raise
    
    # Watchdog state: time of last saved JSON and consecutive no-save counter
    time_of_last_save = time.time()
    consecutive_no_save = 0
    stagnation_restarts = 0
    
    # Create progress bar with rich colors
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"[bold cyan]Scraping {year}[/bold cyan]", total=len(targets))
        
        for num in targets:
            # Create timestamped filename for the JSON output
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            case_filename = f"{year}-{num:06d}_{timestamp}.json"
            case_filepath = out_dir / case_filename
            
            try:
                # Check if context is still alive
                try:
                    await page.evaluate("1")  # Quick test to see if page is responsive
                except Exception as ctx_error:
                    # Context crashed - try to recover
                    progress.console.print(f"[yellow]⚠️  Browser context crashed, recovering...[/yellow]")
                    try:
                        await context.close()
                    except:
                        pass
                    
                    context_retries += 1
                    if context_retries > max_context_retries:
                        progress.console.print(f"[red]✗ Failed to recover context after {max_context_retries} attempts - aborting[/red]")
                        raise RuntimeError(f"Context crashed and recovery failed after {max_context_retries} attempts")
                    
                    # Wait before recreating to avoid rapid failure loops
                    await asyncio.sleep(2 ** context_retries)  # Exponential backoff: 2, 4, 8 seconds
                    
                    progress.console.print(f"[cyan]🔄 Recreating browser context (attempt {context_retries}/{max_context_retries})...[/cyan]")
                    context = await create_context()
                    page = context.pages[0] if context.pages else await context.new_page()
                    await page.route("**/*", lambda route: route.abort()
                                     if route.request.resource_type in {"image", "media", "font"}
                                     else route.continue_())
                    progress.console.print(f"[green]✓ Browser context recovered[/green]")
                
                # Extract case, retrying when tabs did not fully load.
                max_case_attempts = 3
                case_data = None
                for attempt in range(1, max_case_attempts + 1):
                    case_data = await snapshot_case(page, year, num, out_dir, delay_ms,
                                                   download_pdfs, pdf_cases)

                    if not case_data["metadata"].get("exists"):
                        break

                    if case_data["metadata"].get("complete_extraction", False):
                        break

                    progress.console.print(
                        f"[yellow]⚠ Incomplete extraction for {year}-{num:06d} (attempt {attempt}/{max_case_attempts}), retrying...[/yellow]"
                    )

                if case_data is None:
                    raise RuntimeError(f"No case data returned for {year}-{num:06d}")
                
                # Only save if case exists - skip non-existent cases
                if case_data["metadata"]["exists"]:
                    if not case_data["metadata"].get("complete_extraction", False):
                        # All retries exhausted and still incomplete — skip this case
                        tracker.add_error(num)
                        consecutive_no_save += 1
                        progress.console.print(f"[red]✗ {year}-{num:06d}[/red] skipped (stubborn incomplete after {max_case_attempts} attempts)")
                    else:
                        # Save the comprehensive JSON file
                        case_filepath.write_text(
                            json.dumps(case_data, indent=2, ensure_ascii=False), 
                            encoding="utf-8"
                        )
                        file_size = case_filepath.stat().st_size
                        # Explicit single-line saved confirmation for log parsing / user visibility
                        progress.console.print(f"SAVED_JSON {case_filepath} {file_size}")
                        tracker.add_success(num)
                        # Atomically increment per-year counter in out/stats.json
                        try:
                            increment_year_counter(out_dir, year)
                        except Exception:
                            pass
                        # Update watchdog because we just saved a JSON
                        try:
                            time_of_last_save = time.time()
                            consecutive_no_save = 0
                        except Exception:
                            pass
                        progress.console.print(f"[green]✓ {year}-{num:06d}[/green] ({file_size/1024:.1f}KB)")
                else:
                    tracker.add_missing(num)
                    # Mark a no-save iteration for watchdog
                    consecutive_no_save += 1
                    progress.console.print(f"[yellow]⊝ {year}-{num:06d}[/yellow] (missing)")
                
                # Log extraction summary if successful
                if case_data["metadata"]["exists"]:
                    # Count fields in summary (nested structure)
                    summary_count = len(case_data.get('summary', {}).get('fields', {}))
                    
                    summary_items = [
                        f"S:{summary_count}",
                        f"D:{len(case_data['docket'])}", 
                        f"C:{len(case_data['costs'])}",
                        f"Def:{len(case_data['defendant'])}",
                        f"Att:{len(case_data['attorneys'])}"
                    ]
                    
                    # Flag if we have sentencing entry
                    has_je = any(
                        e.get("docket_type", e.get("document_type", "")).upper() in ("JE", "SENTENCING", "JUDGMENT ENTRY") or
                        e.get("Entry", "").upper().startswith(("JE", "SENTENCING", "JUDGMENT ENTRY"))
                        for e in case_data['docket']
                    )
                    if has_je:
                        je_count = sum(1 for e in case_data['docket'] 
                                      if e.get("docket_type", e.get("document_type", "")).upper() in ("JE", "SENTENCING", "JUDGMENT ENTRY") or
                                         e.get("Entry", "").upper().startswith(("JE", "SENTENCING", "JUDGMENT ENTRY")))
                        summary_items.append(f"[JE×{je_count}]")
                    
                    if case_data["errors"]:
                        # Only show errors that aren't just validation warnings
                        real_errors = [e for e in case_data["errors"] if e.get("type") != "validation_warning"]
                        if real_errors:
                            summary_items.append(f"Err:{len(real_errors)}")
                    
                    progress.console.print(f"[blue]    {' | '.join(summary_items)}[/blue]")
                
                # Reset retry counter on successful case
                context_retries = 0
                
            except Exception as e:
                tracker.add_error(num)
                progress.console.print(f"[red]✗ {year}-{num:06d}: {str(e)[:60]}[/red]")
                
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
                # Log error file saved as well
                try:
                    error_size = case_filepath.stat().st_size
                    progress.console.print(f"SAVED_JSON {case_filepath} {error_size}")
                    # Treat a saved error JSON as activity for the watchdog
                    try:
                        time_of_last_save = time.time()
                        consecutive_no_save = 0
                    except Exception:
                        pass
                except:
                    pass
                
            processed += 1
            save_resume_state(resume_file, num)
            progress.update(task, advance=1)

            # Watchdog: if we haven't saved anything for STAGNATION_TIMEOUT seconds
            # or we've seen many consecutive no-save iterations, recreate context
            try:
                now = time.time()
                if (now - time_of_last_save) > STAGNATION_TIMEOUT or consecutive_no_save >= STAGNATION_MAX_NO_SAVE:
                    stagnation_restarts += 1
                    progress.console.print(f"[yellow]⚠️  No saved JSONs for {int(now - time_of_last_save)}s or {consecutive_no_save} consecutive no-saves - restarting browser context (#{stagnation_restarts})[/yellow]")
                    try:
                        await context.close()
                    except Exception:
                        pass

                    # Small backoff before recreating to avoid tight crash loops
                    await asyncio.sleep(min(30, 2 ** min(stagnation_restarts, 6)))
                    context = await create_context()
                    page = context.pages[0] if context.pages else await context.new_page()
                    await page.route("**/*", lambda route: route.abort()
                                     if route.request.resource_type in {"image", "media", "font"}
                                     else route.continue_())
                    # Reset watchdog markers
                    time_of_last_save = time.time()
                    consecutive_no_save = 0
                    context_retries = 0
                    progress.console.print(f"[green]✓ Browser context restarted by watchdog[/green]")
            except Exception:
                pass
    
    # Save tracking logs
    tracker.save_logs()
    stats = tracker.get_stats()
    
    # Print final summary
    console.rule(f"[bold cyan]Year {year} Summary[/bold cyan]")
    table = Table(title=f"Download Statistics for {year}")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="magenta")
    table.add_row("Total Range", f"{stats['total_range']:,}")
    table.add_row("Successfully Downloaded", f"[green]{stats['successfully_downloaded']:,}[/green]")
    table.add_row("Missing Cases", f"[yellow]{stats['missing_cases']:,}[/yellow]")
    table.add_row("Errored Cases", f"[red]{stats['errored_cases']:,}[/red]")
    table.add_row("Total Accounted", f"{stats['total_accounted']:,}")
    if stats['unaccounted'] > 0:
        table.add_row("Unaccounted For", f"[red]{stats['unaccounted']:,}[/red]")
    console.print(table)
    
    # Cleanup
    try:
        await context.close()
    except:
        pass


async def process_case_range_parallel(playwright_instance: Playwright, year: int, targets: List[int], out_dir: Path,
                                     resume_file: Path, delay_ms: int, download_pdfs: bool, pdf_cases: List[str], *,
                                     headless: bool = True, workers: int = 3):
    """Process case numbers in parallel with one browser context per worker."""
    workers = max(1, workers)
    tracker = CaseTracker(year, targets[0], targets[-1], out_dir)

    queue: asyncio.Queue[int] = asyncio.Queue()
    for n in targets:
        queue.put_nowait(n)

    resume_lock = asyncio.Lock()
    progress_lock = asyncio.Lock()
    max_saved_resume = load_resume_state(resume_file) or 0

    async def create_context():
        user_data_dir = Path("./browser_data")
        user_data_dir.mkdir(exist_ok=True)
        ctx = await playwright_instance.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ],
            viewport={"width": 1920, "height": 1080},
        )
        return ctx

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"[bold cyan]Scraping {year} ({workers} workers)[/bold cyan]", total=len(targets))

        async def worker_loop(worker_id: int):
            nonlocal max_saved_resume
            context = await create_context()
            page = context.pages[0] if context.pages else await context.new_page()
            await page.route("**/*", lambda route: route.abort()
                             if route.request.resource_type in {"image", "media", "font"}
                             else route.continue_())

            try:
                while True:
                    try:
                        num = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                    case_filepath = out_dir / f"{year}-{num:06d}_{timestamp}.json"

                    try:
                        max_case_attempts = 3
                        case_data = None
                        for attempt in range(1, max_case_attempts + 1):
                            case_data = await snapshot_case(page, year, num, out_dir, delay_ms, download_pdfs, pdf_cases)

                            if not case_data["metadata"].get("exists"):
                                break
                            if case_data["metadata"].get("complete_extraction", False):
                                break

                            async with progress_lock:
                                progress.console.print(
                                    f"[yellow]⚠ W{worker_id} incomplete {year}-{num:06d} (attempt {attempt}/{max_case_attempts})[/yellow]"
                                )

                        if case_data is None:
                            raise RuntimeError(f"No case data returned for {year}-{num:06d}")

                        if case_data["metadata"].get("exists"):
                            if not case_data["metadata"].get("complete_extraction", False):
                                # All retries exhausted — skip stubborn case
                                tracker.add_error(num)
                                async with progress_lock:
                                    progress.console.print(f"[red]✗ W{worker_id} {year}-{num:06d}[/red] skipped (stubborn incomplete after {max_case_attempts} attempts)")
                            else:
                                case_filepath.write_text(json.dumps(case_data, indent=2, ensure_ascii=False), encoding="utf-8")
                                tracker.add_success(num)
                                try:
                                    increment_year_counter(out_dir, year)
                                except Exception:
                                    pass
                                async with progress_lock:
                                    progress.console.print(f"SAVED_JSON {case_filepath} {case_filepath.stat().st_size}")
                        else:
                            tracker.add_missing(num)

                    except Exception as e:
                        tracker.add_error(num)
                        error_case_data = {
                            "metadata": {
                                "year": year,
                                "number": num,
                                "case_number_formatted": f"{year}-{num:06d}",
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                                "scraper_version": "1.0.0",
                                "exists": False,
                                "case_id": None,
                                "complete_extraction": False,
                            },
                            "summary": {},
                            "docket": [],
                            "costs": [],
                            "defendant": {},
                            "attorneys": [],
                            "errors": [{
                                "type": "critical_scraper_error",
                                "message": str(e),
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }],
                            "html_snapshots": {},
                        }
                        case_filepath.write_text(json.dumps(error_case_data, indent=2, ensure_ascii=False), encoding="utf-8")

                    async with resume_lock:
                        if num > max_saved_resume:
                            max_saved_resume = num
                            save_resume_state(resume_file, num)

                    async with progress_lock:
                        progress.update(task, advance=1)

                    queue.task_done()
            finally:
                try:
                    await context.close()
                except Exception:
                    pass

        await asyncio.gather(*[worker_loop(i + 1) for i in range(workers)])

    tracker.save_logs()
    stats = tracker.get_stats()
    console.rule(f"[bold cyan]Year {year} Summary[/bold cyan]")
    table = Table(title=f"Download Statistics for {year}")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="magenta")
    table.add_row("Total Range", f"{stats['total_range']:,}")
    table.add_row("Successfully Downloaded", f"[green]{stats['successfully_downloaded']:,}[/green]")
    table.add_row("Missing Cases", f"[yellow]{stats['missing_cases']:,}[/yellow]")
    table.add_row("Errored Cases", f"[red]{stats['errored_cases']:,}[/red]")
    table.add_row("Total Accounted", f"{stats['total_accounted']:,}")
    if stats['unaccounted'] > 0:
        table.add_row("Unaccounted For", f"[red]{stats['unaccounted']:,}[/red]")
    console.print(table)

async def process_full_years(playwright_instance, page: Page, years: List[int], reference_case: int, 
                           output_dir: str, delay_ms: int, download_pdfs: bool, pdf_cases: List[str],
                           headless: bool = True, workers: int = 1):
    """Discover and process full years of cases"""
    year_ranges = {}
    
    # Discover ranges for each year
    for idx, year in enumerate(years):
        console.rule(f"[bold]🔍 DISCOVERING YEAR {year}[/bold]")

        # Find start and end of year.
        # For the first requested year, use the explicit reference. For later years,
        # seed discovery from the previous year's discovered start minus ~10k.
        if idx == 0:
            year_reference = reference_case
        else:
            prev_year = years[idx - 1]
            prev_start, _ = year_ranges.get(prev_year, (reference_case, reference_case))
            year_reference = max(1, prev_start - 10000)

        console.print(f"[blue]Using discovery reference {year_reference:06d} for year {year}[/blue]")
        start_case = await find_year_start(page, year, year_reference)
        
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

        # Process all cases in this year. Pass the Playwright controller so the
        # worker context creation uses the correct API (playwright_instance.chromium).
        await process_case_range(playwright_instance, year, all_cases, year_dir, resume_file,
                       delay_ms, download_pdfs, pdf_cases, headless=headless, workers=workers)

        console.print(f"[green]✅ Completed year {year}[/green]")


async def process_live_mode(playwright_instance: Playwright, year: int, year_dir: Path, resume_file: Path,
                            delay_ms: int, download_pdfs: bool, pdf_cases: List[str], *,
                            workers: int = 8, repair_workers: int = 1,
                            frontier_interval: int = 300, max_batch_size: int = 200,
                            headless: bool = True):
    """Run live collection for a single year.

    Behavior:
    - Discover the current end (frontier) for the year.
    - Spawn N forward workers that claim sequential case numbers from a shared queue.
    - Spawn 1 repair worker that re-processes missing/errored lists.
    - Periodically (frontier_interval) probe for new cases and enqueue new numbers.
    """
    year_dir.mkdir(parents=True, exist_ok=True)
    # Use a lightweight discovery context/page to probe for frontier changes
    user_data_dir = Path("./browser_data")
    user_data_dir.mkdir(exist_ok=True)

    console.print(f"[cyan]🔴 Starting live mode for {year} with {workers} workers (+{repair_workers} repair)")

    # Helper to create a context for workers
    async def create_context_for_worker():
        ctx = await playwright_instance.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir), headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ], viewport={"width": 1920, "height": 1080},
        )
        return ctx

    # Discover a starting point: prefer resume, then latest file in year_dir, else 1
    resume_n = load_resume_state(resume_file)
    start_case = int(resume_n) if resume_n else None
    if start_case is None:
        # Inspect existing JSON files to find a reasonable start
        try:
            files = list(year_dir.glob(f"{year}-*.json"))
            if files:
                # parse last numeric part from filenames like 2025-706402_YYYYMMDD_HHMMSS.json
                nums = []
                for f in files:
                    m = re.match(rf"{year}-(\d{{6}})_", f.name)
                    if m:
                        nums.append(int(m.group(1)))
                if nums:
                    start_case = max(1, max(nums) - 200)  # back off a bit to include nearby missing
        except Exception:
            start_case = None
    if start_case is None:
        start_case = 1

    # Create a discovery page to find current frontier
    discover_ctx = await create_context_for_worker()
    discover_page = discover_ctx.pages[0] if discover_ctx.pages else await discover_ctx.new_page()
    await discover_page.route("**/*", lambda route: route.abort()
                              if route.request.resource_type in {"image", "media", "font"}
                              else route.continue_())

    # Find initial frontier end
    try:
        frontier_end = await find_year_end(discover_page, year, max(start_case, 1))
    except Exception as e:
        console.print(f"[yellow]Could not discover frontier end reliably: {e}; using start_case+1000[/yellow]")
        frontier_end = start_case + 1000

    console.print(f"[green]Initial frontier for {year}: {start_case:06d} -> {frontier_end:06d}[/green]")

    # Shared queue and bookkeeping
    queue: asyncio.Queue = asyncio.Queue()
    in_flight = set()
    processed = set()

    def enqueue_range(a: int, b: int):
        # enqueue numbers [a..b]
        for n in range(a, b + 1):
            if n not in in_flight and n not in processed:
                queue.put_nowait(n)
                in_flight.add(n)

    enqueue_range(start_case, frontier_end)

    stop_event = asyncio.Event()

    async def forward_worker(worker_id: int):
        ctx = await create_context_for_worker()
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.route("**/*", lambda route: route.abort()
                         if route.request.resource_type in {"image", "media", "font"}
                         else route.continue_())

        while not stop_event.is_set():
            try:
                n = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # No work for now
                await asyncio.sleep(1)
                continue

            try:
                console.print(f"[cyan][W{worker_id}] Working {year}-{n:06d}[/cyan]")
                case_data = await snapshot_case(page, year, n, year_dir, delay_ms, download_pdfs, pdf_cases)

                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                fname = f"{year}-{n:06d}_{ts}.json"
                fpath = year_dir / fname
                if case_data["metadata"].get("exists"):
                    fpath.write_text(json.dumps(case_data, indent=2, ensure_ascii=False), encoding="utf-8")
                    file_size = fpath.stat().st_size
                    console.print(f"SAVED_JSON {fpath} {file_size}")
                    try:
                        increment_year_counter(year_dir, year)
                    except:
                        pass
                else:
                    # Save a note for missing case as well so repair worker can see it
                    fpath.write_text(json.dumps(case_data, indent=2, ensure_ascii=False), encoding="utf-8")

                # Bookkeeping
                processed.add(n)
                in_flight.discard(n)
                # Update resume state to this number so future resumes skip completed
                try:
                    save_resume_state(resume_file, n)
                except:
                    pass

            except Exception as e:
                console.print(f"[red][W{worker_id}] Error on {year}-{n:06d}: {e}")
                in_flight.discard(n)
                processed.add(n)
            finally:
                queue.task_done()

        try:
            await ctx.close()
        except:
            pass

    async def repair_worker_fn(rid: int):
        # Periodically scan missing/errored logs and re-enqueue numbers
        while not stop_event.is_set():
            try:
                logs_dir = year_dir / "logs"
                for suffix in (f"{year}_missing.txt", f"{year}_errored.txt"):
                    p = logs_dir / suffix
                    if p.exists():
                        try:
                            for line in p.read_text().splitlines():
                                line = line.strip()
                                if not line:
                                    continue
                                m = re.search(rf"{year}-(\d{{6}})", line)
                                if m:
                                    n = int(m.group(1))
                                    if n not in processed and n not in in_flight:
                                        queue.put_nowait(n)
                                        in_flight.add(n)
                        except Exception:
                            pass
            except Exception:
                pass

            await asyncio.sleep(60)

    async def frontier_expander():
        nonlocal frontier_end
        while not stop_event.is_set():
            await asyncio.sleep(frontier_interval)
            try:
                new_end = await find_year_end(discover_page, year, max(frontier_end, start_case))
                if new_end > frontier_end:
                    a = frontier_end + 1
                    b = min(new_end, frontier_end + max_batch_size)
                    console.print(f"[green]Frontier expanded: enqueueing {a:06d}-{b:06d} (was {frontier_end:06d})[/green]")
                    enqueue_range(a, b)
                    frontier_end = b if b < new_end else new_end
            except Exception as e:
                console.print(f"[yellow]Frontier probe failed: {e}[/yellow]")

    # Start workers
    tasks = []
    for i in range(max(1, workers - repair_workers)):
        tasks.append(asyncio.create_task(forward_worker(i + 1)))

    for r in range(repair_workers):
        tasks.append(asyncio.create_task(repair_worker_fn(r + 1)))

    tasks.append(asyncio.create_task(frontier_expander()))

    try:
        # Run until canceled by user - keep the loop alive and report status periodically
        while True:
            await asyncio.sleep(60)
            # Quick status
            console.print(f"[blue]Live {year} status: queued={queue.qsize()} in_flight={len(in_flight)} processed={len(processed)} frontier={frontier_end:06d}")
    except asyncio.CancelledError:
        pass
    finally:
        stop_event.set()
        # Wait for workers to finish
        for t in tasks:
            t.cancel()
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except:
            pass

        try:
            await discover_ctx.close()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(run())
