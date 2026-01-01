"""
Quadrant Analysis Engine
Multi-dimensional case categorization framework
"""

from typing import Dict, Any, List, Tuple
from datetime import datetime, date
from enum import Enum


class Quadrant(str, Enum):
    Q1 = "Q1"  # High X, High Y
    Q2 = "Q2"  # Low X, High Y
    Q3 = "Q3"  # Low X, Low Y
    Q4 = "Q4"  # High X, Low Y


class QuadrantAnalyzer:
    """
    Analyzes cases across multiple dimensions and assigns quadrants
    """
    
    # Severity weights for different charge types
    SEVERITY_WEIGHTS = {
        "MURDER": 10.0,
        "RAPE": 9.5,
        "ROBBERY": 8.0,
        "ASSAULT": 7.0,
        "BURGLARY": 6.0,
        "THEFT": 4.0,
        "DRUG": 5.0,
        "WEAPON": 6.5,
        "DUI": 3.0,
        "TRAFFIC": 1.0,
    }
    
    def __init__(self):
        pass
    
    def calculate_severity_score(self, case_data: Dict[str, Any]) -> float:
        """
        Calculate case severity score (0-10)
        Based on charge types, number of charges, and violence indicators
        """
        charges = case_data.get("summary", {}).get("charges", [])
        if not charges:
            return 0.0
        
        total_severity = 0.0
        charge_count = len(charges)
        
        for charge in charges:
            description = charge.get("description", "").upper()
            
            # Match against severity weights
            severity = 2.0  # Default
            for crime_type, weight in self.SEVERITY_WEIGHTS.items():
                if crime_type in description:
                    severity = max(severity, weight)
            
            # Boost for felonies
            if "FELONY" in description or "FELONIOUS" in description:
                severity *= 1.2
            
            total_severity += severity
        
        # Average severity, capped at 10
        avg_severity = total_severity / charge_count
        
        # Boost for multiple charges
        multiplier = min(1.0 + (charge_count - 1) * 0.1, 1.5)
        
        return min(avg_severity * multiplier, 10.0)
    
    def calculate_complexity_score(self, case_data: Dict[str, Any]) -> float:
        """
        Calculate case complexity score (0-10)
        Based on number of charges, co-defendants, docket entries, attorneys
        """
        charges = len(case_data.get("summary", {}).get("charges", []))
        co_defendants = len(case_data.get("co_defendants", []))
        docket_entries = len(case_data.get("docket", []))
        attorneys = len(case_data.get("attorneys", []))
        
        # Complexity factors
        charge_complexity = min(charges * 1.5, 4.0)
        co_def_complexity = min(co_defendants * 2.0, 3.0)
        docket_complexity = min(docket_entries / 10.0, 2.0)
        attorney_complexity = min(attorneys * 0.5, 1.0)
        
        total = charge_complexity + co_def_complexity + docket_complexity + attorney_complexity
        
        return min(total, 10.0)
    
    def calculate_speed_score(self, case_data: Dict[str, Any]) -> float:
        """
        Calculate case speed score (0-10, where 10 = fastest)
        Based on time from arrest to disposition
        """
        metadata = case_data.get("metadata", {})
        
        # Try to get arrest and disposition dates
        arrest_date_str = case_data.get("summary", {}).get("fields", {}).get("Arrested Date:", "N/A")
        
        # Parse dates from docket
        docket = case_data.get("docket", [])
        if not docket:
            return 5.0  # Neutral if no data
        
        # Count days from first to last docket entry
        try:
            first_entry = docket[-1].get("col1", "")
            last_entry = docket[0].get("col1", "")
            
            first_date = datetime.strptime(first_entry, "%m/%d/%Y")
            last_date = datetime.strptime(last_entry, "%m/%d/%Y")
            
            days_elapsed = (last_date - first_date).days
            
            # Speed scoring (inverse of time)
            # < 30 days = 10, > 365 days = 0
            if days_elapsed < 30:
                return 10.0
            elif days_elapsed > 365:
                return 0.0
            else:
                return 10.0 - (days_elapsed / 365.0) * 10.0
        except:
            return 5.0  # Neutral on error
    
    def calculate_outcome_score(self, case_data: Dict[str, Any]) -> float:
        """
        Calculate outcome favorability score (0-10, where 10 = most favorable for defendant)
        Based on disposition type and sentencing
        """
        outcome = case_data.get("outcome", {})
        final_status = outcome.get("final_status", "PENDING")
        
        # Outcome scoring
        outcome_scores = {
            "DISMISSED": 10.0,
            "ACQUITTED": 10.0,
            "NOLLE_PROSEQUI": 9.0,
            "PLEA_BARGAIN": 6.0,
            "CONVICTED": 2.0,
            "PENDING": 5.0,
        }
        
        base_score = outcome_scores.get(final_status, 5.0)
        
        # Adjust for sentencing severity
        sentence_duration = outcome.get("sentence_duration_days", 0)
        if sentence_duration > 0:
            # Reduce score based on sentence length
            penalty = min(sentence_duration / 365.0, 5.0)  # Max 5 point penalty
            base_score = max(base_score - penalty, 0.0)
        
        return base_score

    def calculate_cost_score(self, case_data: Dict[str, Any]) -> float:
        """
        Calculate cost score (0-10, where 10 = highest cost)
        Based on total costs, fines, restitution
        """
        costs = case_data.get("costs", [])
        outcome = case_data.get("outcome", {})

        # Sum up all costs
        total_costs = 0.0
        for cost in costs:
            try:
                amount_str = cost.get("col2", "0").replace("$", "").replace(",", "")
                if amount_str and amount_str != "":
                    total_costs += float(amount_str)
            except:
                pass

        # Add fines and restitution
        fine_amount = outcome.get("fine_amount", 0) or 0
        restitution = outcome.get("restitution_amount", 0) or 0

        total = total_costs + fine_amount + restitution

        # Score based on total (logarithmic scale)
        if total == 0:
            return 0.0
        elif total < 100:
            return 2.0
        elif total < 500:
            return 4.0
        elif total < 1000:
            return 6.0
        elif total < 5000:
            return 8.0
        else:
            return 10.0

    def calculate_representation_score(self, case_data: Dict[str, Any]) -> float:
        """
        Calculate representation quality score (0-10, where 10 = best representation)
        Based on attorney type, number of attorneys, case outcome
        """
        attorneys = case_data.get("attorneys", [])

        if not attorneys:
            return 2.0  # No attorney = poor representation

        # Check for private vs public defender
        has_private = any("PRIVATE" in str(atty).upper() for atty in attorneys)
        has_public = any("PUBLIC" in str(atty).upper() for atty in attorneys)

        base_score = 7.0 if has_private else 5.0

        # Boost for multiple attorneys
        if len(attorneys) > 1:
            base_score += 1.0

        # Adjust based on outcome
        outcome = case_data.get("outcome", {})
        final_status = outcome.get("final_status", "PENDING")

        if final_status in ["DISMISSED", "ACQUITTED"]:
            base_score += 2.0
        elif final_status == "CONVICTED":
            base_score -= 1.0

        return min(base_score, 10.0)

    def assign_quadrant(self, x_score: float, y_score: float) -> Quadrant:
        """
        Assign quadrant based on X and Y scores
        Threshold is 5.0 (midpoint)
        """
        if x_score >= 5.0 and y_score >= 5.0:
            return Quadrant.Q1
        elif x_score < 5.0 and y_score >= 5.0:
            return Quadrant.Q2
        elif x_score < 5.0 and y_score < 5.0:
            return Quadrant.Q3
        else:  # x_score >= 5.0 and y_score < 5.0
            return Quadrant.Q4

    def analyze_case(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform complete quadrant analysis on a case
        Returns all scores and quadrant assignments
        """
        # Calculate all scores
        severity = self.calculate_severity_score(case_data)
        complexity = self.calculate_complexity_score(case_data)
        speed = self.calculate_speed_score(case_data)
        outcome = self.calculate_outcome_score(case_data)
        cost = self.calculate_cost_score(case_data)
        representation = self.calculate_representation_score(case_data)

        # Assign quadrants
        sev_comp_quad = self.assign_quadrant(severity, complexity)
        speed_outcome_quad = self.assign_quadrant(speed, outcome)
        cost_rep_quad = self.assign_quadrant(cost, representation)

        return {
            "severity_score": round(severity, 2),
            "complexity_score": round(complexity, 2),
            "severity_complexity_quadrant": sev_comp_quad.value,

            "speed_score": round(speed, 2),
            "outcome_score": round(outcome, 2),
            "speed_outcome_quadrant": speed_outcome_quad.value,

            "cost_score": round(cost, 2),
            "representation_score": round(representation, 2),
            "cost_representation_quadrant": cost_rep_quad.value,

            "calculated_at": datetime.utcnow().isoformat(),

            "score_breakdown": {
                "severity_factors": {
                    "num_charges": len(case_data.get("summary", {}).get("charges", [])),
                    "has_violent_charges": severity > 7.0,
                },
                "complexity_factors": {
                    "num_charges": len(case_data.get("summary", {}).get("charges", [])),
                    "num_co_defendants": len(case_data.get("co_defendants", [])),
                    "num_docket_entries": len(case_data.get("docket", [])),
                    "num_attorneys": len(case_data.get("attorneys", [])),
                },
                "speed_factors": {
                    "num_docket_entries": len(case_data.get("docket", [])),
                },
                "outcome_factors": {
                    "final_status": case_data.get("outcome", {}).get("final_status", "PENDING"),
                },
                "cost_factors": {
                    "num_cost_entries": len(case_data.get("costs", [])),
                },
                "representation_factors": {
                    "num_attorneys": len(case_data.get("attorneys", [])),
                    "has_attorney": len(case_data.get("attorneys", [])) > 0,
                }
            }
        }

    def generate_quadrant_report(self, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate aggregate quadrant report for multiple cases
        """
        if not cases:
            return {"error": "No cases provided"}

        # Analyze all cases
        analyses = [self.analyze_case(case) for case in cases]

        # Count quadrant distributions
        sev_comp_dist = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
        speed_outcome_dist = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
        cost_rep_dist = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}

        for analysis in analyses:
            sev_comp_dist[analysis["severity_complexity_quadrant"]] += 1
            speed_outcome_dist[analysis["speed_outcome_quadrant"]] += 1
            cost_rep_dist[analysis["cost_representation_quadrant"]] += 1

        # Calculate averages
        avg_severity = sum(a["severity_score"] for a in analyses) / len(analyses)
        avg_complexity = sum(a["complexity_score"] for a in analyses) / len(analyses)
        avg_speed = sum(a["speed_score"] for a in analyses) / len(analyses)
        avg_outcome = sum(a["outcome_score"] for a in analyses) / len(analyses)
        avg_cost = sum(a["cost_score"] for a in analyses) / len(analyses)
        avg_representation = sum(a["representation_score"] for a in analyses) / len(analyses)

        return {
            "total_cases": len(cases),
            "quadrant_distributions": {
                "severity_complexity": sev_comp_dist,
                "speed_outcome": speed_outcome_dist,
                "cost_representation": cost_rep_dist,
            },
            "average_scores": {
                "severity": round(avg_severity, 2),
                "complexity": round(avg_complexity, 2),
                "speed": round(avg_speed, 2),
                "outcome": round(avg_outcome, 2),
                "cost": round(avg_cost, 2),
                "representation": round(avg_representation, 2),
            },
            "generated_at": datetime.utcnow().isoformat()
        }

