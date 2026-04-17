# Cuyahoga Court Analytics Guide

## Overview

The Cuyahoga Court Scraper now includes comprehensive analytics and AI-powered insights for legal professionals. This system tracks judges, prosecutors, and defense attorneys to provide data-driven recommendations.

## Crime Type Classification

The operations dashboard no longer relies only on `summary.charges` when assigning crime types. When the court JSON omits normalized charges, analytics now recover charge signals from:

- Embedded charge tables stored in `summary.fields`
- Summary statute fields such as `INDICT` or `COMPLAINT`
- Docket entries that contain charge language or cited statutes

If a case JSON has no usable offense signal in any of those places, analytics classify it as `OTHER` instead of `UNKNOWN`. This keeps the crime-type charts aligned with what is actually present in the scraped record.

When a case contains both a specific category and residual `OTHER` rows, the dashboard now uses the specific category as the case's `primary_crime_type` instead of letting `OTHER` win by sort order alone.

## Key Features

### 1. **Attorney Recommendation Engine** 🎯

Get the best defense attorney recommendations based on:
- **Judge-Prosecutor Matchup**: Historical performance of attorneys against specific judge/prosecutor combinations
- **Charge Type**: Win rates for violent crimes, drug offenses, property crimes, etc.
- **Trial Performance**: Success rates in trial vs. plea negotiations
- **Sentence Mitigation**: Ability to reduce sentences when convicted

**Example API Call:**
```bash
curl -X POST "http://localhost:8000/api/v1/recommendations" \
  -H "Content-Type: application/json" \
  -d '{
    "judge_id": 123,
    "prosecutor_id": 456,
    "charge_type": "VIOLENT",
    "top_n": 5
  }'
```

**Response:**
```json
[
  {
    "attorney_id": 789,
    "attorney_name": "Jane Smith",
    "firm": "Smith & Associates",
    "score": 87.5,
    "overall_win_rate": 65.2,
    "matchup_win_rate": 72.3,
    "charge_type_win_rate": 68.9,
    "total_cases": 145,
    "effectiveness_score": 8.2
  }
]
```

### 2. **Judge Performance Tracking** ⚖️

Comprehensive metrics for each judge:
- **Case Volume**: Total cases, cases per year, current caseload
- **Disposition Rates**: Conviction, dismissal, acquittal, plea bargain rates
- **Timing**: Average days to disposition, fastest/slowest cases
- **Sentencing**: Average sentence duration, fines, restitution
- **Defendant Favorability Score**: 0-10 scale (higher = more favorable to defendants)
- **Charge-Type Specific Rates**: Performance on violent, drug, property crimes

### 3. **Prosecutor Performance Tracking** 📊

Track prosecutor effectiveness:
- **Conviction Rate**: Overall success rate
- **Trial Win Rate**: Success in cases that go to trial
- **Plea Bargain Rate**: Frequency of plea deals
- **Aggressiveness Score**: 0-10 scale (higher = more aggressive)
- **Performance by Judge**: How they perform with different judges
- **Case Load**: Active cases, new cases per year

### 4. **Defense Attorney Performance Tracking** 🛡️

Measure defense attorney success:
- **Win Rate**: Dismissals + Acquittals / Total cases
- **Trial Win Rate**: Acquittals / Total trials
- **Favorable Outcome Rate**: Includes favorable plea bargains
- **Effectiveness Score**: 0-10 composite score
- **Performance by Judge**: Win rates with specific judges
- **Performance by Prosecutor**: Win rates against specific prosecutors
- **Matchup Performance**: Win rates for judge-prosecutor combinations

### 5. **Quadrant Analysis System** 📈

Multi-dimensional case categorization:

#### **Quadrant 1: Severity vs. Complexity**
- **X-axis**: Severity (0-10) - Based on charge types, violence indicators
- **Y-axis**: Complexity (0-10) - Based on # of charges, co-defendants, docket entries
- **Use Case**: Resource allocation, case prioritization

#### **Quadrant 2: Speed vs. Outcome**
- **X-axis**: Speed (0-10) - Days from arrest to disposition (inverse)
- **Y-axis**: Outcome (0-10) - Favorability for defendant
- **Use Case**: Identify efficient vs. favorable outcomes

#### **Quadrant 3: Cost vs. Representation Quality**
- **X-axis**: Cost (0-10) - Total fines, fees, restitution
- **Y-axis**: Representation (0-10) - Attorney quality/type
- **Use Case**: Cost-benefit analysis of legal representation

### 6. **Document Analysis** 📄

AI-powered PDF analysis using LLMs:
- **Document Classification**: Motion, Order, Brief, Indictment, etc.
- **Entity Extraction**: Names, dates, amounts, legal citations
- **Sentiment Analysis**: Favorable vs. unfavorable for defendant
- **Summary Generation**: Concise 2-3 sentence summaries
- **Legal Element Extraction**: Sentencing details, motion specifics, order rulings

