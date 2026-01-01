# Architecture Enhancement Plan: LLM + Database + Quadrant Analysis

## Overview
Transform the Cuyahoga CP Scraper into an intelligent legal analytics platform with:
1. **LLM Integration** - AI-powered data extraction and analysis
2. **Robust Database** - MongoDB & PostgreSQL support
3. **Quadrant Analysis** - Multi-dimensional case categorization framework
4. **Docker Deployment** - Fully containerized stack

---

## 1. LLM Integration Strategy

### Purpose
- **Enhanced Data Extraction**: Use LLMs to parse unstructured text from PDFs and docket entries
- **Sentiment Analysis**: Analyze judge rulings and attorney arguments
- **Pattern Recognition**: Identify anomalies (like Brad Davis metadata)
- **Predictive Analytics**: Predict case outcomes based on historical data
- **Natural Language Queries**: Allow users to query the database conversationally

### LLM Provider Options
1. **OpenAI GPT-4** - Best quality, requires API key
2. **Anthropic Claude** - Strong reasoning, requires API key
3. **Ollama (Local)** - Privacy-focused, runs locally (llama3, mistral, etc.)
4. **LiteLLM** - Unified interface for multiple providers

### Implementation Components

#### A. LLM Service Layer (`services/llm_service.py`)
```python
class LLMService:
    - extract_charges_from_text(text: str) -> List[Charge]
    - analyze_docket_sentiment(entries: List[Dict]) -> SentimentScore
    - predict_case_outcome(case_data: Dict) -> Prediction
    - extract_entities(text: str) -> Entities
    - summarize_case(case_data: Dict) -> Summary
```

#### B. Enhanced Extraction (`services/enhanced_extractor.py`)
- Parse complex charge descriptions
- Extract sentencing details from JE entries
- Identify plea bargain terms
- Extract attorney arguments from motions

#### C. Anomaly Detection (`services/anomaly_detector.py`)
- Detect unusual PDF metadata patterns
- Identify statistical outliers in case processing times
- Flag suspicious attorney/judge combinations

---

## 2. Database Architecture

### Dual Database Strategy

#### MongoDB (Document Store)
**Use Case**: Store raw scraped data with flexible schema
- Full JSON documents as-is
- PDF metadata and binary storage
- Audit logs and scraping history
- Fast writes, schema flexibility

#### PostgreSQL (Relational)
**Use Case**: Structured analytics and reporting
- Normalized tables for efficient queries
- Complex joins and aggregations
- Time-series analysis
- ACID compliance for critical data

### Schema Design

#### PostgreSQL Schema
```sql
-- Core Tables
cases (id, case_number, year, status, judge_id, scraped_at)
defendants (id, case_id, name, dob, race, sex)
charges (id, case_id, statute, description, disposition, charge_date)
attorneys (id, name, party, role)
case_attorneys (case_id, attorney_id, assigned_date)
judges (id, name, division)
docket_entries (id, case_id, entry_date, entry_type, description)
costs (id, case_id, cost_type, amount, paid, balance, date)
bonds (id, case_id, bond_type, amount, status, date)

-- Analytics Tables
case_outcomes (case_id, final_status, disposition_date, sentence_type, duration)
case_metrics (case_id, total_docket_entries, total_costs, days_to_disposition)
judge_statistics (judge_id, total_cases, avg_disposition_days, conviction_rate)
```

#### MongoDB Collections
```javascript
{
  raw_cases: {  // Original scraped JSON
    _id, case_number, year, metadata, summary, docket, costs, ...
  },
  pdf_documents: {  // PDF storage
    _id, case_id, filename, content_type, data, metadata
  },
  scrape_logs: {  // Audit trail
    _id, timestamp, case_number, status, errors, duration
  },
  llm_analysis: {  // AI-generated insights
    _id, case_id, analysis_type, result, confidence, timestamp
  }
}
```

---

## 3. Quadrant Analysis Framework

### What is Quadrant Analysis?
A multi-dimensional categorization system that places cases into strategic quadrants based on key metrics.

### Proposed Quadrants

#### Quadrant 1: Severity vs. Complexity
```
High Severity, High Complexity  |  High Severity, Low Complexity
--------------------------------|--------------------------------
Complex felonies, multiple      |  Simple violent crimes,
charges, co-defendants          |  single charge felonies
--------------------------------|--------------------------------
Low Severity, High Complexity   |  Low Severity, Low Complexity
--------------------------------|--------------------------------
Multiple misdemeanors,          |  Simple misdemeanors,
procedural issues               |  traffic violations
```

#### Quadrant 2: Speed vs. Outcome
```
Fast Resolution, Favorable      |  Fast Resolution, Unfavorable
--------------------------------|--------------------------------
Quick plea deals, dismissals    |  Quick convictions, guilty pleas
--------------------------------|--------------------------------
Slow Resolution, Favorable      |  Slow Resolution, Unfavorable
--------------------------------|--------------------------------
Long trials ending in acquittal |  Lengthy proceedings, conviction
```

#### Quadrant 3: Cost vs. Representation Quality
```
High Cost, Good Representation  |  High Cost, Poor Representation
--------------------------------|--------------------------------
Private attorney, low costs     |  Private attorney, high costs
--------------------------------|--------------------------------
Low Cost, Good Representation   |  Low Cost, Poor Representation
--------------------------------|--------------------------------
Public defender, low costs      |  Public defender, high costs
```

### Quadrant Calculation Engine
```python
class QuadrantAnalyzer:
    def calculate_severity_score(case: Case) -> float
    def calculate_complexity_score(case: Case) -> float
    def calculate_speed_score(case: Case) -> float
    def calculate_outcome_score(case: Case) -> float
    def assign_quadrant(case: Case) -> Quadrant
    def generate_quadrant_report(cases: List[Case]) -> Report
```

---

## 4. Technology Stack

### Core Services
- **Scraper**: Playwright + Python (existing)
- **LLM**: LiteLLM + Ollama (local) or OpenAI/Claude (cloud)
- **Databases**: PostgreSQL 16 + MongoDB 7
- **API**: FastAPI (REST + GraphQL)
- **Queue**: Redis + Celery (async processing)
- **Cache**: Redis
- **Search**: Elasticsearch (optional, for full-text search)

### Docker Services
```yaml
services:
  - scraper (Python app)
  - postgres (relational DB)
  - mongodb (document DB)
  - redis (cache + queue)
  - ollama (local LLM)
  - api (FastAPI)
  - worker (Celery)
  - nginx (reverse proxy)
```

---

## Next Steps
1. ✅ Design database schemas
2. Create database models (SQLAlchemy + Motor)
3. Implement LLM service layer
4. Build quadrant analysis engine
5. Update Docker compose with all services
6. Create migration scripts for existing data
7. Build API endpoints
8. Create analytics dashboard

