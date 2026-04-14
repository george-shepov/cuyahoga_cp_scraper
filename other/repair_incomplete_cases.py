#!/usr/bin/env python3
"""
Multi-threaded case repair system
- Scans existing JSONs for missing/incomplete data (costs, attorneys, PDFs)
- Deletes broken JSONs immediately
- Re-scrapes with full data
- One thread per year for parallel processing
"""

import json
import asyncio
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Set, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import threading

# Rich console for pretty output
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
    console = Console()
except ImportError:
    class Console:
        def print(self, *args, **kwargs): print(*args)
        def rule(self, *args, **kwargs): print("=" * 80)
    console = Console()


def cleanup_browsers():
    """Aggressively kill all playwright and chromium browser processes"""
    try:
        subprocess.run(['pkill', '-9', '-f', 'chromium'], 
                     capture_output=True, check=False)
        subprocess.run(['pkill', '-9', '-f', 'playwright'], 
                     capture_output=True, check=False)
        time.sleep(0.5)  # Give processes time to die
    except:
        pass


class CaseIssue:
    """Represents an issue found in a case JSON"""
    def __init__(self, case_id: str, year: int, file_path: Path, issues: List[str]):
        self.case_id = case_id
        self.year = year
        self.file_path = file_path
        self.issues = issues
    
    def __repr__(self):
        return f"{self.case_id} ({self.year}): {', '.join(self.issues)}"


