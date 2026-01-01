"""
Analytics Calculator Service
Calculates and updates performance metrics for judges, prosecutors, and attorneys
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case as sql_case
from collections import defaultdict
import statistics


class AnalyticsCalculator:
    """
    Calculates comprehensive analytics for legal professionals
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def calculate_judge_performance(self, judge_id: int) -> Dict[str, Any]:
        """
        Calculate all performance metrics for a judge
        """
        from database.models_postgres import Case, CaseOutcome, Charge
        from database.analytics_models import JudgePerformance
        
        # Get all cases for this judge
        cases = self.db.query(Case).filter(Case.judge_id == judge_id).all()
        
        if not cases:
            return {"error": "No cases found for judge"}
        
        # Calculate metrics
        total_cases = len(cases)
        
        # Get cases with outcomes
        cases_with_outcomes = [c for c in cases if c.outcome]
        
        # Count outcomes
        convictions = sum(1 for c in cases_with_outcomes 
                         if c.outcome.final_status == "CONVICTED")
        dismissals = sum(1 for c in cases_with_outcomes 
                        if c.outcome.final_status == "DISMISSED")
        acquittals = sum(1 for c in cases_with_outcomes 
                        if c.outcome.final_status == "ACQUITTED")
        plea_bargains = sum(1 for c in cases_with_outcomes 
                           if c.outcome.final_status == "PLEA_BARGAIN")
        
        # Calculate rates
        total_disposed = len(cases_with_outcomes)
        conviction_rate = (convictions / total_disposed * 100) if total_disposed > 0 else 0
        dismissal_rate = (dismissals / total_disposed * 100) if total_disposed > 0 else 0
        acquittal_rate = (acquittals / total_disposed * 100) if total_disposed > 0 else 0
        plea_bargain_rate = (plea_bargains / total_disposed * 100) if total_disposed > 0 else 0
        
        # Calculate timing metrics
        days_to_disposition = []
        for case in cases_with_outcomes:
            if case.arrest_date and case.disposition_date:
                delta = (case.disposition_date - case.arrest_date).days
                if delta > 0:
                    days_to_disposition.append(delta)
        
        avg_days = statistics.mean(days_to_disposition) if days_to_disposition else 0
        median_days = statistics.median(days_to_disposition) if days_to_disposition else 0
        fastest = min(days_to_disposition) if days_to_disposition else 0
        slowest = max(days_to_disposition) if days_to_disposition else 0
        
        # Calculate sentencing metrics
        sentences = [c.outcome.sentence_duration_days for c in cases_with_outcomes 
                    if c.outcome and c.outcome.sentence_duration_days]
        fines = [c.outcome.fine_amount for c in cases_with_outcomes 
                if c.outcome and c.outcome.fine_amount]
        restitutions = [c.outcome.restitution_amount for c in cases_with_outcomes 
                       if c.outcome and c.outcome.restitution_amount]
        
        avg_sentence = statistics.mean(sentences) if sentences else 0
        avg_fine = statistics.mean(fines) if fines else 0
        avg_restitution = statistics.mean(restitutions) if restitutions else 0
        
        # Calculate charge-type specific rates
        violent_cases = self._get_cases_by_charge_type(cases_with_outcomes, "VIOLENT")
        drug_cases = self._get_cases_by_charge_type(cases_with_outcomes, "DRUG")
        property_cases = self._get_cases_by_charge_type(cases_with_outcomes, "PROPERTY")
        
        violent_conviction_rate = self._calculate_conviction_rate(violent_cases)
        drug_conviction_rate = self._calculate_conviction_rate(drug_cases)
        property_conviction_rate = self._calculate_conviction_rate(property_cases)
        
        # Calculate defendant favorability score (0-10)
        # Lower conviction rate = higher favorability
        # Higher dismissal/acquittal rate = higher favorability
        # Lower sentences = higher favorability
        favorability = self._calculate_defendant_favorability(
            conviction_rate, dismissal_rate, acquittal_rate, avg_sentence
        )
        
        # Calculate cases per year
        years_active = self._calculate_years_active(cases)
        avg_cases_per_year = total_cases / years_active if years_active > 0 else total_cases
        
        # Get current year cases
        current_year = datetime.now().year
        cases_this_year = sum(1 for c in cases if c.year == current_year)
        
        return {
            "judge_id": judge_id,
            "total_cases": total_cases,
            "cases_this_year": cases_this_year,
            "avg_cases_per_year": round(avg_cases_per_year, 2),
            "total_convictions": convictions,
            "total_dismissals": dismissals,
            "total_acquittals": acquittals,
            "total_plea_bargains": plea_bargains,
            "conviction_rate": round(conviction_rate, 2),
            "dismissal_rate": round(dismissal_rate, 2),
            "acquittal_rate": round(acquittal_rate, 2),
            "plea_bargain_rate": round(plea_bargain_rate, 2),
            "avg_days_to_disposition": round(avg_days, 2),
            "median_days_to_disposition": round(median_days, 2),
            "fastest_case_days": fastest,
            "slowest_case_days": slowest,
            "avg_sentence_duration_days": round(avg_sentence, 2),
            "avg_fine_amount": round(avg_fine, 2),
            "avg_restitution_amount": round(avg_restitution, 2),
            "violent_crime_conviction_rate": round(violent_conviction_rate, 2),
            "drug_crime_conviction_rate": round(drug_conviction_rate, 2),
            "property_crime_conviction_rate": round(property_conviction_rate, 2),
            "defendant_favorability_score": round(favorability, 2),
            "calculated_at": datetime.utcnow().isoformat()
        }
    
    def _get_cases_by_charge_type(self, cases: List[Any], charge_type: str) -> List[Any]:
        """Filter cases by charge type"""
        filtered = []
        for case in cases:
            if case.charges:
                for charge in case.charges:
                    if charge_type.upper() in charge.description.upper():
                        filtered.append(case)
                        break
        return filtered
    
    def _calculate_conviction_rate(self, cases: List[Any]) -> float:
        """Calculate conviction rate for a list of cases"""
        if not cases:
            return 0.0
        convictions = sum(1 for c in cases if c.outcome and c.outcome.final_status == "CONVICTED")
        return (convictions / len(cases)) * 100
    
    def _calculate_defendant_favorability(
        self,
        conviction_rate: float,
        dismissal_rate: float,
        acquittal_rate: float,
        avg_sentence: float
    ) -> float:
        """Calculate defendant favorability score (0-10)"""
        # Lower conviction = higher favorability
        conviction_score = (100 - conviction_rate) / 10
        
        # Higher dismissal/acquittal = higher favorability
        favorable_outcome_score = (dismissal_rate + acquittal_rate) / 10
        
        # Lower sentence = higher favorability (assume 365 days = neutral)
        sentence_score = max(0, 10 - (avg_sentence / 365) * 5)
        
        # Weighted average
        favorability = (conviction_score * 0.5 + favorable_outcome_score * 0.3 + sentence_score * 0.2)
        
        return min(max(favorability, 0), 10)  # Clamp to 0-10
    
    def _calculate_years_active(self, cases: List[Any]) -> int:
        """Calculate number of years judge has been active"""
        if not cases:
            return 1
        years = set(c.year for c in cases if c.year)
        return len(years) if years else 1

    def calculate_prosecutor_performance(self, attorney_id: int) -> Dict[str, Any]:
        """Calculate prosecutor performance metrics"""
        from database.models_postgres import Case, CaseAttorney

        # Get all cases where this attorney was prosecutor
        case_attorneys = self.db.query(CaseAttorney).filter(
            and_(
                CaseAttorney.attorney_id == attorney_id,
                CaseAttorney.role == "PROSECUTOR"
            )
        ).all()

        case_ids = [ca.case_id for ca in case_attorneys]
        cases = self.db.query(Case).filter(Case.id.in_(case_ids)).all()

        if not cases:
            return {"error": "No cases found for prosecutor"}

        # Similar calculations as judge, but from prosecutor perspective
        total_cases = len(cases)
        cases_with_outcomes = [c for c in cases if c.outcome]

        convictions = sum(1 for c in cases_with_outcomes
                         if c.outcome.final_status == "CONVICTED")
        dismissals = sum(1 for c in cases_with_outcomes
                        if c.outcome.final_status == "DISMISSED")
        acquittals = sum(1 for c in cases_with_outcomes
                        if c.outcome.final_status == "ACQUITTED")
        plea_bargains = sum(1 for c in cases_with_outcomes
                           if c.outcome.final_status == "PLEA_BARGAIN")

        total_disposed = len(cases_with_outcomes)
        conviction_rate = (convictions / total_disposed * 100) if total_disposed > 0 else 0
        plea_bargain_rate = (plea_bargains / total_disposed * 100) if total_disposed > 0 else 0

        # Trial win rate (convictions from trial, not plea)
        trial_cases = [c for c in cases_with_outcomes
                      if c.outcome.final_status in ["CONVICTED", "ACQUITTED"]]
        trial_convictions = sum(1 for c in trial_cases
                               if c.outcome.final_status == "CONVICTED")
        trial_win_rate = (trial_convictions / len(trial_cases) * 100) if trial_cases else 0

        # Aggressiveness score (high conviction rate + low plea rate = aggressive)
        aggressiveness = (conviction_rate / 10) * 0.6 + ((100 - plea_bargain_rate) / 10) * 0.4

        # Performance by judge
        performance_by_judge = self._calculate_prosecutor_by_judge(cases_with_outcomes)

        current_year = datetime.now().year
        cases_this_year = sum(1 for c in cases if c.year == current_year)
        active_cases = sum(1 for c in cases if c.status == "ACTIVE")

        return {
            "attorney_id": attorney_id,
            "total_cases": total_cases,
            "cases_this_year": cases_this_year,
            "active_cases": active_cases,
            "total_convictions": convictions,
            "total_dismissals": dismissals,
            "total_acquittals": acquittals,
            "total_plea_bargains": plea_bargains,
            "conviction_rate": round(conviction_rate, 2),
            "trial_win_rate": round(trial_win_rate, 2),
            "plea_bargain_rate": round(plea_bargain_rate, 2),
            "aggressiveness_score": round(aggressiveness, 2),
            "performance_by_judge": performance_by_judge,
            "calculated_at": datetime.utcnow().isoformat()
        }

    def calculate_defense_attorney_performance(self, attorney_id: int) -> Dict[str, Any]:
        """Calculate defense attorney performance metrics"""
        from database.models_postgres import Case, CaseAttorney

        # Get all cases where this attorney was defense counsel
        case_attorneys = self.db.query(CaseAttorney).filter(
            and_(
                CaseAttorney.attorney_id == attorney_id,
                CaseAttorney.role == "DEFENSE"
            )
        ).all()

        case_ids = [ca.case_id for ca in case_attorneys]
        cases = self.db.query(Case).filter(Case.id.in_(case_ids)).all()

        if not cases:
            return {"error": "No cases found for defense attorney"}

        total_cases = len(cases)
        cases_with_outcomes = [c for c in cases if c.outcome]

        # From defendant perspective: dismissals and acquittals are wins
        dismissals = sum(1 for c in cases_with_outcomes
                        if c.outcome.final_status == "DISMISSED")
        acquittals = sum(1 for c in cases_with_outcomes
                        if c.outcome.final_status == "ACQUITTED")
        convictions = sum(1 for c in cases_with_outcomes
                         if c.outcome.final_status == "CONVICTED")
        favorable_pleas = sum(1 for c in cases_with_outcomes
                             if c.outcome.final_status == "PLEA_BARGAIN")

        total_disposed = len(cases_with_outcomes)
        dismissal_rate = (dismissals / total_disposed * 100) if total_disposed > 0 else 0
        acquittal_rate = (acquittals / total_disposed * 100) if total_disposed > 0 else 0
        win_rate = ((dismissals + acquittals) / total_disposed * 100) if total_disposed > 0 else 0
        favorable_outcome_rate = ((dismissals + acquittals + favorable_pleas) / total_disposed * 100) if total_disposed > 0 else 0

        # Trial performance
        trial_cases = [c for c in cases_with_outcomes
                      if c.outcome.final_status in ["CONVICTED", "ACQUITTED"]]
        trial_wins = sum(1 for c in trial_cases if c.outcome.final_status == "ACQUITTED")
        trial_win_rate = (trial_wins / len(trial_cases) * 100) if trial_cases else 0

        # Effectiveness score
        effectiveness = (win_rate / 10) * 0.6 + (trial_win_rate / 10) * 0.4

        # Performance by judge and prosecutor
        performance_by_judge = self._calculate_defense_by_judge(cases_with_outcomes)
        performance_by_prosecutor = self._calculate_defense_by_prosecutor(cases_with_outcomes)
        performance_by_matchup = self._calculate_defense_by_matchup(cases_with_outcomes)

        current_year = datetime.now().year
        cases_this_year = sum(1 for c in cases if c.year == current_year)
        active_cases = sum(1 for c in cases if c.status == "ACTIVE")

        return {
            "attorney_id": attorney_id,
            "total_cases": total_cases,
            "cases_this_year": cases_this_year,
            "active_cases": active_cases,
            "total_dismissals": dismissals,
            "total_acquittals": acquittals,
            "total_convictions": convictions,
            "total_favorable_pleas": favorable_pleas,
            "dismissal_rate": round(dismissal_rate, 2),
            "acquittal_rate": round(acquittal_rate, 2),
            "win_rate": round(win_rate, 2),
            "favorable_outcome_rate": round(favorable_outcome_rate, 2),
            "trial_win_rate": round(trial_win_rate, 2),
            "total_trials": len(trial_cases),
            "effectiveness_score": round(effectiveness, 2),
            "performance_by_judge": performance_by_judge,
            "performance_by_prosecutor": performance_by_prosecutor,
            "performance_by_matchup": performance_by_matchup,
            "calculated_at": datetime.utcnow().isoformat()
        }

    def _calculate_prosecutor_by_judge(self, cases: List[Any]) -> Dict[str, Any]:
        """Calculate prosecutor performance broken down by judge"""
        by_judge = defaultdict(lambda: {"cases": 0, "convictions": 0})

        for case in cases:
            if case.judge_id and case.outcome:
                judge_key = str(case.judge_id)
                by_judge[judge_key]["cases"] += 1
                if case.outcome.final_status == "CONVICTED":
                    by_judge[judge_key]["convictions"] += 1

        # Calculate rates
        result = {}
        for judge_id, data in by_judge.items():
            result[judge_id] = {
                "cases": data["cases"],
                "conviction_rate": round((data["convictions"] / data["cases"] * 100), 2) if data["cases"] > 0 else 0
            }

        return result

    def _calculate_defense_by_judge(self, cases: List[Any]) -> Dict[str, Any]:
        """Calculate defense attorney performance by judge"""
        by_judge = defaultdict(lambda: {"cases": 0, "wins": 0})

        for case in cases:
            if case.judge_id and case.outcome:
                judge_key = str(case.judge_id)
                by_judge[judge_key]["cases"] += 1
                if case.outcome.final_status in ["DISMISSED", "ACQUITTED"]:
                    by_judge[judge_key]["wins"] += 1

        result = {}
        for judge_id, data in by_judge.items():
            result[judge_id] = {
                "cases": data["cases"],
                "win_rate": round((data["wins"] / data["cases"] * 100), 2) if data["cases"] > 0 else 0
            }

        return result

    def _calculate_defense_by_prosecutor(self, cases: List[Any]) -> Dict[str, Any]:
        """Calculate defense attorney performance by prosecutor"""
        # This would require joining with CaseAttorney to find prosecutors
        # Simplified version for now
        return {}

    def _calculate_defense_by_matchup(self, cases: List[Any]) -> Dict[str, Any]:
        """Calculate defense attorney performance by judge-prosecutor matchup"""
        # This would require joining with CaseAttorney to find prosecutors
        # Simplified version for now
        return {}
