#!/usr/bin/env python3
"""
Fill missing case numbers for the most recent years.

- Discovers year ranges from the court site
- Finds gaps in local downloads
- Downloads missing cases
- Avoids exact duplicates (replaces older identical files)
- Logs all actions
"""

import argparse
import asyncio
import json
import re
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Dict, List, Optional, Protocol, Tuple, cast

from playwright.async_api import Page, async_playwright, TimeoutError as PlaywrightTimeoutError

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import main as scraper


class SnapshotCase(Protocol):
    def __call__(
        self,
        page: Any,
        year: int,
        number: int,
        out_root: Path,
        delay_ms: int,
        download_pdfs: bool = False,
        case_id_filter: Optional[List[str]] = None,
    ) -> Awaitable[Dict[str, Any]]: ...


def now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def parse_case_number(year: int, filename: str) -> Optional[int]:
    match = re.match(rf"{year}-(\d{{6}})_", filename)
    if not match:
        return None
    return int(match.group(1))


def collect_existing_cases(year_dir: Path, year: int) -> Tuple[Dict[int, List[Path]], Dict[int, Path]]:
    case_files: Dict[int, List[Path]] = {}
    for f in year_dir.glob("*.json"):
        num = parse_case_number(year, f.name)
        if num is None:
            continue
        case_files.setdefault(num, []).append(f)

    latest_by_num: Dict[int, Path] = {
        num: max(files, key=lambda p: p.stat().st_mtime)
        for num, files in case_files.items()
    }
    return case_files, latest_by_num


def canonical_hash(obj: Dict[str, Any]) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def choose_years(out_dir: Path, explicit_years: Optional[List[int]]) -> List[int]:
    if explicit_years:
        return sorted(set(explicit_years))

    years: List[int] = []
    for entry in out_dir.iterdir():
        if entry.is_dir() and re.fullmatch(r"20\d{2}", entry.name):
            years.append(int(entry.name))

    years = sorted(years)
    return years[-3:] if len(years) > 3 else years


def default_reference_case(year: int) -> int:
    # Fallback reference cases based on known ranges
    if year == 2025:
        return 706402
    if year == 2024:
        return 696402
    if year == 2023:
        return 684826
    return 100000


def log_line(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(message.rstrip() + "\n")


async def discover_year_range(page: Page, year: int, reference_case: int) -> Tuple[int, int]:
    await scraper.ensure_past_tos(page)
    start_case = await scraper.find_year_start(page, year, reference_case)
    end_case = await scraper.find_year_end(page, year, start_case)
    return start_case, end_case


async def fill_year_gaps(
    year: int,
    out_dir: Path,
    download_pdfs: bool,
    delay_ms: int,
    headless: bool,
    log_path: Path,
    reference_case: Optional[int] = None,
    nav_timeout_start_s: int = 5,
    nav_timeout_min_s: int = 5,
    nav_timeout_max_s: int = 60,
    nav_timeout_step_s: int = 1,
) -> Dict[str, int]:
    year_dir = out_dir / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)

    case_files, latest_by_num = collect_existing_cases(year_dir, year)
    existing_nums = set(latest_by_num.keys())

    if reference_case is None:
        reference_case = max(existing_nums) if existing_nums else default_reference_case(year)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(Path("./browser_data")),
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
        page = context.pages[0] if context.pages else await context.new_page()
        await page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in {"image", "media", "font"}
            else route.continue_(),
        )

        start_case, end_case = await discover_year_range(page, year, reference_case)

        total_expected = end_case - start_case + 1
        missing_nums = [n for n in range(start_case, end_case + 1) if n not in existing_nums]

        log_line(log_path, f"YEAR {year} RANGE {start_case:06d}-{end_case:06d} TOTAL {total_expected} EXISTING {len(existing_nums)} MISSING {len(missing_nums)}")

        downloaded = 0
        skipped_missing = 0
        duplicate_replaced = 0
        errors = 0

        current_timeout_s = nav_timeout_start_s

        for num in missing_nums:
            try:
                snapshot_case: SnapshotCase = cast(SnapshotCase, getattr(scraper, "snapshot_case"))

                while True:
                    try:
                        page.set_default_timeout(current_timeout_s * 1000)
                        case_data = await snapshot_case(
                            page,
                            year,
                            num,
                            year_dir,
                            delay_ms,
                            download_pdfs,
                            None,
                        )
                        if current_timeout_s > nav_timeout_min_s:
                            current_timeout_s = max(nav_timeout_min_s, current_timeout_s - nav_timeout_step_s)
                        break
                    except PlaywrightTimeoutError:
                        if current_timeout_s < nav_timeout_max_s:
                            current_timeout_s = min(nav_timeout_max_s, current_timeout_s + nav_timeout_step_s)
                            log_line(
                                log_path,
                                f"TIMEOUT_RETRY {year}-{num:06d} timeout={current_timeout_s}s",
                            )
                            continue
                        raise

                if not case_data.get("metadata", {}).get("exists"):
                    skipped_missing += 1
                    log_line(log_path, f"MISSING {year}-{num:06d}")
                    continue

                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                new_path = year_dir / f"{year}-{num:06d}_{timestamp}.json"

                existing_path = latest_by_num.get(num)
                is_duplicate = False
                if existing_path and existing_path.exists():
                    try:
                        with existing_path.open("r", encoding="utf-8") as f:
                            existing_data = json.load(f)
                        if canonical_hash(existing_data) == canonical_hash(case_data):
                            is_duplicate = True
                    except Exception:
                        pass

                new_path.write_text(json.dumps(case_data, indent=2, ensure_ascii=False), encoding="utf-8")

                if is_duplicate:
                    for old_file in case_files.get(num, []):
                        try:
                            old_file.unlink()
                        except Exception:
                            pass
                    duplicate_replaced += 1
                    log_line(log_path, f"DUPLICATE_REPLACED {year}-{num:06d} -> {new_path.name}")
                    latest_by_num[num] = new_path
                    case_files[num] = [new_path]
                else:
                    downloaded += 1
                    log_line(log_path, f"DOWNLOADED {year}-{num:06d} -> {new_path.name}")
                    case_files.setdefault(num, []).append(new_path)
                    latest_by_num[num] = new_path
                    try:
                        scraper.increment_year_counter(year_dir, year)
                    except Exception:
                        pass

            except Exception as exc:
                errors += 1
                log_line(log_path, f"ERROR {year}-{num:06d} {exc}")
                continue

            scraper.polite_delay(delay_ms)

        await context.close()

    return {
        "year": year,
        "total_expected": total_expected,
        "existing": len(existing_nums),
        "missing": len(missing_nums),
        "downloaded": downloaded,
        "duplicates_replaced": duplicate_replaced,
        "not_found": skipped_missing,
        "errors": errors,
    }