class CaseRepairWorker:
    """Worker thread for repairing cases in a specific year"""
    
    def __init__(self, year: int, output_dir: Path, worker_id: int):
        self.year = year
        self.output_dir = output_dir
        self.worker_id = worker_id
        self.repaired = 0
        self.failed = 0
        self.lock = threading.Lock()
    
    def scan_year(self) -> List[CaseIssue]:
        """Scan all cases in this year for issues"""
        year_dir = self.output_dir / str(self.year)
        if not year_dir.exists():
            console.print(f"[yellow]Year {self.year} directory not found[/yellow]")
            return []
        
        issues_found = []
        json_files = list(year_dir.glob("*.json"))
        
        console.print(f"[cyan]Worker {self.worker_id} (Year {self.year}): Scanning {len(json_files)} cases...[/cyan]")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                # Extract case_id from metadata or summary or filename
                case_id = None
                if 'metadata' in data and 'case_id' in data['metadata']:
                    case_id = data['metadata']['case_id']
                elif 'summary' in data and 'case_id' in data['summary']:
                    case_id = data['summary']['case_id']
                elif 'case_id' in data:
                    case_id = data['case_id']
                else:
                    # Try to construct from filename (e.g., CR-24-695587-A.json)
                    case_id = json_file.stem
                
                if not case_id or case_id == 'UNKNOWN':
                    case_id = json_file.stem
                
                problems = []
                
                # Check for missing costs
                costs = data.get('costs', [])
                if 'summary' in data and 'fields' in data['summary']:
                    # Check embedded costs table
                    fields = data['summary']['fields']
                    has_costs_table = any('cost' in str(k).lower() for k in fields.keys())
                    if not has_costs_table and (not costs or len(costs) == 0):
                        problems.append('no_costs')
                elif not costs or len(costs) == 0:
                    problems.append('no_costs')
                
                # Check for missing attorneys
                attorneys = data.get('attorneys', [])
                if not attorneys or len(attorneys) == 0:
                    problems.append('no_attorneys')
                
                # Check for missing case info (summary section)
                has_summary = 'summary' in data and data['summary']
                has_metadata = 'metadata' in data and data['metadata']
                if not has_summary and not has_metadata:
                    problems.append('no_case_info')
                
                # Check for missing docket
                docket = data.get('docket', [])
                if not docket or len(docket) == 0:
                    problems.append('no_docket')
                
                # Check for empty/minimal party info
                parties = data.get('parties', [])
                if 'summary' in data and 'fields' in data['summary']:
                    # Check if defendant info exists
                    fields = data['summary']['fields']
                    has_name = 'Name:' in fields or 'name' in str(fields).lower()
                    if not has_name and (not parties or len(parties) == 0):
                        problems.append('no_parties')
                elif not parties or len(parties) == 0:
                    problems.append('no_parties')
                
                # Check for scrape errors
                if data.get('error'):
                    problems.append('scrape_error')
                
                # Check for missing disposition (only flag if truly empty, not "Unknown")
                disposition = data.get('disposition')
                if not disposition:
                    problems.append('no_disposition')
                
                if problems:
                    issues_found.append(CaseIssue(case_id, self.year, json_file, problems))
            
            except json.JSONDecodeError:
                # Corrupted JSON - definitely needs repair
                case_id = json_file.stem
                issues_found.append(CaseIssue(case_id, self.year, json_file, ['corrupted_json']))
            except Exception as e:
                console.print(f"[yellow]Error scanning {json_file}: {e}[/yellow]")
                continue
        
        return issues_found
    
    def repair_case(self, issue: CaseIssue) -> bool:
        """Delete and re-scrape a single case"""
        try:
            # Extract case number from case_id (e.g., CR-23-684826-A -> 684826)
            import re
            import os
            match = re.search(r'-(\d+)-', issue.case_id)
            if not match:
                # Try to extract from filename (e.g., 2023-684826_timestamp.json -> 684826)
                match = re.search(r'\d{4}-(\d+)_', issue.file_path.name)
                if not match:
                    console.print(f"[red]Cannot extract case number from {issue.case_id} or {issue.file_path.name}[/red]")
                    return False
            
            case_num = int(match.group(1))
            
            # Delete the broken JSON immediately
            if issue.file_path.exists():
                issue.file_path.unlink()
            
            # Use wrapper script that ensures headless and kills browsers
            cmd = [
                './scrape_headless.sh',
                str(self.year),
                str(case_num)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout per case
                cwd=Path(__file__).parent
            )
            
            # Aggressively clean up any browser processes after EVERY scrape
            cleanup_browsers()
            
            if result.returncode == 0:
                # Look for new JSON file with this case number pattern
                year_dir = self.output_dir / str(self.year)
                pattern = f"{self.year}-{case_num:06d}_*.json"
                new_files = list(year_dir.glob(pattern))
                
                if new_files:
                    # Take the most recent file
                    new_file = max(new_files, key=lambda p: p.stat().st_mtime)
                    
                    # Verify it's valid JSON
                    try:
                        with open(new_file, 'r') as f:
                            new_data = json.load(f)
                        
                        # Check if repair actually fixed the issues
                        fixed = True
                        if 'no_costs' in issue.issues:
                            costs = new_data.get('costs', [])
                            if not costs or len(costs) == 0:
                                # Check embedded costs
                                if 'summary' in new_data and 'fields' in new_data['summary']:
                                    has_costs = any('cost' in str(k).lower() for k in new_data['summary']['fields'].keys())
                                    if not has_costs:
                                        fixed = False
                                else:
                                    fixed = False
                        
                        if 'no_attorneys' in issue.issues:
                            attorneys = new_data.get('attorneys', [])
                            if not attorneys or len(attorneys) == 0:
                                fixed = False
                        
                        if fixed:
                            console.print(f"[green]Worker {self.worker_id}: ✓ {issue.case_id}[/green]")
                            return True
                        else:
                            console.print(f"[yellow]Worker {self.worker_id}: ⚠ {issue.case_id} (issues remain)[/yellow]")
                            return False
                    except json.JSONDecodeError:
                        console.print(f"[red]Worker {self.worker_id}: ✗ {issue.case_id} (corrupted)[/red]")
                        return False
                else:
                    console.print(f"[red]Worker {self.worker_id}: ✗ {issue.case_id} (not created)[/red]")
                    return False
            else:
                console.print(f"[red]Worker {self.worker_id}: ✗ {issue.case_id} (failed)[/red]")
                return False
        
        except subprocess.TimeoutExpired:
            console.print(f"[red]Worker {self.worker_id}: ✗ {issue.case_id} (timeout)[/red]")
            cleanup_browsers()  # Clean up on timeout
            return False
        except Exception as e:
            console.print(f"[red]Worker {self.worker_id}: ✗ {issue.case_id} ({str(e)[:30]})[/red]")
            cleanup_browsers()  # Clean up on error
            return False
    
    def run(self) -> Dict:
        """Main worker loop"""
        console.rule(f"[bold cyan]Worker {self.worker_id}: Processing Year {self.year}[/bold cyan]")
        
        # Scan for issues
        issues = self.scan_year()
        
        if not issues:
            console.print(f"[green]Worker {self.worker_id}: No issues found in year {self.year}! ✓[/green]")
            return {
                'year': self.year,
                'worker_id': self.worker_id,
                'scanned': 0,
                'issues_found': 0,
                'repaired': 0,
                'failed': 0
            }
        
        console.print(f"[yellow]Worker {self.worker_id}: Found {len(issues)} cases with issues in {self.year}[/yellow]")
        
        # Show issue breakdown
        issue_types = {}
        for issue in issues:
            for problem in issue.issues:
                issue_types[problem] = issue_types.get(problem, 0) + 1
        
        console.print(f"[cyan]Worker {self.worker_id}: Issue breakdown:[/cyan]")
        for issue_type, count in sorted(issue_types.items(), key=lambda x: x[1], reverse=True):
            console.print(f"  • {issue_type}: {count}")
        
        # Repair each case
        for i, issue in enumerate(issues, 1):
            if i % 50 == 0 or i == 1:
                console.print(f"[cyan]Worker {self.worker_id}: Progress [{i}/{len(issues)}][/cyan]")
            
            if self.repair_case(issue):
                with self.lock:
                    self.repaired += 1
            else:
                with self.lock:
                    self.failed += 1
        
        console.rule(f"[bold green]Worker {self.worker_id} Complete: Year {self.year}[/bold green]")
        console.print(f"  ✓ Repaired: {self.repaired}")
        console.print(f"  ✗ Failed: {self.failed}")
        
        return {
            'year': self.year,
            'worker_id': self.worker_id,
            'scanned': len(list((self.output_dir / str(self.year)).glob("*.json"))),
            'issues_found': len(issues),
            'repaired': self.repaired,
            'failed': self.failed
        }


