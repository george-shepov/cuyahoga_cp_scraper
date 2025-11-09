"""
Comprehensive Cuyahoga County Court Statistics and Analytics Module
Analyzes case data to identify patterns, costs, judicial efficiency, and potential issues
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict, field
from datetime import datetime
import statistics as stats_module

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
import seaborn as sns
import pandas as pd
import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()


@dataclass
class CaseStats:
    """Statistics for a single case"""
    case_number: str
    year: int
    status: str
    judge: Optional[str]
    charges: List[str] = field(default_factory=list)
    dismissed: bool = False
    convicted: bool = False
    has_attorney: bool = False
    attorney_type: Optional[str] = None  # "private" or "public" or "appointed"
    attorneys: List[str] = field(default_factory=list)
    arresting_agency: Optional[str] = None
    cost_total: float = 0.0
    costs: Dict[str, float] = field(default_factory=dict)
    has_warrant: bool = False
    defendant_name: Optional[str] = None
    case_id: Optional[str] = None
    docket_entries: List[Dict] = field(default_factory=list)
    is_drug_possession: bool = False
    is_repeat_offender: bool = False
    is_probation_violation: bool = False
    outcome: Optional[str] = None  # "imprisoned", "dismissed", "plea", "convicted", "pending"


@dataclass
class YearlyStatistics:
    """Aggregated statistics for a year"""
    year: int
    total_cases: int = 0
    cases_by_status: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    cases_by_judge: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    cases_by_charge: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    cases_by_agency: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    attorneys: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Representation statistics
    with_attorney: int = 0
    without_attorney: int = 0
    public_defender: int = 0
    private_attorney: int = 0
    appointed_attorney: int = 0
    
    # Outcomes
    dismissed_cases: int = 0
    convicted_cases: int = 0
    imprisoned_cases: int = 0
    pending_cases: int = 0
    plea_cases: int = 0
    
    # Cost analysis
    total_costs: float = 0.0
    costs_by_category: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    avg_cost_per_case: float = 0.0
    
    # Charges
    drug_possession_cases: int = 0
    warrant_count: int = 0
    
    # Repeat offenders
    repeat_offender_cases: int = 0
    probation_violation_cases: int = 0
    first_time_offenders: int = 0
    
    # Judge statistics
    judge_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    case_details: List[CaseStats] = field(default_factory=list)


class CaseDataAnalyzer:
    """Analyze case data from JSON files"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.stats = YearlyStatistics(year=0)
        
    def load_cases(self, year: int, limit: Optional[int] = None) -> List[CaseStats]:
        """Load all case data for a given year"""
        cases = []
        year_dir = self.data_dir / str(year)
        
        if not year_dir.exists():
            console.print(f"[red]Year directory not found: {year_dir}[/red]")
            return cases
        
        json_files = list(year_dir.glob("*.json"))
        console.print(f"[cyan]Found {len(json_files)} case files for year {year}[/cyan]")
        
        for idx, json_file in enumerate(json_files[:limit] if limit else json_files):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                case = self._parse_case_data(data)
                if case:
                    cases.append(case)
                    
                if (idx + 1) % 100 == 0:
                    console.print(f"[blue]  Loaded {idx + 1}/{len(json_files)} cases[/blue]")
                    
            except Exception as e:
                console.print(f"[yellow]Warning: Could not parse {json_file}: {e}[/yellow]")
        
        console.print(f"[green]✓ Loaded {len(cases)} cases for year {year}[/green]")
        return cases
    
    def _parse_case_data(self, data: Dict) -> Optional[CaseStats]:
        """Parse individual case JSON data into CaseStats"""
        try:
            if not data.get("metadata", {}).get("exists", False):
                return None
            
            metadata = data.get("metadata", {})
            summary = data.get("summary", {})
            docket = data.get("docket", [])
            costs = data.get("costs", [])
            defendant = data.get("defendant", {})
            attorneys = data.get("attorneys", [])
            
            case_number = f"{metadata.get('year')}-{metadata.get('number', 0):06d}"
            case_id = metadata.get("case_id", "")
            
            # Extract status
            status = summary.get("Case Status", "Unknown")
            
            # Extract judge
            judge = summary.get("Judge", None) or summary.get("Assigned Judge", None)
            
            # Extract charges
            charges = self._extract_charges(summary, docket)
            
            # Determine outcomes
            dismissed = "dismissed" in status.lower()
            convicted = "conviction" in status.lower() or "convicted" in status.lower()
            outcome = self._determine_outcome(status, docket)
            
            # Attorney information
            has_attorney = len(attorneys) > 0
            attorney_list = [att.get("name", "Unknown") for att in attorneys]
            attorney_type = self._determine_attorney_type(attorney_list)
            
            # Arresting agency
            arresting_agency = summary.get("Arresting Agency", None)
            
            # Parse costs
            cost_total = 0.0
            cost_dict = {}
            for cost_entry in costs:
                if isinstance(cost_entry, dict):
                    category = cost_entry.get("category", "Unknown")
                    try:
                        amount = float(cost_entry.get("amount", 0))
                        cost_dict[category] = amount
                        cost_total += amount
                    except (ValueError, TypeError):
                        pass
            
            # Check for warrant
            has_warrant = any("warrant" in str(entry).lower() for entry in docket)
            
            # Check if drug possession
            is_drug_possession = any(
                "drug" in str(charge).lower() and "possession" in str(charge).lower()
                for charge in charges
            )
            
            # Check probation violation
            is_probation_violation = any(
                "probation" in str(entry).lower() for entry in docket
            )
            
            return CaseStats(
                case_number=case_number,
                year=metadata.get("year", 0),
                status=status,
                judge=judge,
                charges=charges,
                dismissed=dismissed,
                convicted=convicted,
                has_attorney=has_attorney,
                attorney_type=attorney_type,
                attorneys=attorney_list,
                arresting_agency=arresting_agency,
                cost_total=cost_total,
                costs=cost_dict,
                has_warrant=has_warrant,
                defendant_name=defendant.get("Name", None),
                case_id=case_id,
                docket_entries=docket,
                is_drug_possession=is_drug_possession,
                is_probation_violation=is_probation_violation,
                outcome=outcome
            )
        except Exception as e:
            console.print(f"[yellow]Error parsing case: {e}[/yellow]")
            return None
    
    def _extract_charges(self, summary: Dict, docket: List) -> List[str]:
        """Extract charges from summary and docket"""
        charges = set()
        
        # From summary
        if "Charges" in summary:
            charge_str = summary["Charges"]
            # Simple split by comma
            charges.update([c.strip() for c in charge_str.split(",")])
        
        # From docket entries (look for charge-related entries)
        for entry in docket:
            if isinstance(entry, dict):
                description = entry.get("description", "").lower()
                if any(keyword in description for keyword in ["charge", "felony", "misdemeanor", "offense"]):
                    if "description" in entry:
                        charges.add(entry.get("description", ""))
        
        return list(charges)
    
    def _determine_attorney_type(self, attorneys: List[str]) -> Optional[str]:
        """Determine if attorney is public defender, private, or court appointed"""
        if not attorneys:
            return None
        
        # Simple heuristics
        for att in attorneys:
            att_lower = att.lower()
            if "public defender" in att_lower or "pd" in att_lower:
                return "public"
            if "appointed" in att_lower:
                return "appointed"
        
        # Default to private if attorney listed
        return "private"
    
    def _determine_outcome(self, status: str, docket: List) -> Optional[str]:
        """Determine case outcome"""
        status_lower = status.lower()
        
        if "dismiss" in status_lower:
            return "dismissed"
        elif "convicted" in status_lower or "conviction" in status_lower:
            return "convicted"
        elif "plea" in status_lower:
            return "plea"
        elif "imprisoned" in status_lower or "prison" in status_lower:
            return "imprisoned"
        elif "pending" in status_lower or "open" in status_lower:
            return "pending"
        
        # Check docket entries
        for entry in docket:
            if isinstance(entry, dict):
                desc = entry.get("description", "").lower()
                if "dismissed" in desc:
                    return "dismissed"
                if "sentenced" in desc or "prison" in desc:
                    return "imprisoned"
        
        return "pending"
    
    def analyze_year(self, cases: List[CaseStats]) -> YearlyStatistics:
        """Aggregate statistics for all cases in a year"""
        if not cases:
            return self.stats
        
        year = cases[0].year
        stats = YearlyStatistics(year=year)
        stats.total_cases = len(cases)
        stats.case_details = cases
        
        # Count by status
        status_counter = Counter(case.status for case in cases)
        stats.cases_by_status = dict(status_counter)
        
        # Count by judge
        judge_cases = defaultdict(list)
        for case in cases:
            if case.judge:
                stats.cases_by_judge[case.judge] += 1
                judge_cases[case.judge].append(case)
        
        # Judge statistics
        for judge, judge_case_list in judge_cases.items():
            stats.judge_stats[judge] = {
                "total_cases": len(judge_case_list),
                "convicted": sum(1 for c in judge_case_list if c.convicted),
                "dismissed": sum(1 for c in judge_case_list if c.dismissed),
                "avg_cost": stats_module.mean([c.cost_total for c in judge_case_list if c.cost_total > 0]) if any(c.cost_total > 0 for c in judge_case_list) else 0
            }
        
        # Count by charge
        all_charges = []
        for case in cases:
            all_charges.extend(case.charges)
        charge_counter = Counter(all_charges)
        stats.cases_by_charge = dict(charge_counter)
        
        # Count by arresting agency
        agency_counter = Counter(case.arresting_agency for case in cases if case.arresting_agency)
        stats.cases_by_agency = dict(agency_counter)
        
        # Attorney statistics
        attorney_stats = defaultdict(lambda: {"total": 0, "convicted": 0, "dismissed": 0, "type": None})
        for case in cases:
            for attorney in case.attorneys:
                attorney_stats[attorney]["total"] += 1
                attorney_stats[attorney]["type"] = case.attorney_type
                if case.convicted:
                    attorney_stats[attorney]["convicted"] += 1
                if case.dismissed:
                    attorney_stats[attorney]["dismissed"] += 1
        
        stats.attorneys = dict(attorney_stats)
        
        # Representation stats
        stats.with_attorney = sum(1 for case in cases if case.has_attorney)
        stats.without_attorney = len(cases) - stats.with_attorney
        stats.public_defender = sum(1 for case in cases if case.attorney_type == "public")
        stats.private_attorney = sum(1 for case in cases if case.attorney_type == "private")
        stats.appointed_attorney = sum(1 for case in cases if case.attorney_type == "appointed")
        
        # Outcomes
        stats.dismissed_cases = sum(1 for case in cases if case.dismissed)
        stats.convicted_cases = sum(1 for case in cases if case.convicted)
        stats.imprisoned_cases = sum(1 for case in cases if case.outcome == "imprisoned")
        stats.pending_cases = sum(1 for case in cases if case.outcome == "pending")
        stats.plea_cases = sum(1 for case in cases if case.outcome == "plea")
        
        # Costs
        stats.total_costs = sum(case.cost_total for case in cases)
        for case in cases:
            for category, amount in case.costs.items():
                stats.costs_by_category[category] += amount
        
        if len(cases) > 0:
            stats.avg_cost_per_case = stats.total_costs / len(cases)
        
        # Drug possession
        stats.drug_possession_cases = sum(1 for case in cases if case.is_drug_possession)
        
        # Warrants
        stats.warrant_count = sum(1 for case in cases if case.has_warrant)
        
        # Repeat offenders (simple heuristic)
        stats.repeat_offender_cases = sum(1 for case in cases if case.is_repeat_offender)
        stats.probation_violation_cases = sum(1 for case in cases if case.is_probation_violation)
        stats.first_time_offenders = stats.total_cases - stats.repeat_offender_cases
        
        self.stats = stats
        return stats
    
    def generate_summary_table(self) -> Table:
        """Generate summary statistics table"""
        stats = self.stats
        
        table = Table(title=f"📊 Cuyahoga County {stats.year} Case Statistics Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Count/Value", style="green")
        table.add_column("Percentage", style="yellow")
        
        # Cases
        table.add_row("Total Cases", str(stats.total_cases), "100%")
        
        # Representation
        with_pct = (stats.with_attorney / stats.total_cases * 100) if stats.total_cases > 0 else 0
        table.add_row("With Attorney", str(stats.with_attorney), f"{with_pct:.1f}%")
        
        without_pct = (stats.without_attorney / stats.total_cases * 100) if stats.total_cases > 0 else 0
        table.add_row("Without Attorney", str(stats.without_attorney), f"{without_pct:.1f}%")
        
        table.add_row("  └─ Public Defender", str(stats.public_defender), 
                     f"{(stats.public_defender / stats.total_cases * 100):.1f}%")
        table.add_row("  └─ Private Attorney", str(stats.private_attorney), 
                     f"{(stats.private_attorney / stats.total_cases * 100):.1f}%")
        table.add_row("  └─ Court Appointed", str(stats.appointed_attorney), 
                     f"{(stats.appointed_attorney / stats.total_cases * 100):.1f}%")
        
        # Outcomes
        table.add_row("", "", "")
        table.add_row("Dismissed Cases", str(stats.dismissed_cases), 
                     f"{(stats.dismissed_cases / stats.total_cases * 100):.1f}%")
        table.add_row("Convicted Cases", str(stats.convicted_cases), 
                     f"{(stats.convicted_cases / stats.total_cases * 100):.1f}%")
        table.add_row("Imprisoned", str(stats.imprisoned_cases), 
                     f"{(stats.imprisoned_cases / stats.total_cases * 100):.1f}%")
        table.add_row("Pending", str(stats.pending_cases), 
                     f"{(stats.pending_cases / stats.total_cases * 100):.1f}%")
        table.add_row("Plea Agreements", str(stats.plea_cases), 
                     f"{(stats.plea_cases / stats.total_cases * 100):.1f}%")
        
        # Charges and agencies
        table.add_row("", "", "")
        table.add_row("Drug Possession Cases", str(stats.drug_possession_cases), 
                     f"{(stats.drug_possession_cases / stats.total_cases * 100):.1f}%")
        table.add_row("Probation Violation Cases", str(stats.probation_violation_cases), 
                     f"{(stats.probation_violation_cases / stats.total_cases * 100):.1f}%")
        table.add_row("Warrants Issued", str(stats.warrant_count), "")
        
        # Costs
        table.add_row("", "", "")
        table.add_row("Total Costs", f"${stats.total_costs:,.2f}", "")
        table.add_row("Avg Cost per Case", f"${stats.avg_cost_per_case:,.2f}", "")
        
        return table
    
    def generate_judge_table(self) -> Table:
        """Generate judge statistics table"""
        stats = self.stats
        
        table = Table(title="⚖️ Judge Statistics")
        table.add_column("Judge", style="cyan")
        table.add_column("Cases", justify="right", style="green")
        table.add_column("Convicted", justify="right", style="yellow")
        table.add_column("Dismissed", justify="right", style="blue")
        table.add_column("Conv. Rate", justify="right", style="magenta")
        table.add_column("Avg Cost", justify="right", style="red")
        
        # Sort by number of cases
        sorted_judges = sorted(stats.judge_stats.items(), key=lambda x: x[1]["total_cases"], reverse=True)
        
        for judge, judge_stat in sorted_judges[:20]:  # Top 20 judges
            total = judge_stat["total_cases"]
            convicted = judge_stat["convicted"]
            dismissed = judge_stat["dismissed"]
            conv_rate = (convicted / total * 100) if total > 0 else 0
            avg_cost = judge_stat["avg_cost"]
            
            table.add_row(
                judge or "Unknown",
                str(total),
                str(convicted),
                str(dismissed),
                f"{conv_rate:.1f}%",
                f"${avg_cost:,.2f}"
            )
        
        return table
    
    def generate_attorney_table(self) -> Table:
        """Generate attorney statistics table"""
        stats = self.stats
        
        table = Table(title="👨‍⚖️ Top Attorneys by Case Volume")
        table.add_column("Attorney", style="cyan")
        table.add_column("Cases", justify="right", style="green")
        table.add_column("Type", justify="right", style="blue")
        table.add_column("Convicted", justify="right", style="yellow")
        table.add_column("Dismissed", justify="right", style="magenta")
        table.add_column("Success %", justify="right", style="red")
        
        # Sort by case count
        sorted_attorneys = sorted(stats.attorneys.items(), key=lambda x: x[1]["total"], reverse=True)
        
        for attorney, att_stat in sorted_attorneys[:15]:  # Top 15 attorneys
            total = att_stat["total"]
            convicted = att_stat["convicted"]
            dismissed = att_stat["dismissed"]
            success_rate = (dismissed / total * 100) if total > 0 else 0
            att_type = att_stat.get("type", "Unknown") or "Unknown"
            
            table.add_row(
                attorney,
                str(total),
                att_type,
                str(convicted),
                str(dismissed),
                f"{success_rate:.1f}%"
            )
        
        return table
    
    def generate_charges_table(self) -> Table:
        """Generate charges statistics table"""
        stats = self.stats
        
        table = Table(title="📋 Top Charges")
        table.add_column("Charge", style="cyan")
        table.add_column("Count", justify="right", style="green")
        table.add_column("Percentage", justify="right", style="yellow")
        
        # Sort by count
        sorted_charges = sorted(stats.cases_by_charge.items(), key=lambda x: x[1], reverse=True)
        
        for charge, count in sorted_charges[:20]:  # Top 20 charges
            pct = (count / stats.total_cases * 100) if stats.total_cases > 0 else 0
            table.add_row(charge[:60], str(count), f"{pct:.1f}%")
        
        return table
    
    def generate_agency_table(self) -> Table:
        """Generate arresting agency statistics table"""
        stats = self.stats
        
        table = Table(title="🚔 Arresting Agencies")
        table.add_column("Agency", style="cyan")
        table.add_column("Cases", justify="right", style="green")
        table.add_column("Percentage", justify="right", style="yellow")
        
        # Sort by count
        sorted_agencies = sorted(stats.cases_by_agency.items(), key=lambda x: x[1], reverse=True)
        
        for agency, count in sorted_agencies:
            pct = (count / stats.total_cases * 100) if stats.total_cases > 0 else 0
            table.add_row(agency[:50], str(count), f"{pct:.1f}%")
        
        return table