async def main():
    parser = argparse.ArgumentParser(description="Fill missing cases for recent years")
    parser.add_argument("--output-dir", default="./out", help="Output directory with year folders")
    parser.add_argument("--years", nargs="*", type=int, help="Years to process (default: last 3 years found)")
    parser.add_argument("--download-pdfs", action="store_true", help="Download PDFs while scraping missing cases")
    parser.add_argument("--delay-ms", type=int, default=int(scraper.DEFAULT_DELAY), help="Delay between cases")
    parser.add_argument("--headed", action="store_true", help="Run with visible browser windows")
    parser.add_argument("--reference-case", type=int, default=None, help="Reference case number for year discovery")
    parser.add_argument("--log-path", default=None, help="Log file path (default: logs/gap_fill_TIMESTAMP.log)")
    parser.add_argument("--nav-timeout-start", type=int, default=5, help="Starting navigation timeout (seconds)")
    parser.add_argument("--nav-timeout-min", type=int, default=5, help="Minimum navigation timeout (seconds)")
    parser.add_argument("--nav-timeout-max", type=int, default=60, help="Maximum navigation timeout (seconds)")
    parser.add_argument("--nav-timeout-step", type=int, default=1, help="Step to adjust timeout (seconds)")

    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    years = choose_years(out_dir, args.years)
    if not years:
        print("No year directories found in output directory. - fill_recent_year_gaps.py:278")
        return

    log_path = Path(args.log_path) if args.log_path else Path("logs") / f"gap_fill_{now_ts()}.log"
    log_line(log_path, f"START {datetime.now(timezone.utc).isoformat()} YEARS {','.join(map(str, years))}")

    summaries: List[Dict[str, int]] = []
    for year in years:
        summary = await fill_year_gaps(
            year=year,
            out_dir=out_dir,
            download_pdfs=args.download_pdfs,
            delay_ms=args.delay_ms,
            headless=not args.headed,
            log_path=log_path,
            reference_case=args.reference_case,
            nav_timeout_start_s=args.nav_timeout_start,
            nav_timeout_min_s=args.nav_timeout_min,
            nav_timeout_max_s=args.nav_timeout_max,
            nav_timeout_step_s=args.nav_timeout_step,
        )
        summaries.append(summary)

    log_line(log_path, f"END {datetime.now(timezone.utc).isoformat()}")

    print("\nGap fill summary: - fill_recent_year_gaps.py:303")
    for summary in summaries:
        print(
            f"{summary['year']}: total_expected={summary['total_expected']:,} "
            f"existing={summary['existing']:,} missing={summary['missing']:,} "
            f"downloaded={summary['downloaded']:,} duplicates_replaced={summary['duplicates_replaced']:,} "
            f"not_found={summary['not_found']:,} errors={summary['errors']:,}"
        )
    print(f"\nLog: {log_path} - fill_recent_year_gaps.py:311")


if __name__ == "__main__":
    asyncio.run(main())
