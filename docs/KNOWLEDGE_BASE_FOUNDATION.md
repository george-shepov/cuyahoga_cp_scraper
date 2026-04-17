# Knowledge Base Foundation

## Goal

Build a backend knowledge layer that answers real criminal-case questions using existing analytics, recommendation scores, and attorney-reviewed AI drafts. Phase 1 is intentionally backend-only: it creates the data model, review workflow, explanation service, and API endpoints that a future website or publishing workflow can consume.

## Why This Exists

Most law firm websites are brochure sites. This project already has a stronger foundation than a brochure site because it can combine:

- historical case analytics
- matchup-aware attorney recommendations
- structured case and actor performance data
- LLM-assisted draft generation

The missing layer is a way to turn that data into answers people actually search for, while keeping legal accuracy under attorney control.

## Phase 1 Scope

Phase 1 includes:

- a reviewed content model for FAQs, guides, and profile summaries
- structured recommendation explanations tied to existing scoring factors
- AI draft generation with mandatory attorney review before approval
- internal API endpoints for listing approved content and generating drafts
- API support for explanation payloads on recommendation results

Phase 1 excludes:

- a public website or CMS
- autonomous publishing
- SEO dashboards and ranking analytics
- a custom editorial UI

## Content Types

Initial content types:

- `FAQ`: direct answers to common criminal-case questions
- `GUIDE`: what-to-expect and process-focused guidance
- `JUDGE_PROFILE`: reviewed summaries of judge tendencies backed by aggregate analytics
- `PROSECUTOR_PROFILE`: reviewed summaries of prosecutor patterns backed by aggregate analytics
- `RECOMMENDATION_EXPLANATION`: structured narrative for why a given attorney is recommended for a matchup

## Review Workflow

Every generated answer moves through these states:

1. `DRAFT`: AI-generated or manually created content, not user-facing
2. `UNDER_REVIEW`: attorney is reviewing for accuracy and tone
3. `APPROVED`: cleared for API exposure or later publishing
4. `ARCHIVED`: superseded or no longer valid

Stored metadata must include:

- prompt version
- model/provider used for draft generation
- source metrics and citations
- reviewer name
- review timestamp
- approval timestamp

Unapproved content must never appear in public-facing read endpoints.

## Architecture

### Existing Inputs

- recommendation scoring from `services/attorney_recommender.py`
- analytics from `services/analytics_calculator.py`
- LLM provider abstraction from `services/llm_service.py`
- FastAPI transport from `api/main.py`

### New Foundation

- content persistence model for draft and approved answers
- knowledge base service for creating, reviewing, and retrieving content
- explanation builder that converts recommendation factors into defensible prose
- internal endpoints for draft generation and approved content retrieval

## Implementation Decisions

Phase 1 uses a relational content table in the existing SQLAlchemy model layer because the repo does not currently ship a working MongoDB client or PostgreSQL session module. The implementation therefore adds a minimal session helper with an environment-configurable SQLAlchemy engine and a SQLite fallback for local development and tests.

This is a pragmatic delivery choice, not a claim that SQLite is the long-term production target.

## API Surface

Planned endpoints in phase 1:

- `POST /api/v1/recommendations` returns recommendations with explanation previews
- `POST /api/v1/recommendations/explain` returns a focused explanation for one attorney/matchup
- `GET /api/v1/content` lists approved content with optional filters
- `GET /api/v1/content/{slug}` fetches one approved content item
- `POST /api/v1/content/drafts` creates a review-required draft
- `POST /api/v1/content/drafts/generate` generates a draft answer from a question and source context

## Initial Seed Questions

Recommended first batch:

- What should I expect at my first felony court date in Cuyahoga County?
- How much does the assigned judge affect the likely outcome?
- When does it make sense to fight the case versus negotiate early?
- What can a defense lawyer realistically change in a case like this?
- How do prosecutors differ in plea posture and trial pressure?
- What does a favorable outcome actually look like in this court?
- How long do criminal cases like this usually take?
- What should I do before talking to the prosecutor or appearing in court?
- How should I think about hiring a lawyer for this specific judge and prosecutor?
- What warning signs suggest a case may get more serious over time?

## Verification

Implementation is complete for phase 1 only when:

1. approved content can be stored and retrieved through the API
2. unapproved drafts are blocked from approved-content endpoints
3. recommendation responses expose explanation factors tied to the live scoring logic
4. draft generation records source context and review metadata
5. tests cover review-state enforcement and explanation payload structure

## Email Review Routing

The review workflow can run as a staged email sequence:

1. `submit` sends the draft to Sonia for first review.
2. Sonia `approve` sends the draft to Aaron for final approval.
3. Aaron `approve` sets content status to `APPROVED`.

Environment variables:

- `REVIEW_SONIA_NAME` (default: `Sonia`)
- `REVIEW_SONIA_EMAIL`
- `REVIEW_AARON_NAME` (default: `Aaron`)
- `REVIEW_AARON_EMAIL`

SMTP configuration (optional):

- `SMTP_HOST`
- `SMTP_PORT` (default: `587`)
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SMTP_USE_TLS` (default: `true`)

If SMTP is not configured, review messages are written to `logs/review_email_outbox.log` so the workflow can still be audited and tested.
