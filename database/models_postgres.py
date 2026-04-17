"""
PostgreSQL Database Models using SQLAlchemy
Normalized relational schema for analytics and reporting
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text, 
    ForeignKey, Date, Enum, JSON, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class CaseStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    DISPOSED = "DISPOSED"
    APPEALED = "APPEALED"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


class DispositionType(str, enum.Enum):
    CONVICTED = "CONVICTED"
    DISMISSED = "DISMISSED"
    ACQUITTED = "ACQUITTED"
    PLEA_BARGAIN = "PLEA_BARGAIN"
    NOLLE_PROSEQUI = "NOLLE_PROSEQUI"
    PENDING = "PENDING"


class ContentType(str, enum.Enum):
    FAQ = "FAQ"
    GUIDE = "GUIDE"
    JUDGE_PROFILE = "JUDGE_PROFILE"
    PROSECUTOR_PROFILE = "PROSECUTOR_PROFILE"
    RECOMMENDATION_EXPLANATION = "RECOMMENDATION_EXPLANATION"


class ContentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"


class Case(Base):
    __tablename__ = "cases"
    
    id = Column(Integer, primary_key=True)
    case_number = Column(String(50), unique=True, nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    number = Column(Integer, nullable=False)
    case_id = Column(String(50), unique=True, index=True)  # CR-25-706402-A
    
    status = Column(Enum(CaseStatus), default=CaseStatus.UNKNOWN)
    judge_id = Column(Integer, ForeignKey("judges.id"), nullable=True)
    
    # Timestamps
    arrest_date = Column(Date, nullable=True)
    indictment_date = Column(Date, nullable=True)
    disposition_date = Column(Date, nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Metadata
    arresting_agency = Column(String(200))
    agency_report_number = Column(String(100))
    appeals_case_number = Column(String(50))
    
    # Relationships
    judge = relationship("Judge", back_populates="cases")
    defendant = relationship("Defendant", back_populates="case", uselist=False)
    charges = relationship("Charge", back_populates="case", cascade="all, delete-orphan")
    docket_entries = relationship("DocketEntry", back_populates="case", cascade="all, delete-orphan")
    costs = relationship("Cost", back_populates="case", cascade="all, delete-orphan")
    bonds = relationship("Bond", back_populates="case", cascade="all, delete-orphan")
    case_attorneys = relationship("CaseAttorney", back_populates="case", cascade="all, delete-orphan")
    outcome = relationship("CaseOutcome", back_populates="case", uselist=False)
    metrics = relationship("CaseMetrics", back_populates="case", uselist=False)
    quadrant = relationship("CaseQuadrant", back_populates="case", uselist=False)
    
    __table_args__ = (
        Index('idx_case_year_number', 'year', 'number'),
    )


class Defendant(Base):
    __tablename__ = "defendants"
    
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, unique=True)
    
    name = Column(String(200), nullable=False, index=True)
    date_of_birth = Column(Date, nullable=True)
    race = Column(String(50))
    sex = Column(String(20))
    
    # Additional fields
    address = Column(Text)
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))
    
    case = relationship("Case", back_populates="defendant")


class Judge(Base):
    __tablename__ = "judges"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), unique=True, nullable=False, index=True)
    division = Column(String(100))
    
    cases = relationship("Case", back_populates="judge")
    statistics = relationship("JudgeStatistics", back_populates="judge", uselist=False)


class Charge(Base):
    __tablename__ = "charges"
    
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    
    charge_type = Column(String(50))  # INDICT, COMPLAINT, etc.
    statute = Column(String(50), index=True)
    description = Column(Text, nullable=False)
    disposition = Column(String(200))
    
    # Severity classification (from LLM)
    severity_score = Column(Float)  # 0-10 scale
    is_violent = Column(Boolean, default=False)
    is_felony = Column(Boolean, default=False)
    
    charge_date = Column(Date)
    disposition_date = Column(Date)
    
    case = relationship("Case", back_populates="charges")
    
    __table_args__ = (
        Index('idx_charge_statute', 'statute'),
    )


class Attorney(Base):
    __tablename__ = "attorneys"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), unique=True, nullable=False, index=True)
    bar_number = Column(String(50))
    firm = Column(String(200))
    
    case_attorneys = relationship("CaseAttorney", back_populates="attorney")


class CaseAttorney(Base):
    __tablename__ = "case_attorneys"

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    attorney_id = Column(Integer, ForeignKey("attorneys.id"), nullable=False)

    party = Column(String(50))  # Defense, Prosecution
    role = Column(String(100))  # Lead Counsel, Co-Counsel, etc.
    assigned_date = Column(Date)

    case = relationship("Case", back_populates="case_attorneys")
    attorney = relationship("Attorney", back_populates="case_attorneys")


class DocketEntry(Base):
    __tablename__ = "docket_entries"

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)

    entry_date = Column(Date, nullable=False)
    filed_date = Column(Date)
    entry_type = Column(String(10))  # JE, CS, SR, etc.
    description = Column(Text, nullable=False)

    # LLM-enhanced fields
    sentiment_score = Column(Float)  # -1 to 1
    is_critical = Column(Boolean, default=False)
    extracted_entities = Column(JSON)  # Names, dates, amounts mentioned

    case = relationship("Case", back_populates="docket_entries")

    __table_args__ = (
        Index('idx_docket_date', 'entry_date'),
    )


class Cost(Base):
    __tablename__ = "costs"

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)

    cost_type = Column(String(100), nullable=False)
    description = Column(String(500))
    amount = Column(Float, nullable=False)
    paid = Column(Float, default=0.0)
    balance = Column(Float, nullable=False)

    cost_date = Column(Date)
    payment_date = Column(Date, nullable=True)

    case = relationship("Case", back_populates="costs")


class Bond(Base):
    __tablename__ = "bonds"

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)

    bond_type = Column(String(100))
    amount = Column(Float)
    status = Column(String(50))
    bond_date = Column(Date)

    case = relationship("Case", back_populates="bonds")


class CaseOutcome(Base):
    __tablename__ = "case_outcomes"

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, unique=True)

    final_status = Column(Enum(DispositionType), default=DispositionType.PENDING)
    disposition_date = Column(Date)
    disposing_judge_id = Column(Integer, ForeignKey("judges.id"))

    # Sentencing details
    plea_deal = Column(Text)
    sentence_type = Column(String(100))  # Incarceration, Probation, Fine, etc.
    sentence_duration_days = Column(Integer)
    fine_amount = Column(Float)
    restitution_amount = Column(Float)
    community_service_hours = Column(Integer)

    # Appeal info
    appeal_filed = Column(Boolean, default=False)
    appeal_case_number = Column(String(50))

    case = relationship("Case", back_populates="outcome")


class CaseMetrics(Base):
    __tablename__ = "case_metrics"

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, unique=True)

    total_docket_entries = Column(Integer, default=0)
    total_costs = Column(Float, default=0.0)
    total_paid = Column(Float, default=0.0)
    total_balance = Column(Float, default=0.0)

    days_to_indictment = Column(Integer)
    days_to_disposition = Column(Integer)
    total_case_duration_days = Column(Integer)

    num_charges = Column(Integer, default=0)
    num_attorneys = Column(Integer, default=0)
    num_co_defendants = Column(Integer, default=0)

    case = relationship("Case", back_populates="metrics")


class CaseQuadrant(Base):
    __tablename__ = "case_quadrants"

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, unique=True)

    # Severity vs Complexity
    severity_score = Column(Float)  # 0-10
    complexity_score = Column(Float)  # 0-10
    severity_complexity_quadrant = Column(String(50))  # Q1, Q2, Q3, Q4

    # Speed vs Outcome
    speed_score = Column(Float)  # 0-10 (10 = fastest)
    outcome_score = Column(Float)  # 0-10 (10 = most favorable)
    speed_outcome_quadrant = Column(String(50))

    # Cost vs Representation
    cost_score = Column(Float)  # 0-10 (10 = highest cost)
    representation_score = Column(Float)  # 0-10 (10 = best representation)
    cost_representation_quadrant = Column(String(50))

    calculated_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="quadrant")


class JudgeStatistics(Base):
    __tablename__ = "judge_statistics"

    id = Column(Integer, primary_key=True)
    judge_id = Column(Integer, ForeignKey("judges.id"), nullable=False, unique=True)

    total_cases = Column(Integer, default=0)
    total_convictions = Column(Integer, default=0)
    total_dismissals = Column(Integer, default=0)
    total_acquittals = Column(Integer, default=0)

    avg_disposition_days = Column(Float)
    conviction_rate = Column(Float)  # Percentage

    avg_sentence_duration_days = Column(Float)
    avg_fine_amount = Column(Float)

    last_updated = Column(DateTime, default=datetime.utcnow)

    judge = relationship("Judge", back_populates="statistics")


class KnowledgeContent(Base):
    __tablename__ = "knowledge_content"

    id = Column(Integer, primary_key=True)
    slug = Column(String(160), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    question = Column(Text)
    summary = Column(Text)
    body = Column(Text, nullable=False)

    content_type = Column(Enum(ContentType), nullable=False, index=True)
    status = Column(Enum(ContentStatus), nullable=False, default=ContentStatus.DRAFT, index=True)
    audience = Column(String(50), default="public")
    charge_type = Column(String(50), index=True)

    tags = Column(JSON, default=list)
    source_payload = Column(JSON, default=dict)
    source_metrics = Column(JSON, default=dict)
    citations = Column(JSON, default=list)

    related_judge_id = Column(Integer, ForeignKey("judges.id"), nullable=True)
    related_prosecutor_id = Column(Integer, ForeignKey("attorneys.id"), nullable=True)
    related_attorney_id = Column(Integer, ForeignKey("attorneys.id"), nullable=True)

    prompt_version = Column(String(50), default="kb-v1")
    ai_provider = Column(String(50))
    ai_model = Column(String(100))

    reviewer_name = Column(String(200))
    reviewed_at = Column(DateTime)
    approved_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_knowledge_content_type_status", "content_type", "status"),
    )


class RecommendationExplanationSnapshot(Base):
    __tablename__ = "recommendation_explanations"

    id = Column(Integer, primary_key=True)
    content_id = Column(Integer, ForeignKey("knowledge_content.id"), nullable=True)

    judge_id = Column(Integer, ForeignKey("judges.id"), nullable=False)
    prosecutor_id = Column(Integer, ForeignKey("attorneys.id"), nullable=False)
    attorney_id = Column(Integer, ForeignKey("attorneys.id"), nullable=False)
    charge_type = Column(String(50), default="GENERAL", index=True)

    explanation_summary = Column(Text, nullable=False)
    explanation_points = Column(JSON, default=list)
    evidence = Column(JSON, default=dict)
    confidence_label = Column(String(50), default="LIMITED")

    generated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index(
            "idx_recommendation_explanations_lookup",
            "judge_id",
            "prosecutor_id",
            "attorney_id",
            "charge_type",
        ),
    )

