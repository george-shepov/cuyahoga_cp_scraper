"""
MongoDB Models using Motor (async) and Pydantic
Document-oriented storage for raw scraped data and flexible schemas
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic"""
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


class RawCaseDocument(BaseModel):
    """
    Stores the complete raw JSON from scraper
    Mirrors the existing output structure
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    
    # Core identifiers
    case_number: str = Field(..., index=True)
    year: int = Field(..., index=True)
    case_id: Optional[str] = Field(None, index=True)
    
    # Raw scraped data (as-is from scraper)
    metadata: Dict[str, Any]
    summary: Dict[str, Any]
    docket: List[Dict[str, Any]]
    costs: List[Dict[str, Any]]
    defendant: Dict[str, Any]
    attorneys: List[Dict[str, Any]]
    co_defendants: List[Dict[str, Any]] = []
    bonds: List[Dict[str, Any]] = []
    case_actions: List[Dict[str, Any]] = []
    judge_history: List[Dict[str, Any]] = []
    outcome: Dict[str, Any] = {}
    errors: List[Dict[str, Any]] = []
    html_snapshots: Dict[str, str] = {}
    pdf_info: Optional[Dict[str, Any]] = None
    
    # Indexing and search
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class PDFDocument(BaseModel):
    """Stores PDF files and metadata"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    
    case_id: str = Field(..., index=True)
    case_number: str = Field(..., index=True)
    filename: str
    
    # PDF metadata
    content_type: str = "application/pdf"
    size_bytes: int
    page_count: Optional[int] = None
    
    # Extracted metadata
    pdf_metadata: Dict[str, Any] = {}  # Creator, Author, Title, etc.
    
    # Binary data (GridFS reference or base64)
    gridfs_id: Optional[str] = None  # If using GridFS
    data: Optional[bytes] = None  # If storing inline (small PDFs)
    
    # Anomaly flags
    has_anomaly: bool = False
    anomaly_type: Optional[str] = None  # e.g., "brad_davis_metadata"
    anomaly_details: Dict[str, Any] = {}
    
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class ScrapeLog(BaseModel):
    """Audit trail for scraping operations"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    
    case_number: str = Field(..., index=True)
    year: int
    operation: str  # scrape, repair, update
    
    status: str  # success, failed, partial
    errors: List[Dict[str, Any]] = []
    
    duration_seconds: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Scraper metadata
    scraper_version: str = "1.0.0"
    headless: bool = True
    download_pdfs: bool = False
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class LLMAnalysis(BaseModel):
    """Stores AI-generated insights and analysis"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    
    case_id: str = Field(..., index=True)
    case_number: str = Field(..., index=True)
    
    analysis_type: str = Field(..., index=True)  # sentiment, extraction, prediction, summary
    
    # Input and output
    input_data: Dict[str, Any]
    result: Dict[str, Any]
    
    # Metadata
    model_name: str  # gpt-4, claude-3, llama3, etc.
    confidence_score: Optional[float] = None  # 0-1
    tokens_used: Optional[int] = None
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class QuadrantAnalysis(BaseModel):
    """Stores quadrant analysis results"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    
    case_id: str = Field(..., index=True)
    case_number: str = Field(..., index=True)
    
    # Severity vs Complexity
    severity_score: float
    complexity_score: float
    severity_complexity_quadrant: str  # Q1, Q2, Q3, Q4
    
    # Speed vs Outcome
    speed_score: float
    outcome_score: float
    speed_outcome_quadrant: str
    
    # Cost vs Representation
    cost_score: float
    representation_score: float
    cost_representation_quadrant: str
    
    # Detailed breakdown
    score_breakdown: Dict[str, Any] = {}
    
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

