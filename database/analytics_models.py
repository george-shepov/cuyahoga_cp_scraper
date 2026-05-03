"""
Analytics Models for Legal Professional Performance Tracking
Tracks judges, prosecutors, and defense attorneys with detailed metrics
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime,
    ForeignKey, JSON, Index
)
from sqlalchemy.orm import declarative_base, relationship

from database.models_postgres import Attorney, Judge

Base = declarative_base()


class JudgePerformance(Base):
    """Comprehensive judge performance metrics"""
    __tablename__ = "judge_performance"
    
    id = Column(Integer, primary_key=True)
    judge_id = Column(Integer, ForeignKey("judges.id"), nullable=False, unique=True)
    
    # Case volume metrics
    total_cases = Column(Integer, default=0)
    cases_this_year = Column(Integer, default=0)
    avg_cases_per_year = Column(Float, default=0.0)
    
    # Disposition metrics
    total_convictions = Column(Integer, default=0)
    total_dismissals = Column(Integer, default=0)
    total_acquittals = Column(Integer, default=0)
    total_plea_bargains = Column(Integer, default=0)
    
    # Rates (percentages)
    conviction_rate = Column(Float, default=0.0)  # % of cases ending in conviction
    dismissal_rate = Column(Float, default=0.0)
    acquittal_rate = Column(Float, default=0.0)
    plea_bargain_rate = Column(Float, default=0.0)
    
    # Timing metrics
    avg_days_to_disposition = Column(Float, default=0.0)
    median_days_to_disposition = Column(Float, default=0.0)
    fastest_case_days = Column(Integer)
    slowest_case_days = Column(Integer)
    
    # Sentencing metrics
    avg_sentence_duration_days = Column(Float, default=0.0)
    avg_fine_amount = Column(Float, default=0.0)
    avg_restitution_amount = Column(Float, default=0.0)
    
    # Severity metrics (by charge type)
    violent_crime_conviction_rate = Column(Float, default=0.0)
    drug_crime_conviction_rate = Column(Float, default=0.0)
    property_crime_conviction_rate = Column(Float, default=0.0)
    
    # Defendant favorability score (0-10, higher = more favorable to defendants)
    defendant_favorability_score = Column(Float, default=5.0)
    
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    judge = relationship(Judge)


class ProsecutorPerformance(Base):
    """Prosecutor performance and conviction tracking"""
    __tablename__ = "prosecutor_performance"
    
    id = Column(Integer, primary_key=True)
    attorney_id = Column(Integer, ForeignKey("attorneys.id"), nullable=False, unique=True)
    
    # Case volume
    total_cases = Column(Integer, default=0)
    cases_this_year = Column(Integer, default=0)
    avg_cases_per_year = Column(Float, default=0.0)
    active_cases = Column(Integer, default=0)
    
    # Win/Loss record
    total_convictions = Column(Integer, default=0)
    total_dismissals = Column(Integer, default=0)
    total_acquittals = Column(Integer, default=0)
    total_plea_bargains = Column(Integer, default=0)
    
    # Success rates
    conviction_rate = Column(Float, default=0.0)  # Convictions / Total disposed cases
    trial_win_rate = Column(Float, default=0.0)  # Convictions from trial / Total trials
    plea_bargain_rate = Column(Float, default=0.0)
    
    # Timing
    avg_days_to_disposition = Column(Float, default=0.0)
    avg_days_to_plea = Column(Float, default=0.0)
    avg_days_to_trial = Column(Float, default=0.0)
    
    # Sentencing outcomes
    avg_sentence_duration_days = Column(Float, default=0.0)
    avg_fine_secured = Column(Float, default=0.0)
    avg_restitution_secured = Column(Float, default=0.0)
    
    # By charge type
    violent_crime_conviction_rate = Column(Float, default=0.0)
    drug_crime_conviction_rate = Column(Float, default=0.0)
    property_crime_conviction_rate = Column(Float, default=0.0)
    
    # Aggressiveness score (0-10, higher = more aggressive)
    aggressiveness_score = Column(Float, default=5.0)
    
    # Judge-specific performance (JSON: {judge_id: {conviction_rate, avg_sentence, ...}})
    performance_by_judge = Column(JSON, default={})
    
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    attorney = relationship(Attorney)


class DefenseAttorneyPerformance(Base):
    """Defense attorney performance and win tracking"""
    __tablename__ = "defense_attorney_performance"
    
    id = Column(Integer, primary_key=True)
    attorney_id = Column(Integer, ForeignKey("attorneys.id"), nullable=False, unique=True)
    
    # Case volume
    total_cases = Column(Integer, default=0)
    cases_this_year = Column(Integer, default=0)
    avg_cases_per_year = Column(Float, default=0.0)
    active_cases = Column(Integer, default=0)
    
    # Win/Loss record (from defendant perspective)
    total_dismissals = Column(Integer, default=0)  # Wins
    total_acquittals = Column(Integer, default=0)  # Wins
    total_favorable_pleas = Column(Integer, default=0)  # Partial wins
    total_convictions = Column(Integer, default=0)  # Losses
    
    # Success rates
    dismissal_rate = Column(Float, default=0.0)
    acquittal_rate = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)  # (Dismissals + Acquittals) / Total
    favorable_outcome_rate = Column(Float, default=0.0)  # Includes favorable pleas
    
    # Trial performance
    trial_win_rate = Column(Float, default=0.0)  # Acquittals / Total trials
    total_trials = Column(Integer, default=0)
    
    # Timing
    avg_days_to_disposition = Column(Float, default=0.0)
    avg_days_to_dismissal = Column(Float, default=0.0)
    
    # Sentencing mitigation (when convicted)
    avg_sentence_duration_days = Column(Float, default=0.0)
    avg_fine_amount = Column(Float, default=0.0)
    sentence_reduction_rate = Column(Float, default=0.0)  # % below average for charge type

    # By charge type
    violent_crime_win_rate = Column(Float, default=0.0)
    drug_crime_win_rate = Column(Float, default=0.0)
    property_crime_win_rate = Column(Float, default=0.0)

    # Effectiveness score (0-10, higher = more effective)
    effectiveness_score = Column(Float, default=5.0)

    # Judge-specific performance (JSON: {judge_id: {win_rate, avg_sentence, ...}})
    performance_by_judge = Column(JSON, default={})

    # Prosecutor-specific performance (JSON: {prosecutor_id: {win_rate, ...}})
    performance_by_prosecutor = Column(JSON, default={})

    # Combined matchup performance (JSON: {judge_prosecutor_combo: {win_rate, ...}})
    performance_by_matchup = Column(JSON, default={})

    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    attorney = relationship(Attorney)


class JudgeProsecutorMatchup(Base):
    """Track performance of specific judge-prosecutor combinations"""
    __tablename__ = "judge_prosecutor_matchups"

    id = Column(Integer, primary_key=True)
    judge_id = Column(Integer, ForeignKey("judges.id"), nullable=False)
    prosecutor_id = Column(Integer, ForeignKey("attorneys.id"), nullable=False)

    total_cases = Column(Integer, default=0)
    total_convictions = Column(Integer, default=0)
    total_dismissals = Column(Integer, default=0)
    total_acquittals = Column(Integer, default=0)

    conviction_rate = Column(Float, default=0.0)
    avg_sentence_duration_days = Column(Float, default=0.0)
    avg_days_to_disposition = Column(Float, default=0.0)

    # Defendant favorability for this combo (0-10)
    defendant_favorability_score = Column(Float, default=5.0)

    last_updated = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_judge_prosecutor', 'judge_id', 'prosecutor_id'),
    )


class AttorneyRecommendation(Base):
    """Pre-calculated attorney recommendations for judge/prosecutor combinations"""
    __tablename__ = "attorney_recommendations"

    id = Column(Integer, primary_key=True)
    judge_id = Column(Integer, ForeignKey("judges.id"), nullable=False)
    prosecutor_id = Column(Integer, ForeignKey("attorneys.id"), nullable=False)
    charge_type = Column(String(50))  # VIOLENT, DRUG, PROPERTY, etc.

    # Top 5 recommended attorneys
    recommended_attorney_1_id = Column(Integer, ForeignKey("attorneys.id"))
    recommended_attorney_1_score = Column(Float)
    recommended_attorney_1_win_rate = Column(Float)

    recommended_attorney_2_id = Column(Integer, ForeignKey("attorneys.id"))
    recommended_attorney_2_score = Column(Float)
    recommended_attorney_2_win_rate = Column(Float)

    recommended_attorney_3_id = Column(Integer, ForeignKey("attorneys.id"))
    recommended_attorney_3_score = Column(Float)
    recommended_attorney_3_win_rate = Column(Float)

    recommended_attorney_4_id = Column(Integer, ForeignKey("attorneys.id"))
    recommended_attorney_4_score = Column(Float)
    recommended_attorney_4_win_rate = Column(Float)

    recommended_attorney_5_id = Column(Integer, ForeignKey("attorneys.id"))
    recommended_attorney_5_score = Column(Float)
    recommended_attorney_5_win_rate = Column(Float)

    # Metadata
    total_attorneys_analyzed = Column(Integer)
    confidence_score = Column(Float)  # 0-1
    calculated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_judge_prosecutor_charge', 'judge_id', 'prosecutor_id', 'charge_type'),
    )


class CaseTypeStatistics(Base):
    """Aggregate statistics by case/charge type"""
    __tablename__ = "case_type_statistics"

    id = Column(Integer, primary_key=True)
    charge_type = Column(String(50), unique=True, nullable=False)  # VIOLENT, DRUG, etc.
    statute_prefix = Column(String(20))  # e.g., "2903" for assault

    total_cases = Column(Integer, default=0)

    # Outcomes
    avg_conviction_rate = Column(Float, default=0.0)
    avg_dismissal_rate = Column(Float, default=0.0)
    avg_acquittal_rate = Column(Float, default=0.0)
    avg_plea_bargain_rate = Column(Float, default=0.0)

    # Timing
    avg_days_to_disposition = Column(Float, default=0.0)
    median_days_to_disposition = Column(Float, default=0.0)

    # Sentencing
    avg_sentence_duration_days = Column(Float, default=0.0)
    median_sentence_duration_days = Column(Float, default=0.0)
    avg_fine_amount = Column(Float, default=0.0)

    last_updated = Column(DateTime, default=datetime.utcnow)


class YearlyTrends(Base):
    """Track yearly trends for judges, prosecutors, attorneys"""
    __tablename__ = "yearly_trends"

    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False)
    entity_type = Column(String(20), nullable=False)  # JUDGE, PROSECUTOR, DEFENSE_ATTORNEY
    entity_id = Column(Integer, nullable=False)  # ID of judge/attorney

    # Volume
    total_cases = Column(Integer, default=0)
    new_cases = Column(Integer, default=0)
    closed_cases = Column(Integer, default=0)

    # Outcomes
    convictions = Column(Integer, default=0)
    dismissals = Column(Integer, default=0)
    acquittals = Column(Integer, default=0)
    plea_bargains = Column(Integer, default=0)

    # Rates
    conviction_rate = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)  # Context-dependent

    # Timing
    avg_case_lifetime_days = Column(Float, default=0.0)

    __table_args__ = (
        Index('idx_year_entity', 'year', 'entity_type', 'entity_id'),
    )
