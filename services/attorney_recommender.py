"""
Attorney Recommendation Engine
Recommends best defense attorneys based on judge, prosecutor, and charge type
Uses historical performance data and machine learning
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
import numpy as np


class AttorneyRecommender:
    """
    Intelligent attorney recommendation system
    Analyzes historical matchups to suggest optimal defense counsel
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def get_recommendations(
        self,
        judge_id: int,
        prosecutor_id: int,
        charge_type: str = "GENERAL",
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get top N attorney recommendations for a specific matchup
        
        Args:
            judge_id: ID of the judge
            prosecutor_id: ID of the prosecutor
            charge_type: Type of charge (VIOLENT, DRUG, PROPERTY, etc.)
            top_n: Number of recommendations to return
            
        Returns:
            List of attorney recommendations with scores and metrics
        """
        # Get all defense attorneys with performance data
        from database.analytics_models import DefenseAttorneyPerformance
        from database.models_postgres import Attorney
        
        attorneys = self.db.query(
            Attorney,
            DefenseAttorneyPerformance
        ).join(
            DefenseAttorneyPerformance,
            Attorney.id == DefenseAttorneyPerformance.attorney_id
        ).filter(
            DefenseAttorneyPerformance.total_cases >= 5  # Minimum case threshold
        ).all()
        
        if not attorneys:
            return []
        
        # Score each attorney
        scored_attorneys = []
        for attorney, performance in attorneys:
            score = self._calculate_attorney_score(
                attorney.id,
                judge_id,
                prosecutor_id,
                charge_type,
                performance
            )
            
            scored_attorneys.append({
                "attorney_id": attorney.id,
                "attorney_name": attorney.name,
                "firm": attorney.firm,
                "score": score,
                "overall_win_rate": performance.win_rate,
                "total_cases": performance.total_cases,
                "effectiveness_score": performance.effectiveness_score,
                "matchup_win_rate": self._get_matchup_win_rate(
                    attorney.id, judge_id, prosecutor_id, performance
                ),
                "charge_type_win_rate": self._get_charge_type_win_rate(
                    charge_type, performance
                ),
                "avg_sentence_reduction": performance.sentence_reduction_rate,
                "trial_win_rate": performance.trial_win_rate,
            })
        
        # Sort by score descending
        scored_attorneys.sort(key=lambda x: x["score"], reverse=True)
        
        return scored_attorneys[:top_n]
    
    def _calculate_attorney_score(
        self,
        attorney_id: int,
        judge_id: int,
        prosecutor_id: int,
        charge_type: str,
        performance: Any
    ) -> float:
        """
        Calculate composite score for attorney recommendation
        
        Scoring factors:
        1. Matchup-specific win rate (40% weight)
        2. Charge-type specific win rate (30% weight)
        3. Overall effectiveness score (15% weight)
        4. Trial win rate (10% weight)
        5. Sentence reduction rate (5% weight)
        """
        # 1. Matchup-specific performance
        matchup_key = f"{judge_id}_{prosecutor_id}"
        matchup_data = performance.performance_by_matchup.get(matchup_key, {})
        matchup_win_rate = matchup_data.get("win_rate", performance.win_rate)
        matchup_score = matchup_win_rate * 40.0
        
        # 2. Charge-type specific performance
        charge_win_rate = self._get_charge_type_win_rate(charge_type, performance)
        charge_score = charge_win_rate * 30.0
        
        # 3. Overall effectiveness
        effectiveness_score = (performance.effectiveness_score / 10.0) * 15.0
        
        # 4. Trial performance
        trial_score = performance.trial_win_rate * 10.0
        
        # 5. Sentence mitigation
        sentence_score = performance.sentence_reduction_rate * 5.0
        
        # Total score (0-100)
        total_score = (
            matchup_score +
            charge_score +
            effectiveness_score +
            trial_score +
            sentence_score
        )
        
        # Confidence penalty for low case volume
        if performance.total_cases < 20:
            confidence_penalty = (20 - performance.total_cases) * 0.02
            total_score *= (1.0 - confidence_penalty)
        
        return round(total_score, 2)
    
    def _get_matchup_win_rate(
        self,
        attorney_id: int,
        judge_id: int,
        prosecutor_id: int,
        performance: Any
    ) -> float:
        """Get win rate for specific judge-prosecutor matchup"""
        matchup_key = f"{judge_id}_{prosecutor_id}"
        matchup_data = performance.performance_by_matchup.get(matchup_key, {})
        return matchup_data.get("win_rate", performance.win_rate)
    
    def _get_charge_type_win_rate(
        self,
        charge_type: str,
        performance: Any
    ) -> float:
        """Get win rate for specific charge type"""
        charge_type_map = {
            "VIOLENT": performance.violent_crime_win_rate,
            "DRUG": performance.drug_crime_win_rate,
            "PROPERTY": performance.property_crime_win_rate,
        }
        return charge_type_map.get(charge_type, performance.win_rate)

    def get_matchup_analysis(
        self,
        judge_id: int,
        prosecutor_id: int
    ) -> Dict[str, Any]:
        """
        Get detailed analysis of a judge-prosecutor matchup
        """
        from database.analytics_models import (
            JudgeProsecutorMatchup,
            JudgePerformance,
            ProsecutorPerformance
        )
        from database.models_postgres import Judge, Attorney

        # Get matchup data
        matchup = self.db.query(JudgeProsecutorMatchup).filter(
            and_(
                JudgeProsecutorMatchup.judge_id == judge_id,
                JudgeProsecutorMatchup.prosecutor_id == prosecutor_id
            )
        ).first()

        # Get judge data
        judge = self.db.query(Judge, JudgePerformance).join(
            JudgePerformance
        ).filter(Judge.id == judge_id).first()

        # Get prosecutor data
        prosecutor = self.db.query(Attorney, ProsecutorPerformance).join(
            ProsecutorPerformance
        ).filter(Attorney.id == prosecutor_id).first()

        if not matchup or not judge or not prosecutor:
            return {"error": "Matchup data not found"}

        judge_obj, judge_perf = judge
        prosecutor_obj, prosecutor_perf = prosecutor

        return {
            "judge": {
                "id": judge_obj.id,
                "name": judge_obj.name,
                "total_cases": judge_perf.total_cases,
                "conviction_rate": judge_perf.conviction_rate,
                "defendant_favorability": judge_perf.defendant_favorability_score,
                "avg_sentence_days": judge_perf.avg_sentence_duration_days,
            },
            "prosecutor": {
                "id": prosecutor_obj.id,
                "name": prosecutor_obj.name,
                "total_cases": prosecutor_perf.total_cases,
                "conviction_rate": prosecutor_perf.conviction_rate,
                "aggressiveness": prosecutor_perf.aggressiveness_score,
                "trial_win_rate": prosecutor_perf.trial_win_rate,
            },
            "matchup": {
                "total_cases": matchup.total_cases,
                "conviction_rate": matchup.conviction_rate,
                "avg_sentence_days": matchup.avg_sentence_duration_days,
                "avg_days_to_disposition": matchup.avg_days_to_disposition,
                "defendant_favorability": matchup.defendant_favorability_score,
            },
            "recommendation": {
                "difficulty_level": self._calculate_difficulty_level(matchup),
                "strategy_suggestions": self._get_strategy_suggestions(
                    judge_perf, prosecutor_perf, matchup
                ),
            }
        }

    def _calculate_difficulty_level(self, matchup: Any) -> str:
        """Calculate difficulty level for defendant"""
        if matchup.conviction_rate >= 0.8:
            return "VERY_DIFFICULT"
        elif matchup.conviction_rate >= 0.6:
            return "DIFFICULT"
        elif matchup.conviction_rate >= 0.4:
            return "MODERATE"
        elif matchup.conviction_rate >= 0.2:
            return "FAVORABLE"
        else:
            return "VERY_FAVORABLE"

    def _get_strategy_suggestions(
        self,
        judge_perf: Any,
        prosecutor_perf: Any,
        matchup: Any
    ) -> List[str]:
        """Generate strategic suggestions based on matchup"""
        suggestions = []

        # Judge-based suggestions
        if judge_perf.defendant_favorability_score >= 7.0:
            suggestions.append("Judge has favorable track record for defendants - consider trial")
        elif judge_perf.defendant_favorability_score <= 3.0:
            suggestions.append("Judge tends to favor prosecution - negotiate plea early")

        if judge_perf.avg_days_to_disposition > 180:
            suggestions.append("Judge has slow case processing - prepare for long timeline")

        # Prosecutor-based suggestions
        if prosecutor_perf.aggressiveness_score >= 8.0:
            suggestions.append("Prosecutor is highly aggressive - expect tough negotiations")

        if prosecutor_perf.trial_win_rate <= 0.4:
            suggestions.append("Prosecutor has low trial win rate - trial may be viable option")

        if prosecutor_perf.plea_bargain_rate >= 0.7:
            suggestions.append("Prosecutor frequently offers plea deals - negotiate strategically")

        # Matchup-based suggestions
        if matchup.conviction_rate >= 0.8:
            suggestions.append("This matchup has high conviction rate - consider experienced trial attorney")

        if matchup.avg_sentence_days > judge_perf.avg_sentence_duration_days * 1.2:
            suggestions.append("This matchup results in harsher sentences - focus on mitigation")

        return suggestions

    def compare_attorneys(
        self,
        attorney_ids: List[int],
        judge_id: int,
        prosecutor_id: int,
        charge_type: str = "GENERAL"
    ) -> Dict[str, Any]:
        """
        Compare multiple attorneys side-by-side for a specific matchup
        """
        from database.analytics_models import DefenseAttorneyPerformance
        from database.models_postgres import Attorney

        comparisons = []

        for attorney_id in attorney_ids:
            attorney = self.db.query(Attorney, DefenseAttorneyPerformance).join(
                DefenseAttorneyPerformance
            ).filter(Attorney.id == attorney_id).first()

            if not attorney:
                continue

            attorney_obj, performance = attorney

            score = self._calculate_attorney_score(
                attorney_id, judge_id, prosecutor_id, charge_type, performance
            )

            comparisons.append({
                "attorney_id": attorney_id,
                "attorney_name": attorney_obj.name,
                "firm": attorney_obj.firm,
                "recommendation_score": score,
                "overall_win_rate": performance.win_rate,
                "matchup_win_rate": self._get_matchup_win_rate(
                    attorney_id, judge_id, prosecutor_id, performance
                ),
                "charge_type_win_rate": self._get_charge_type_win_rate(
                    charge_type, performance
                ),
                "total_cases": performance.total_cases,
                "trial_win_rate": performance.trial_win_rate,
                "avg_sentence_days": performance.avg_sentence_duration_days,
                "effectiveness_score": performance.effectiveness_score,
            })

        # Sort by recommendation score
        comparisons.sort(key=lambda x: x["recommendation_score"], reverse=True)

        return {
            "attorneys": comparisons,
            "best_choice": comparisons[0] if comparisons else None,
            "comparison_date": datetime.utcnow().isoformat()
        }