class StatisticsVisualizer:
    """Create visualizations for case statistics"""
    
    def __init__(self, stats: YearlyStatistics, output_dir: Path):
        self.stats = stats
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set style
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = (14, 8)
    
    def create_all_visualizations(self):
        """Create all chart visualizations"""
        console.print("[cyan]Generating visualizations...[/cyan]")
        
        self.pie_charges()
        console.print("[green]✓ Charges pie chart[/green]")
        
        self.pie_agencies()
        console.print("[green]✓ Agencies pie chart[/green]")
        
        self.pie_representation()
        console.print("[green]✓ Attorney representation chart[/green]")
        
        self.pie_outcomes()
        console.print("[green]✓ Case outcomes chart[/green]")
        
        self.bar_top_attorneys()
        console.print("[green]✓ Top attorneys chart[/green]")
        
        self.bar_judge_outcomes()
        console.print("[green]✓ Judge outcomes chart[/green]")
        
        self.bar_cost_categories()
        console.print("[green]✓ Cost categories chart[/green]")
        
        self.create_multi_chart()
        console.print("[green]✓ Multi-metric dashboard[/green]")
    
    def pie_charges(self):
        """Create pie chart of charges"""
        charges = self.stats.cases_by_charge
        if not charges:
            return
        
        # Get top 12 charges
        sorted_charges = sorted(charges.items(), key=lambda x: x[1], reverse=True)[:12]
        labels = [c[0][:40] for c in sorted_charges]
        values = [c[1] for c in sorted_charges]
        
        fig, ax = plt.subplots(figsize=(14, 10))
        colors = plt.cm.Set3(range(len(labels)))
        wedges, texts, autotexts = ax.pie(values, labels=labels, autopct='%1.1f%%', 
                                           colors=colors, startangle=90)
        
        for text in texts:
            text.set_fontsize(10)
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(9)
            autotext.set_weight('bold')
        
        ax.set_title(f"Top Charges in Cuyahoga County {self.stats.year}", fontsize=16, fontweight='bold')
        plt.tight_layout()
        plt.savefig(self.output_dir / "01_charges_pie.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def pie_agencies(self):
        """Create pie chart of arresting agencies"""
        agencies = self.stats.cases_by_agency
        if not agencies:
            return
        
        # Get top 10 agencies
        sorted_agencies = sorted(agencies.items(), key=lambda x: x[1], reverse=True)[:10]
        labels = [a[0][:40] for a in sorted_agencies]
        values = [a[1] for a in sorted_agencies]
        
        fig, ax = plt.subplots(figsize=(12, 8))
        colors = plt.cm.Pastel1(range(len(labels)))
        wedges, texts, autotexts = ax.pie(values, labels=labels, autopct='%1.1f%%',
                                           colors=colors, startangle=90)
        
        for text in texts:
            text.set_fontsize(10)
        for autotext in autotexts:
            autotext.set_color('black')
            autotext.set_fontsize(9)
            autotext.set_weight('bold')
        
        ax.set_title(f"Arresting Agencies in Cuyahoga County {self.stats.year}", fontsize=16, fontweight='bold')
        plt.tight_layout()
        plt.savefig(self.output_dir / "02_agencies_pie.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def pie_representation(self):
        """Create pie chart of attorney representation"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # Overall representation
        with_att = self.stats.with_attorney
        without_att = self.stats.without_attorney
        ax1.pie([with_att, without_att], labels=['With Attorney', 'Without Attorney'],
               autopct='%1.1f%%', colors=['#66b3ff', '#ff9999'],
               explode=(0.05, 0.05), startangle=90)
        ax1.set_title(f"Attorney Representation {self.stats.year}", fontweight='bold')
        
        # Type of representation
        pub = self.stats.public_defender
        priv = self.stats.private_attorney
        app = self.stats.appointed_attorney
        ax2.pie([pub, priv, app], labels=['Public Defender', 'Private', 'Court Appointed'],
               autopct='%1.1f%%', colors=['#99ff99', '#ffcc99', '#ff99cc'],
               explode=(0.05, 0.05, 0.05), startangle=90)
        ax2.set_title(f"Type of Attorney Representation {self.stats.year}", fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "03_representation_pie.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def pie_outcomes(self):
        """Create pie chart of case outcomes"""
        outcomes = {
            'Dismissed': self.stats.dismissed_cases,
            'Convicted': self.stats.convicted_cases,
            'Imprisoned': self.stats.imprisoned_cases,
            'Pending': self.stats.pending_cases,
            'Plea': self.stats.plea_cases
        }
        
        # Filter out zero values
        outcomes = {k: v for k, v in outcomes.items() if v > 0}
        
        fig, ax = plt.subplots(figsize=(10, 8))
        colors = plt.cm.RdYlGn(np.linspace(0.3, 0.7, len(outcomes)))
        wedges, texts, autotexts = ax.pie(outcomes.values(), labels=outcomes.keys(), 
                                           autopct='%1.1f%%', colors=colors, startangle=90)
        
        for text in texts:
            text.set_fontsize(12)
            text.set_fontweight('bold')
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(10)
            autotext.set_fontweight('bold')
        
        ax.set_title(f"Case Outcomes in Cuyahoga County {self.stats.year}", fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.savefig(self.output_dir / "04_outcomes_pie.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def bar_top_attorneys(self):
        """Create bar chart of top attorneys"""
        # Get top 15 attorneys
        sorted_attorneys = sorted(self.stats.attorneys.items(), 
                                 key=lambda x: x[1]["total"], reverse=True)[:15]
        
        if not sorted_attorneys:
            return
        
        names = [a[0][:30] for a in sorted_attorneys]
        cases = [a[1]["total"] for a in sorted_attorneys]
        dismissed = [a[1]["dismissed"] for a in sorted_attorneys]
        
        fig, ax = plt.subplots(figsize=(14, 8))
        x = np.arange(len(names))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, cases, width, label='Total Cases', color='steelblue')
        bars2 = ax.bar(x + width/2, dismissed, width, label='Dismissed', color='lightcoral')
        
        ax.set_xlabel('Attorney', fontweight='bold')
        ax.set_ylabel('Number of Cases', fontweight='bold')
        ax.set_title(f'Top 15 Attorneys by Case Volume {self.stats.year}', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=45, ha='right')
        ax.legend()
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "05_top_attorneys_bar.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def bar_judge_outcomes(self):
        """Create bar chart of judge outcomes"""
        # Get top 12 judges
        sorted_judges = sorted(self.stats.judge_stats.items(), 
                              key=lambda x: x[1]["total_cases"], reverse=True)[:12]
        
        if not sorted_judges:
            return
        
        names = [j[0][:25] or "Unknown" for j in sorted_judges]
        convicted = [j[1]["convicted"] for j in sorted_judges]
        dismissed = [j[1]["dismissed"] for j in sorted_judges]
        
        fig, ax = plt.subplots(figsize=(14, 8))
        x = np.arange(len(names))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, convicted, width, label='Convicted', color='#ff6b6b')
        bars2 = ax.bar(x + width/2, dismissed, width, label='Dismissed', color='#51cf66')
        
        ax.set_xlabel('Judge', fontweight='bold')
        ax.set_ylabel('Number of Cases', fontweight='bold')
        ax.set_title(f'Judge Case Outcomes {self.stats.year}', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=45, ha='right')
        ax.legend()
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "06_judge_outcomes_bar.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def bar_cost_categories(self):
        """Create bar chart of cost categories"""
        costs = self.stats.costs_by_category
        if not costs:
            return
        
        # Sort by amount
        sorted_costs = sorted(costs.items(), key=lambda x: x[1], reverse=True)[:10]
        
        categories = [c[0][:35] for c in sorted_costs]
        amounts = [c[1] for c in sorted_costs]
        
        fig, ax = plt.subplots(figsize=(14, 8))
        bars = ax.barh(categories, amounts, color=plt.cm.Spectral(np.linspace(0, 1, len(categories))))
        
        ax.set_xlabel('Total Cost ($)', fontweight='bold')
        ax.set_title(f'Cost Categories in Cuyahoga County {self.stats.year}', fontsize=14, fontweight='bold')
        ax.grid(axis='x', alpha=0.3)
        
        # Add value labels
        for bar in bars:
            width = bar.get_width()
            ax.text(width, bar.get_y() + bar.get_height()/2, 
                   f'${width/1000:.0f}K', ha='left', va='center', fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / "07_cost_categories_bar.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def create_multi_chart(self):
        """Create a dashboard with multiple metrics"""
        fig = plt.figure(figsize=(16, 12))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
        
        # Representation pie
        ax1 = fig.add_subplot(gs[0, 0])
        ax1.pie([self.stats.with_attorney, self.stats.without_attorney],
               labels=['With Att.', 'Without'], autopct='%1.0f%%',
               colors=['#66b3ff', '#ff9999'])
        ax1.set_title('Representation', fontweight='bold', fontsize=11)
        
        # Outcomes pie
        ax2 = fig.add_subplot(gs[0, 1])
        outcomes = [self.stats.dismissed_cases, self.stats.convicted_cases, 
                   self.stats.imprisoned_cases, self.stats.pending_cases]
        labels = ['Dismissed', 'Convicted', 'Imprisoned', 'Pending']
        ax2.pie(outcomes, labels=labels, autopct='%1.0f%%')
        ax2.set_title('Outcomes', fontweight='bold', fontsize=11)
        
        # Drug possession pie
        ax3 = fig.add_subplot(gs[0, 2])
        drug_cases = self.stats.drug_possession_cases
        other_cases = self.stats.total_cases - drug_cases
        ax3.pie([drug_cases, other_cases], labels=['Drug Cases', 'Other'],
               autopct='%1.0f%%', colors=['#ff9999', '#99ff99'])
        ax3.set_title('Drug Possession Cases', fontweight='bold', fontsize=11)
        
        # Top charges
        ax4 = fig.add_subplot(gs[1, :])
        top_charges = sorted(self.stats.cases_by_charge.items(), 
                            key=lambda x: x[1], reverse=True)[:8]
        charges = [c[0][:25] for c in top_charges]
        counts = [c[1] for c in top_charges]
        ax4.barh(charges, counts, color=plt.cm.viridis(np.linspace(0, 1, len(charges))))
        ax4.set_xlabel('Count', fontweight='bold')
        ax4.set_title('Top 8 Charges', fontweight='bold', fontsize=11)
        ax4.grid(axis='x', alpha=0.3)
        
        # Top agencies
        ax5 = fig.add_subplot(gs[2, 0])
        top_agencies = sorted(self.stats.cases_by_agency.items(), 
                             key=lambda x: x[1], reverse=True)[:5]
        agencies = [a[0][:15] for a in top_agencies]
        counts = [a[1] for a in top_agencies]
        ax5.bar(range(len(agencies)), counts, color='steelblue')
        ax5.set_xticks(range(len(agencies)))
        ax5.set_xticklabels(agencies, rotation=45, ha='right')
        ax5.set_title('Top 5 Agencies', fontweight='bold', fontsize=11)
        ax5.grid(axis='y', alpha=0.3)
        
        # Cost breakdown
        ax6 = fig.add_subplot(gs[2, 1])
        top_costs = sorted(self.stats.costs_by_category.items(), 
                          key=lambda x: x[1], reverse=True)[:5]
        cost_labels = [c[0][:15] for c in top_costs]
        cost_amounts = [c[1] for c in top_costs]
        ax6.pie(cost_amounts, labels=cost_labels, autopct='%1.0f%%')
        ax6.set_title('Cost Categories', fontweight='bold', fontsize=11)
        
        # Statistics text
        ax7 = fig.add_subplot(gs[2, 2])
        ax7.axis('off')
        stats_text = f"""
        Total Cases: {self.stats.total_cases:,}
        
        Dismissed: {self.stats.dismissed_cases} ({self.stats.dismissed_cases/self.stats.total_cases*100:.1f}%)
        Convicted: {self.stats.convicted_cases} ({self.stats.convicted_cases/self.stats.total_cases*100:.1f}%)
        Imprisoned: {self.stats.imprisoned_cases}
        
        Avg Cost: ${self.stats.avg_cost_per_case:,.0f}
        Total Cost: ${self.stats.total_costs:,.0f}
        
        Drug Cases: {self.stats.drug_possession_cases}
        Warrants: {self.stats.warrant_count}
        """
        ax7.text(0.1, 0.9, stats_text, transform=ax7.transAxes, fontsize=10,
                verticalalignment='top', family='monospace',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        fig.suptitle(f'Cuyahoga County Court Statistics Dashboard {self.stats.year}',
                    fontsize=16, fontweight='bold')
        
        plt.savefig(self.output_dir / "00_dashboard.png", dpi=300, bbox_inches='tight')
        plt.close()


def generate_yearly_report(data_dir: Path, year: int, limit: Optional[int] = None):
    """Generate complete yearly report"""
    console.rule(f"[bold cyan]📊 Generating {year} Statistics Report[/bold cyan]")
    
    # Load and analyze
    analyzer = CaseDataAnalyzer(data_dir)
    cases = analyzer.load_cases(year, limit=limit)
    
    if not cases:
        console.print(f"[red]No cases found for year {year}[/red]")
        return
    
    stats = analyzer.analyze_year(cases)
    
    # Print tables
    console.print()
    console.print(analyzer.generate_summary_table())
    
    console.print()
    console.print(analyzer.generate_judge_table())
    
    console.print()
    console.print(analyzer.generate_attorney_table())
    
    console.print()
    console.print(analyzer.generate_charges_table())
    
    console.print()
    console.print(analyzer.generate_agency_table())
    
    # Generate visualizations
    output_dir = Path("./statistics_output") / str(year)
    visualizer = StatisticsVisualizer(stats, output_dir)
    visualizer.create_all_visualizations()
    
    # Save JSON report
    report_data = {
        "year": year,
        "summary": {
            "total_cases": stats.total_cases,
            "with_attorney": stats.with_attorney,
            "without_attorney": stats.without_attorney,
            "public_defender": stats.public_defender,
            "private_attorney": stats.private_attorney,
            "appointed_attorney": stats.appointed_attorney,
            "dismissed_cases": stats.dismissed_cases,
            "convicted_cases": stats.convicted_cases,
            "imprisoned_cases": stats.imprisoned_cases,
            "pending_cases": stats.pending_cases,
            "plea_cases": stats.plea_cases,
            "drug_possession_cases": stats.drug_possession_cases,
            "warrant_count": stats.warrant_count,
            "probation_violation_cases": stats.probation_violation_cases,
            "total_costs": stats.total_costs,
            "avg_cost_per_case": stats.avg_cost_per_case,
        },
        "judges": stats.judge_stats,
        "charges": stats.cases_by_charge,
        "agencies": stats.cases_by_agency,
        "top_attorneys": {
            name: {
                "total": stat["total"],
                "convicted": stat["convicted"],
                "dismissed": stat["dismissed"],
                "type": stat.get("type")
            }
            for name, stat in sorted(stats.attorneys.items(), 
                                    key=lambda x: x[1]["total"], 
                                    reverse=True)[:20]
        }
    }
    
    report_file = output_dir / "report.json"
    report_file.write_text(json.dumps(report_data, indent=2))
    
    console.print(f"\n[green]✅ Report generated successfully![/green]")
    console.print(f"[cyan]Charts saved to: {output_dir}[/cyan]")
    console.print(f"[cyan]JSON report: {report_file}[/cyan]")


if __name__ == "__main__":
    # Example usage
    data_dir = Path("./out")
    generate_yearly_report(data_dir, year=2025)
