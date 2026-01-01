#!/usr/bin/env python3
"""
COMPREHENSIVE CASE ANALYSIS TOOL
=================================
Analyzes court case data to reveal patterns in judge-prosecutor-attorney relationships,
success rates, costs, and strategic insights for legal defense.

Usage:
    python3 analyze_cases.py <year>
    python3 analyze_cases.py 2023
    python3 analyze_cases.py all

Features:
- Statistical breakdown by status, demographics, geography
- Judge performance metrics and case volumes
- Prosecutor workload and patterns
- Defense attorney success rates
- Judge-Prosecutor-Attorney relationship matrices
- Cost analysis and financial patterns
- Strategic insights: "Vegas slot machine" recommendations
- Reusable for any year's data
"""

import json
import csv
import sys
from pathlib import Path
from collections import defaultdict, Counter
import pandas as pd
import numpy as np


class CaseAnalyzer:
    def __init__(self, year):
        self.year = year
        self.df = None
        self.config = self.load_config()
        
    def load_config(self):
        """Load analysis configuration"""
        config_file = Path('analysis_config.json')
        if config_file.exists():
            with open(config_file) as f:
                return json.load(f)
        return {
            "success_keywords": ["DISMISS", "NOT GUILTY", "ACQUIT"],
            "guilty_keywords": ["GUILTY", "PLEA"],
            "negative_keywords": ["CAPIAS", "WARRANT", "JAIL", "INCARCERATED"]
        }
    
    def extract_cases(self):
        """Extract all cases from JSON files"""
        print(f"\n{'='*80}")
        print(f"EXTRACTING {self.year} CASE DATA")
        print(f"{'='*80}\n")
        
        year_dir = Path(f"out/{self.year}")
        if not year_dir.exists():
            print(f"❌ Directory not found: {year_dir}")
            return False
        
        json_files = list(year_dir.glob("*.json"))
        print(f"📁 Found {len(json_files):,} JSON files")
        
        # Group by case ID to get latest version
        case_versions = defaultdict(list)
        for json_file in json_files:
            try:
                with open(json_file) as f:
                    data = json.load(f)
                case_id = data.get('metadata', {}).get('case_id')
                if case_id:
                    case_versions[case_id].append((json_file, json_file.stat().st_mtime))
            except:
                continue
        
        print(f"🔍 Found {len(case_versions):,} unique cases")
        print("📊 Extracting comprehensive data...\n")
        
        cases = []
        for case_id, versions in sorted(case_versions.items()):
            latest_file = max(versions, key=lambda x: x[1])[0]
            case_data = self.extract_case_data(latest_file)
            if case_data:
                cases.append(case_data)
        
        self.df = pd.DataFrame(cases)
        print(f"✅ Extracted {len(self.df):,} cases successfully")
        
        # Save to CSV
        output_file = f"{self.year}_cases_comprehensive.csv"
        self.df.to_csv(output_file, index=False, encoding='utf-8')
        print(f"💾 Saved to {output_file}\n")
        
        return True
    
    def extract_case_data(self, json_file):
        """Extract all relevant data from a single case JSON file"""
        try:
            with open(json_file) as f:
                data = json.load(f)
            
            metadata = data.get('metadata', {})
            summary = data.get('summary', {}).get('fields', {})
            defendant = data.get('defendant', {})
            attorneys = data.get('attorneys', [])
            docket = data.get('docket', [])
            costs = data.get('costs', [])
            
            # Parse charges
            charges_data = summary.get('embedded_table_0', {}).get('data', '')
            charges_list = []
            if charges_data:
                lines = charges_data.split('\r\n')[1:]
                for line in lines:
                    if line.strip():
                        charges_list.append(line)
            charges_str = ' | '.join(charges_list) if charges_list else 'N/A'
            
            # Parse events
            events_data = summary.get('embedded_table_1', {}).get('data', '')
            events_list = []
            if events_data:
                lines = events_data.split('\r\n')[1:]
                for line in lines:
                    if line.strip():
                        events_list.append(line)
            events_str = ' | '.join(events_list) if events_list else 'N/A'
            
            # Bond info
            bond_info = summary.get('No bonds currently exist for this case', 'N/A')
            if bond_info == 'No bonds currently exist for this case':
                bond_info = 'NO BOND'
            
            # Docket analysis
            docket_count = len(docket)
            first_docket = last_docket = 'N/A'
            if docket:
                dated_entries = [e for e in docket if e.get('filing_date') or e.get('proceeding_date')]
                if dated_entries:
                    first_docket = dated_entries[0].get('filing_date') or dated_entries[0].get('proceeding_date', 'N/A')
                    last_docket = dated_entries[-1].get('filing_date') or dated_entries[-1].get('proceeding_date', 'N/A')
            
            # Verdict/disposition
            verdict = 'N/A'
            for entry in docket:
                desc = entry.get('docket_description', '').upper()
                dtype = entry.get('docket_type', '').upper()
                if any(word in desc for word in ['GUILTY', 'NOT GUILTY', 'PLEA', 'SENTENCED', 'DISMISSED']):
                    verdict = entry.get('docket_description', 'N/A')[:200]
                    break
                if dtype in ['JE', 'SENTENCING', 'JUDGMENT ENTRY']:
                    verdict = f"{dtype}: {desc[:150]}"
                    break
            
            # Attorneys
            prosecutor = defense_attorney = 'N/A'
            for atty in attorneys:
                if atty.get('party') == 'Prosecution':
                    prosecutor = atty.get('name', 'N/A')
                elif atty.get('party') == 'Defense':
                    defense_attorney = atty.get('name', 'N/A')
            
            # Costs
            total_costs = sum(float(c.get('amount', 0)) for c in costs if c.get('amount'))
            
            # Defendant info
            defendant_name = defendant.get('Name:', summary.get('Name:', 'N/A'))
            dob = defendant.get('DOB:', summary.get('Date of Birth:', 'N/A'))
            sex = defendant.get('Sex:', summary.get('Sex:', 'N/A'))
            race = defendant.get('Race:', summary.get('Race:', 'N/A'))
            
            # Co-defendants
            codef_str = summary.get('Co-Defendants:', 'N/A')
            codef_count = 0 if codef_str == 'N/A' else len(codef_str.split(','))
            
            # Status
            case_status = summary.get('Status:', 'N/A')
            def_status = defendant.get('Def Status:', 'N/A')
            def_id = defendant.get('Defendant ID:', 'N/A')
            marital = defendant.get('Marital Status:', 'N/A')
            citizenship = defendant.get('Citizenship:', 'N/A')
            
            # Address
            address = defendant.get('Address:', 'N/A')
            address_line2 = defendant.get('Line 2:', '')
            city_state_zip = defendant.get('City, State, Zip:', 'N/A')
            
            # Extract city, state, zip
            city = state = zip_code = 'N/A'
            if city_state_zip and city_state_zip != 'N/A':
                parts = city_state_zip.split(',')
                if len(parts) >= 2:
                    city = parts[0].strip()
                    state_zip = parts[1].strip().split()
                    if len(state_zip) >= 2:
                        state = state_zip[0]
                        zip_code = state_zip[1]
            
            full_address = ', '.join([p for p in [address, address_line2, city_state_zip] if p and p != 'N/A'])
            judge = summary.get('Judge Name:', 'N/A')
            
            return {
                'case_number': metadata.get('case_id'),
                'case_status': case_status,
                'def_status': def_status,
                'def_id': def_id,
                'judge': judge,
                'prosecutor': prosecutor,
                'defense_attorney': defense_attorney,
                'defendant_name': defendant_name,
                'dob': dob,
                'sex': sex,
                'race': race,
                'marital': marital,
                'citizenship': citizenship,
                'codefendants_count': codef_count,
                'address': address,
                'city': city,
                'state': state,
                'zip': zip_code,
                'full_address': full_address,
                'charges': charges_str,
                'events': events_str,
                'bond': bond_info,
                'verdict': verdict,
                'first_docket_date': first_docket,
                'last_docket_date': last_docket,
                'total_docket_entries': docket_count,
                'total_costs': total_costs
            }
            
        except Exception as e:
            return None
    
    def overall_statistics(self):
        """Print overall statistics"""
        print(f"\n{'='*80}")
        print(f"OVERALL STATISTICS")
        print(f"{'='*80}\n")
        
        print(f"📊 SUMMARY")
        print(f"{'─'*80}")
        print(f"Total Cases: {len(self.df):,}")
        print(f"Unique Defendants: {self.df['defendant_name'].nunique():,}")
        print(f"Unique Judges: {self.df['judge'].nunique():,}")
        print(f"Unique Prosecutors: {self.df['prosecutor'].nunique():,}")
        print(f"Unique Defense Attorneys: {self.df['defense_attorney'].nunique():,}")
        
        # Status breakdown
        print(f"\n🏛️  CASE STATUS BREAKDOWN")
        print(f"{'─'*80}")
        status_counts = self.df['case_status'].value_counts()
        for status, count in status_counts.head(15).items():
            pct = (count / len(self.df)) * 100
            print(f"{status[:40]:40s}: {count:6,} ({pct:5.1f}%)")
        
        # Defendant status
        print(f"\n👤 DEFENDANT STATUS BREAKDOWN")
        print(f"{'─'*80}")
        def_status_counts = self.df['def_status'].value_counts()
        for status, count in def_status_counts.head(15).items():
            pct = (count / len(self.df)) * 100
            print(f"{status[:40]:40s}: {count:6,} ({pct:5.1f}%)")
        
        # Key categories
        capias = self.df[self.df['def_status'].str.contains('CAPIAS', na=False, case=False)].shape[0]
        terminated = self.df[self.df['case_status'].str.contains('TERMINATED|CLOSED', na=False, case=False)].shape[0]
        in_jail = self.df[self.df['def_status'].str.contains('JAIL|INCARCERATED|CUSTODY', na=False, case=False)].shape[0]
        
        print(f"\n🔍 KEY CATEGORIES")
        print(f"{'─'*80}")
        print(f"CAPIAS (Warrant):     {capias:6,} ({(capias/len(self.df))*100:5.1f}%)")
        print(f"Terminated/Closed:    {terminated:6,} ({(terminated/len(self.df))*100:5.1f}%)")
        print(f"In Jail/Custody:      {in_jail:6,} ({(in_jail/len(self.df))*100:5.1f}%)")
        
        # Demographics
        print(f"\n👥 DEMOGRAPHICS")
        print(f"{'─'*80}")
        print("Race Distribution:")
        race_counts = self.df['race'].value_counts()
        for race, count in race_counts.items():
            pct = (count / len(self.df)) * 100
            print(f"  {race:20s}: {count:6,} ({pct:5.1f}%)")
        
        print("\nSex Distribution:")
        sex_counts = self.df['sex'].value_counts()
        for sex, count in sex_counts.items():
            pct = (count / len(self.df)) * 100
            print(f"  {sex:20s}: {count:6,} ({pct:5.1f}%)")
    
    def judge_analysis(self):
        """Analyze judge performance and patterns"""
        print(f"\n{'='*80}")
        print(f"JUDGE ANALYSIS")
        print(f"{'='*80}\n")
        
        # Top judges by volume
        print(f"⚖️  TOP 20 JUDGES BY CASE VOLUME")
        print(f"{'─'*80}")
        judge_cases = self.df['judge'].value_counts().head(20)
        for judge, count in judge_cases.items():
            pct = (count / len(self.df)) * 100
            print(f"{judge[:40]:40s}: {count:6,} ({pct:5.1f}%)")
        
        # Judge "harshness" metrics
        print(f"\n🎯 JUDGE OUTCOME ANALYSIS (Top 10)")
        print(f"{'─'*80}")
        print(f"(Based on verdict keywords in docket)")
        
        top_judges = self.df['judge'].value_counts().head(10).index
        judge_stats = []
        
        for judge in top_judges:
            judge_df = self.df[self.df['judge'] == judge]
            total = len(judge_df)
            
            # Outcomes
            has_verdict = judge_df[judge_df['verdict'] != 'N/A']
            guilty = has_verdict[has_verdict['verdict'].str.contains('GUILTY', na=False, case=False) & 
                                 ~has_verdict['verdict'].str.contains('NOT GUILTY', na=False, case=False)].shape[0]
            dismissed = has_verdict[has_verdict['verdict'].str.contains('DISMISS', na=False, case=False)].shape[0]
            plea = has_verdict[has_verdict['verdict'].str.contains('PLEA', na=False, case=False)].shape[0]
            
            # Negative outcomes
            capias = judge_df[judge_df['def_status'].str.contains('CAPIAS', na=False, case=False)].shape[0]
            in_jail = judge_df[judge_df['def_status'].str.contains('JAIL', na=False, case=False)].shape[0]
            
            judge_stats.append({
                'judge': judge,
                'total': total,
                'guilty': guilty,
                'dismissed': dismissed,
                'plea': plea,
                'capias': capias,
                'in_jail': in_jail,
                'guilty_rate': (guilty / len(has_verdict) * 100) if len(has_verdict) > 0 else 0,
                'dismiss_rate': (dismissed / len(has_verdict) * 100) if len(has_verdict) > 0 else 0,
                'capias_rate': (capias / total * 100)
            })
        
        for stats in judge_stats:
            print(f"\n{stats['judge'][:60]}")
            print(f"  Total Cases:     {stats['total']:4,}")
            print(f"  Guilty:          {stats['guilty']:4} ({stats['guilty_rate']:5.1f}%)")
            print(f"  Dismissed:       {stats['dismissed']:4} ({stats['dismiss_rate']:5.1f}%)")
            print(f"  Plea:            {stats['plea']:4}")
            print(f"  CAPIAS:          {stats['capias']:4} ({stats['capias_rate']:5.1f}%)")
            print(f"  In Jail:         {stats['in_jail']:4}")
        
        return judge_stats
    
    def attorney_analysis(self):
        """Analyze defense attorney performance"""
        print(f"\n{'='*80}")
        print(f"DEFENSE ATTORNEY ANALYSIS")
        print(f"{'='*80}\n")
        
        # Filter out N/A
        attorneys_df = self.df[self.df['defense_attorney'] != 'N/A']
        
        # Top attorneys by volume
        print(f"🎓 TOP 20 DEFENSE ATTORNEYS BY CASE VOLUME")
        print(f"{'─'*80}")
        attorney_cases = attorneys_df['defense_attorney'].value_counts().head(20)
        for attorney, count in attorney_cases.items():
            pct = (count / len(self.df)) * 100
            print(f"{attorney[:40]:40s}: {count:6,} ({pct:5.1f}%)")
        
        # Success rates
        print(f"\n🏆 DEFENSE ATTORNEY SUCCESS RATES (Top 20)")
        print(f"{'─'*80}")
        print(f"Success = Dismissed or Not Guilty | Failure = Guilty/Plea")
        print()
        
        top_attorneys = attorneys_df['defense_attorney'].value_counts().head(20).index
        attorney_stats = []
        
        for attorney in top_attorneys:
            atty_df = self.df[self.df['defense_attorney'] == attorney]
            total = len(atty_df)
            
            has_verdict = atty_df[atty_df['verdict'] != 'N/A']
            success = has_verdict[has_verdict['verdict'].str.contains('DISMISS|NOT GUILTY', na=False, case=False)].shape[0]
            guilty = has_verdict[has_verdict['verdict'].str.contains('GUILTY', na=False, case=False) & 
                                ~has_verdict['verdict'].str.contains('NOT GUILTY', na=False, case=False)].shape[0]
            plea = has_verdict[has_verdict['verdict'].str.contains('PLEA', na=False, case=False)].shape[0]
            
            capias = atty_df[atty_df['def_status'].str.contains('CAPIAS', na=False, case=False)].shape[0]
            
            success_rate = (success / len(has_verdict) * 100) if len(has_verdict) > 0 else 0
            
            attorney_stats.append({
                'attorney': attorney,
                'total': total,
                'success': success,
                'guilty': guilty,
                'plea': plea,
                'capias': capias,
                'success_rate': success_rate
            })
        
        # Sort by success rate
        attorney_stats.sort(key=lambda x: x['success_rate'], reverse=True)
        
        for stats in attorney_stats:
            print(f"{stats['attorney'][:35]:35s}: {stats['total']:4} cases | "
                  f"Win: {stats['success']:3} ({stats['success_rate']:5.1f}%) | "
                  f"Guilty: {stats['guilty']:3} | Plea: {stats['plea']:3} | "
                  f"CAPIAS: {stats['capias']:3}")
        
        return attorney_stats
    
    def relationship_matrix(self):
        """Analyze judge-prosecutor-attorney relationships"""
        print(f"\n{'='*80}")
        print(f"RELATIONSHIP MATRIX ANALYSIS")
        print(f"{'='*80}\n")
        
        # Judge-Prosecutor matrix
        print(f"🔗 JUDGE × PROSECUTOR (Top 10×10)")
        print(f"{'─'*80}")
        
        top_judges = self.df['judge'].value_counts().head(10).index
        top_prosecutors = self.df[self.df['prosecutor'] != 'N/A']['prosecutor'].value_counts().head(10).index
        
        jp_matrix = pd.crosstab(self.df['judge'], self.df['prosecutor'])
        top_jp = jp_matrix.loc[top_judges, top_prosecutors]
        print(top_jp.to_string())
        
        # Judge-Defense Attorney matrix
        print(f"\n🔗 JUDGE × DEFENSE ATTORNEY (Top 10×10)")
        print(f"{'─'*80}")
        
        top_defense = self.df[self.df['defense_attorney'] != 'N/A']['defense_attorney'].value_counts().head(10).index
        jd_matrix = pd.crosstab(self.df['judge'], self.df['defense_attorney'])
        top_jd = jd_matrix.loc[top_judges, top_defense]
        print(top_jd.to_string())
    
    def strategic_insights(self, judge_stats, attorney_stats):
        """Generate strategic insights - "Vegas Slot Machine" style"""
        print(f"\n{'='*80}")
        print(f"🎰 STRATEGIC INSIGHTS: THE INSIDER'S GUIDE")
        print(f"{'='*80}\n")
        
        print(f"💡 STRATEGY RECOMMENDATIONS")
        print(f"{'─'*80}\n")
        
        # Best judges (lowest capias/jail rates)
        judge_df = pd.DataFrame(judge_stats).sort_values('capias_rate')
        print("✅ BEST JUDGES (Lowest CAPIAS/Warrant Rate):")
        for i, row in judge_df.head(5).iterrows():
            print(f"  {i+1}. {row['judge'][:50]:50s} - CAPIAS Rate: {row['capias_rate']:4.1f}%")
        
        print()
        
        # Toughest judges
        print("⚠️  TOUGHEST JUDGES (Highest CAPIAS/Warrant Rate):")
        for i, row in judge_df.tail(5).iloc[::-1].iterrows():
            print(f"  {i+1}. {row['judge'][:50]:50s} - CAPIAS Rate: {row['capias_rate']:4.1f}%")
        
        print()
        
        # Best attorneys
        atty_df = pd.DataFrame(attorney_stats).sort_values('success_rate', ascending=False)
        print("🏆 TOP PERFORMING ATTORNEYS (Highest Success Rate, min 10 cases):")
        top_atty = atty_df[atty_df['total'] >= 10].head(10)
        for i, row in top_atty.iterrows():
            print(f"  {i+1}. {row['attorney'][:45]:45s} - Success: {row['success_rate']:5.1f}% "
                  f"({row['success']}/{row['total']} cases)")
        
        print()
        
        # Cost analysis
        if self.df['total_costs'].sum() > 0:
            print("💰 COST INSIGHTS:")
            costs_df = self.df[self.df['total_costs'] > 0]
            print(f"  Average Cost: ${costs_df['total_costs'].mean():,.2f}")
            print(f"  Median Cost:  ${costs_df['total_costs'].median():,.2f}")
            print(f"  Max Cost:     ${costs_df['total_costs'].max():,.2f}")
        
        print()
        
        # Geographic patterns
        print("🌆 GEOGRAPHIC PATTERNS (Top 5 Cities):")
        city_counts = self.df[self.df['city'] != 'N/A']['city'].value_counts().head(5)
        for city, count in city_counts.items():
            pct = (count / len(self.df)) * 100
            city_df = self.df[self.df['city'] == city]
            capias = city_df[city_df['def_status'].str.contains('CAPIAS', na=False, case=False)].shape[0]
            capias_rate = (capias / count * 100) if count > 0 else 0
            print(f"  {city:20s}: {count:5,} cases ({pct:4.1f}%) - CAPIAS Rate: {capias_rate:4.1f}%")
        
        print(f"\n{'='*80}")
        print(f"🎯 THE VEGAS SLOT MACHINE: OPTIMAL COMBINATIONS")
        print(f"{'='*80}\n")
        
        print("For each tough judge, here are the best attorneys to represent you:\n")
        
        # For each tough judge, find attorneys with best success rates
        tough_judges = judge_df.tail(5)['judge'].values
        
        for judge in tough_judges:
            judge_cases = self.df[self.df['judge'] == judge]
            judge_attorneys = judge_cases[judge_cases['defense_attorney'] != 'N/A'].groupby('defense_attorney').size()
            
            # Only consider attorneys with 3+ cases with this judge
            experienced_attorneys = judge_attorneys[judge_attorneys >= 3].index
            
            if len(experienced_attorneys) > 0:
                print(f"⚖️  {judge[:50]}")
                
                attorney_performance = []
                for attorney in experienced_attorneys:
                    atty_judge_cases = judge_cases[judge_cases['defense_attorney'] == attorney]
                    total = len(atty_judge_cases)
                    has_verdict = atty_judge_cases[atty_judge_cases['verdict'] != 'N/A']
                    success = has_verdict[has_verdict['verdict'].str.contains('DISMISS|NOT GUILTY', na=False, case=False)].shape[0]
                    success_rate = (success / len(has_verdict) * 100) if len(has_verdict) > 0 else 0
                    
                    attorney_performance.append({
                        'attorney': attorney,
                        'total': total,
                        'success': success,
                        'success_rate': success_rate
                    })
                
                # Sort by success rate
                attorney_performance.sort(key=lambda x: x['success_rate'], reverse=True)
                
                for i, perf in enumerate(attorney_performance[:3], 1):
                    print(f"  {i}. {perf['attorney'][:45]:45s} - {perf['success_rate']:5.1f}% success ({perf['success']}/{perf['total']})")
                print()
    
    def run_full_analysis(self):
        """Run complete analysis pipeline"""
        # Extract data
        if not self.extract_cases():
            return
        
        # Run all analyses
        self.overall_statistics()
        judge_stats = self.judge_analysis()
        attorney_stats = self.attorney_analysis()
        self.relationship_matrix()
        self.strategic_insights(judge_stats, attorney_stats)
        
        print(f"\n{'='*80}")
        print(f"✅ ANALYSIS COMPLETE")
        print(f"{'='*80}\n")
        print(f"📊 Data saved to: {self.year}_cases_comprehensive.csv")
        print(f"📋 Configuration: analysis_config.json")
        print(f"\nTo analyze another year: python3 analyze_cases.py <year>")
        print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_cases.py <year>")
        print("Example: python3 analyze_cases.py 2023")
        sys.exit(1)
    
    year = sys.argv[1]
    analyzer = CaseAnalyzer(year)
    analyzer.run_full_analysis()


if __name__ == "__main__":
    main()