def main():
    """Main repair orchestrator"""
    console.rule("[bold]🔧 Multi-Threaded Case Repair System[/bold]")
    
    # Clean up any existing browser processes before starting
    console.print("[yellow]Cleaning up any existing browser processes...[/yellow]")
    cleanup_browsers()
    
    output_dir = Path("./out")
    years = [2026, 2025, 2024]
    
    console.print(f"[cyan]Output directory: {output_dir}[/cyan]")
    console.print(f"[cyan]Years to process: {', '.join(map(str, years))}[/cyan]")
    console.print(f"[cyan]Workers: {len(years)} (one per year)[/cyan]\n")
    
    # Create workers
    workers = [CaseRepairWorker(year, output_dir, i+1) for i, year in enumerate(years)]
    
    # Run workers in parallel
    console.print("[yellow]Starting parallel repair workers...[/yellow]\n")
    start_time = datetime.now()
    
    with ThreadPoolExecutor(max_workers=len(years)) as executor:
        futures = [executor.submit(worker.run) for worker in workers]
        results = [future.result() for future in futures]
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Summary
    console.rule("[bold green]🎉 Repair Complete[/bold green]")
    
    total_scanned = sum(r['scanned'] for r in results)
    total_issues = sum(r['issues_found'] for r in results)
    total_repaired = sum(r['repaired'] for r in results)
    total_failed = sum(r['failed'] for r in results)
    
    console.print(f"\n[cyan]Total cases scanned: {total_scanned}[/cyan]")
    console.print(f"[yellow]Issues found: {total_issues}[/yellow]")
    console.print(f"[green]Successfully repaired: {total_repaired}[/green]")
    console.print(f"[red]Failed repairs: {total_failed}[/red]")
    console.print(f"[blue]Duration: {duration:.1f} seconds[/blue]\n")
    
    # Per-year breakdown
    console.print("[cyan]Per-Year Results:[/cyan]")
    for result in results:
        console.print(f"  {result['year']}: {result['repaired']}/{result['issues_found']} repaired")
    
    # Save results
    results_file = Path(f"repair_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(results_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': duration,
            'total_scanned': total_scanned,
            'total_issues': total_issues,
            'total_repaired': total_repaired,
            'total_failed': total_failed,
            'results': results
        }, f, indent=2)
    
    console.print(f"\n[green]Results saved to: {results_file}[/green]")
    
    # Final cleanup of any remaining browser processes
    console.print("[yellow]Final browser cleanup...[/yellow]")
    cleanup_browsers()
    console.print("[green]✓ All browser processes terminated[/green]")


if __name__ == "__main__":
    main()