**Example:**
```python
from services.document_analyzer import DocumentAnalyzer

analyzer = DocumentAnalyzer()
result = await analyzer.analyze_pdf("path/to/sentencing_entry.pdf")

print(result["document_type"])  # "SENTENCING"
print(result["summary"])  # AI-generated summary
print(result["sentiment"]["sentiment_score"])  # -0.7 (unfavorable)
print(result["legal_elements"]["sentence_duration_days"])  # 365
```

### 7. **Matchup Analysis** 🤝

Detailed analysis of judge-prosecutor combinations:
- **Historical Performance**: Conviction rates, sentence lengths
- **Difficulty Level**: VERY_DIFFICULT, DIFFICULT, MODERATE, FAVORABLE, VERY_FAVORABLE
- **Strategy Suggestions**: AI-generated recommendations
  - "Judge has favorable track record for defendants - consider trial"
  - "Prosecutor is highly aggressive - expect tough negotiations"
  - "This matchup has high conviction rate - consider experienced trial attorney"

## Database Architecture

### PostgreSQL (Relational Analytics)
- **Core Tables**: Case, Defendant, Judge, Charge, Attorney
- **Analytics Tables**: JudgePerformance, ProsecutorPerformance, DefenseAttorneyPerformance
- **Matchup Tables**: JudgeProsecutorMatchup, AttorneyRecommendation
- **Statistics Tables**: CaseTypeStatistics, YearlyTrends

### MongoDB (Document Store)
- **RawCaseDocument**: Complete scraped JSON
- **PDFDocument**: PDF files with GridFS
- **LLMAnalysis**: AI-generated insights
- **QuadrantAnalysis**: Quadrant categorization results
- **ScrapeLog**: Audit trail

## LLM Integration

Supports multiple LLM providers:
- **Ollama** (default): Local, privacy-focused, free
- **OpenAI**: GPT-4, GPT-3.5
- **Anthropic**: Claude 3
- **Groq**: Fast inference

**Configuration:**
```bash
# .env file
LLM_PROVIDER=ollama  # or openai, anthropic, groq
LLM_MODEL=llama3     # or gpt-4, claude-3-opus, etc.
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/recommendations` | POST | Get attorney recommendations |
| `/api/v1/matchup` | GET | Analyze judge-prosecutor matchup |
| `/api/v1/judges/{id}/performance` | GET | Judge performance metrics |
| `/api/v1/prosecutors/{id}/performance` | GET | Prosecutor performance metrics |
| `/api/v1/attorneys/{id}/performance` | GET | Attorney performance metrics |
| `/api/v1/documents/analyze` | POST | Analyze PDF document |
| `/api/v1/cases/{id}/quadrant` | GET | Quadrant analysis for case |
| `/api/v1/attorneys/compare` | POST | Compare multiple attorneys |
| `/api/v1/statistics/yearly-trends` | GET | Yearly trend data |

## Deployment

### Docker Compose
```bash
cd deploy
docker-compose up -d
```

**Services:**
- `postgres`: PostgreSQL 16 database
- `mongodb`: MongoDB 7 document store
- `redis`: Redis cache and message queue
- `ollama`: Local LLM server
- `scraper`: Web scraping service
- `api`: FastAPI REST API
- `worker`: Celery background tasks

### Environment Variables
```bash
POSTGRES_PASSWORD=your_secure_password
MONGO_PASSWORD=your_secure_password
LLM_PROVIDER=ollama
LLM_MODEL=llama3
OPENAI_API_KEY=sk-...  # Optional
ANTHROPIC_API_KEY=sk-ant-...  # Optional
```

## Use Cases

### 1. **Defendant Seeking Attorney**
"I'm charged with assault. Judge Smith and Prosecutor Jones are assigned. Which attorney should I hire?"

→ Use `/api/v1/recommendations` with judge_id, prosecutor_id, charge_type="VIOLENT"

### 2. **Attorney Evaluating Case**
"How difficult is this matchup? What's my expected win rate?"

→ Use `/api/v1/matchup` to get difficulty level and strategy suggestions

### 3. **Legal Researcher**
"What's Judge Smith's conviction rate for drug cases? How does it compare to other judges?"

→ Use `/api/v1/judges/{id}/performance` and compare metrics

### 4. **Public Defender Office**
"Which of our attorneys performs best against Prosecutor Jones?"

→ Use `/api/v1/attorneys/compare` with multiple attorney IDs

### 5. **Case Document Review**
"Analyze this sentencing entry and extract key details"

→ Use `/api/v1/documents/analyze` with PDF path

## Next Steps

1. **Data Migration**: Import existing JSON files into databases
2. **Analytics Calculation**: Run batch jobs to calculate all metrics
3. **LLM Setup**: Install Ollama and pull llama3 model
4. **API Testing**: Test endpoints with sample data
5. **Dashboard**: Build web UI for visualizations

## Performance Considerations

- **Caching**: Redis caches frequently accessed analytics
- **Batch Processing**: Celery workers handle heavy computations
- **Indexing**: Database indexes on judge_id, prosecutor_id, attorney_id
- **LLM Optimization**: Use local Ollama for cost-free inference
