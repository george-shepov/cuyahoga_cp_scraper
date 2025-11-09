"""
Interactive HTML Dashboard Generator for Court Statistics
Creates a responsive web dashboard from case data analysis
"""

import json
from pathlib import Path
from typing import Dict, List
from statistics import YearlyStatistics

def generate_html_dashboard(stats: YearlyStatistics, output_file: Path):
    """Generate an interactive HTML dashboard"""
    
    # Calculate percentages
    total = stats.total_cases
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cuyahoga County Court Statistics {stats.year}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        
        .main-content {{
            padding: 30px;
        }}
        
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        .card {{
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-left: 4px solid #667eea;
        }}
        
        .card.warning {{
            border-left-color: #ff6b6b;
        }}
        
        .card.success {{
            border-left-color: #51cf66;
        }}
        
        .card.info {{
            border-left-color: #4dabf7;
        }}
        
        .card h3 {{
            color: #333;
            font-size: 0.9em;
            text-transform: uppercase;
            margin-bottom: 10px;
            opacity: 0.7;
        }}
        
        .card .value {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}
        
        .card .subtext {{
            font-size: 0.8em;
            color: #666;
            margin-top: 5px;
        }}
        
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 30px;
            margin-bottom: 40px;
        }}
        
        .chart-container {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            position: relative;
            height: 400px;
        }}
        
        .chart-container h3 {{
            color: #333;
            margin-bottom: 15px;
            font-size: 1.2em;
        }}
        
        .chart-inner {{
            position: relative;
            height: 350px;
        }}
        
        .tables-section {{
            background: white;
            padding: 30px;
            margin-top: 30px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
        }}
        
        table h3 {{
            color: #333;
            margin-bottom: 15px;
        }}
        
        th {{
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #eee;
        }}
        
        tr:hover {{
            background: #f9f9f9;
        }}
        
        tr:nth-child(even) {{
            background: #f5f5f5;
        }}
        
        .highlight {{
            background: #fff3cd;
            font-weight: bold;
        }}
        
        .positive {{
            color: #51cf66;
            font-weight: bold;
        }}
        
        .negative {{
            color: #ff6b6b;
            font-weight: bold;
        }}
        
        .footer {{
            background: #f9f9f9;
            padding: 20px;
            text-align: center;
            border-top: 1px solid #eee;
            color: #666;
            font-size: 0.9em;
        }}
        
        .key-findings {{
            background: #e7f5ff;
            padding: 20px;
            border-left: 4px solid #4dabf7;
            border-radius: 4px;
            margin-bottom: 30px;
        }}
        
        .key-findings h3 {{
            color: #4dabf7;
            margin-bottom: 10px;
        }}
        
        .key-findings ul {{
            list-style: none;
            padding-left: 0;
        }}
        
        .key-findings li {{
            padding: 5px 0;
            color: #333;
        }}
        
        .key-findings li:before {{
            content: "📊 ";
            margin-right: 10px;
        }}
        
        @media (max-width: 768px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
            
            header h1 {{
                font-size: 1.8em;
            }}
            
            .summary-cards {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>⚖️ Cuyahoga County Court Statistics</h1>
            <p>Year {stats.year} Comprehensive Analysis Dashboard</p>
        </header>
        
        <div class="main-content">
            <div class="key-findings">
                <h3>🔍 Key Findings & Analysis</h3>
                <ul>
                    <li><strong>Total Cases Analyzed:</strong> {stats.total_cases:,} criminal cases</li>
                    <li><strong>Representation Gap:</strong> {stats.without_attorney} cases ({(stats.without_attorney/total*100):.1f}%) proceeded without attorney representation</li>
                    <li><strong>Conviction Rate:</strong> {(stats.convicted_cases/total*100):.1f}% conviction rate overall</li>
                    <li><strong>Dismissal Rate:</strong> {(stats.dismissed_cases/total*100):.1f}% of cases dismissed</li>
                    <li><strong>Total System Costs:</strong> ${stats.total_costs:,.0f} ({stats.avg_cost_per_case:.0f} per case average)</li>
                    <li><strong>Drug Possession Cases:</strong> {stats.drug_possession_cases} ({(stats.drug_possession_cases/total*100):.1f}%)</li>
                    <li><strong>Probation Violations:</strong> {stats.probation_violation_cases} cases</li>
                    <li><strong>Warrants Issued:</strong> {stats.warrant_count} warrants</li>
                </ul>
            </div>
            
            <div class="summary-cards">
                <div class="card info">
                    <h3>Total Cases</h3>
                    <div class="value">{stats.total_cases:,}</div>
                </div>
                
                <div class="card">
                    <h3>With Attorney</h3>
                    <div class="value">{stats.with_attorney}</div>
                    <div class="subtext">{(stats.with_attorney/total*100):.1f}% of cases</div>
                </div>
                
                <div class="card warning">
                    <h3>Without Attorney</h3>
                    <div class="value">{stats.without_attorney}</div>
                    <div class="subtext">{(stats.without_attorney/total*100):.1f}% of cases</div>
                </div>
                
                <div class="card success">
                    <h3>Dismissed</h3>
                    <div class="value">{stats.dismissed_cases}</div>
                    <div class="subtext">{(stats.dismissed_cases/total*100):.1f}% of cases</div>
                </div>
                
                <div class="card warning">
                    <h3>Convicted</h3>
                    <div class="value">{stats.convicted_cases}</div>
                    <div class="subtext">{(stats.convicted_cases/total*100):.1f}% of cases</div>
                </div>
                
                <div class="card warning">
                    <h3>Imprisoned</h3>
                    <div class="value">{stats.imprisoned_cases}</div>
                    <div class="subtext">Cases resulting in imprisonment</div>
                </div>
                
                <div class="card info">
                    <h3>Total Costs</h3>
                    <div class="value">${stats.total_costs/1000000:.1f}M</div>
                    <div class="subtext">${stats.avg_cost_per_case:,.0f} per case</div>
                </div>
                
                <div class="card warning">
                    <h3>Drug Cases</h3>
                    <div class="value">{stats.drug_possession_cases}</div>
                    <div class="subtext">{(stats.drug_possession_cases/total*100):.1f}% of cases</div>
                </div>
            </div>
            
            <div class="charts-grid">
                <div class="chart-container">
                    <h3>📋 Attorney Representation</h3>
                    <div class="chart-inner">
                        <canvas id="representationChart"></canvas>
                    </div>
                </div>
                
                <div class="chart-container">
                    <h3>⚖️ Case Outcomes</h3>
                    <div class="chart-inner">
                        <canvas id="outcomesChart"></canvas>
                    </div>
                </div>
                
                <div class="chart-container">
                    <h3>⚗️ Drug Possession Cases</h3>
                    <div class="chart-inner">
                        <canvas id="drugChart"></canvas>
                    </div>
                </div>
                
                <div class="chart-container">
                    <h3>🏛️ Attorney Types</h3>
                    <div class="chart-inner">
                        <canvas id="attorneyTypeChart"></canvas>
                    </div>
                </div>
            </div>
            
            <div class="tables-section">
                <h3>👨‍⚖️ Top Attorneys by Case Volume</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Attorney Name</th>
                            <th>Type</th>
                            <th>Total Cases</th>
                            <th>Convicted</th>
                            <th>Dismissed</th>
                            <th>Success Rate</th>
                        </tr>
                    </thead>
                    <tbody>
"""
    
    # Add top attorneys
    sorted_attorneys = sorted(stats.attorneys.items(), key=lambda x: x[1]["total"], reverse=True)[:15]
    for attorney, stat in sorted_attorneys:
        total_att = stat["total"]
        convicted = stat["convicted"]
        dismissed = stat["dismissed"]
        success = (dismissed / total_att * 100) if total_att > 0 else 0
        att_type = stat.get("type", "Unknown") or "Unknown"
        
        html += f"""                        <tr>
                            <td>{attorney}</td>
                            <td>{att_type}</td>
                            <td>{total_att}</td>
                            <td class="{'positive' if convicted == 0 else 'negative'}">{convicted}</td>
                            <td class="positive">{dismissed}</td>
                            <td><strong>{success:.1f}%</strong></td>
                        </tr>
"""
    
    html += """                    </tbody>
                </table>
                
                <h3>⚖️ Judge Statistics (Top 12)</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Judge Name</th>
                            <th>Total Cases</th>
                            <th>Convicted</th>
                            <th>Dismissed</th>
                            <th>Conviction Rate</th>
                            <th>Avg Cost</th>
                        </tr>
                    </thead>
                    <tbody>
"""
    
    # Add judge stats
    sorted_judges = sorted(stats.judge_stats.items(), key=lambda x: x[1]["total_cases"], reverse=True)[:12]
    for judge, stat in sorted_judges:
        total_judge = stat["total_cases"]
        convicted = stat["convicted"]
        dismissed = stat["dismissed"]
        conv_rate = (convicted / total_judge * 100) if total_judge > 0 else 0
        avg_cost = stat["avg_cost"]
        
        html += f"""                        <tr>
                            <td>{judge or 'Unknown'}</td>
                            <td>{total_judge}</td>
                            <td class="negative">{convicted}</td>
                            <td class="positive">{dismissed}</td>
                            <td><strong>{conv_rate:.1f}%</strong></td>
                            <td>${avg_cost:,.0f}</td>
                        </tr>
"""
    
    html += """                    </tbody>
                </table>
                
                <h3>📋 Top Charges</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Charge</th>
                            <th>Count</th>
                            <th>Percentage</th>
                        </tr>
                    </thead>
                    <tbody>
"""
    
    # Add charges
    sorted_charges = sorted(stats.cases_by_charge.items(), key=lambda x: x[1], reverse=True)[:15]
    for charge, count in sorted_charges:
        pct = (count / total * 100) if total > 0 else 0
        html += f"""                        <tr>
                            <td>{charge[:70]}</td>
                            <td>{count}</td>
                            <td>{pct:.2f}%</td>
                        </tr>
"""
    
    html += """                    </tbody>
                </table>
                
                <h3>🚔 Arresting Agencies</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Agency</th>
                            <th>Cases</th>
                            <th>Percentage</th>
                        </tr>
                    </thead>
                    <tbody>
"""
    
    # Add agencies
    sorted_agencies = sorted(stats.cases_by_agency.items(), key=lambda x: x[1], reverse=True)
    for agency, count in sorted_agencies[:15]:
        pct = (count / total * 100) if total > 0 else 0
        html += f"""                        <tr>
                            <td>{agency[:60]}</td>
                            <td>{count}</td>
                            <td>{pct:.2f}%</td>
                        </tr>
"""
    
    html += f"""                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="footer">
            <p>Cuyahoga County Court Statistics Dashboard | Year {stats.year}</p>
            <p>Data Source: Cuyahoga County Court Docket System</p>
            <p>Generated: {Path.cwd()} | Analysis for forensic investigation and public transparency</p>
        </div>
    </div>
    
    <script>
        // Representation Chart
        const ctx1 = document.getElementById('representationChart').getContext('2d');
        new Chart(ctx1, {{
            type: 'doughnut',
            data: {{
                labels: ['With Attorney', 'Without Attorney'],
                datasets: [{{
                    data: [{stats.with_attorney}, {stats.without_attorney}],
                    backgroundColor: ['#66b3ff', '#ff6b6b'],
                    borderColor: '#fff',
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom'
                    }}
                }}
            }}
        }});
        
        // Outcomes Chart
        const ctx2 = document.getElementById('outcomesChart').getContext('2d');
        new Chart(ctx2, {{
            type: 'doughnut',
            data: {{
                labels: ['Dismissed', 'Convicted', 'Imprisoned', 'Pending'],
                datasets: [{{
                    data: [{stats.dismissed_cases}, {stats.convicted_cases}, {stats.imprisoned_cases}, {stats.pending_cases}],
                    backgroundColor: ['#51cf66', '#ff6b6b', '#ffa94d', '#74c0fc'],
                    borderColor: '#fff',
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom'
                    }}
                }}
            }}
        }});
        
        // Drug Cases Chart
        const ctx3 = document.getElementById('drugChart').getContext('2d');
        new Chart(ctx3, {{
            type: 'doughnut',
            data: {{
                labels: ['Drug Cases', 'Other Cases'],
                datasets: [{{
                    data: [{stats.drug_possession_cases}, {total - stats.drug_possession_cases}],
                    backgroundColor: ['#ff6b6b', '#99ff99'],
                    borderColor: '#fff',
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom'
                    }}
                }}
            }}
        }});
        
        // Attorney Type Chart
        const ctx4 = document.getElementById('attorneyTypeChart').getContext('2d');
        new Chart(ctx4, {{
            type: 'doughnut',
            data: {{
                labels: ['Public Defender', 'Private', 'Appointed'],
                datasets: [{{
                    data: [{stats.public_defender}, {stats.private_attorney}, {stats.appointed_attorney}],
                    backgroundColor: ['#99ff99', '#ffcc99', '#ff99cc'],
                    borderColor: '#fff',
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom'
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
    
    output_file.write_text(html)
    print(f"✅ HTML dashboard generated: {output_file}")


if __name__ == "__main__":
    from statistics import generate_yearly_report
    
    # This will be called by the main statistics module
    pass
