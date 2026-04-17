#!/usr/bin/env python3
"""Generate case-grounded knowledge base drafts for attorney review."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from pathlib import Path
from statistics import median
import sys
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from database.models_postgres import ContentType
from database.session import SessionLocal, init_db
from scripts.query_jobs import build_latest_dataset
from services.knowledge_base import KnowledgeBaseService


AARON_BROCKLER_PROFILE = {
    "name": "Aaron Brockler",
    "role": "Managing Attorney",
    "location": "Cleveland, Ohio",
    "background": [
        "Former prosecutor in Summit County and Cuyahoga County",
        "Practicing criminal defense attorney",
        "Case Western Reserve University School of Law graduate",
        "Highest grade in trial tactics at Case Western Reserve School of Law",
    ],
    "practice_focus": ["criminal defense", "OVI/DUI defense", "traffic law"],
    "credibility_signals": ["former prosecutor", "trial tactics honors", "280+ Google reviews"],
    "source_url": "https://www.brocklerlaw.com/aaron-brockler",
}


def summarize_dataset() -> Dict[str, Any]:
    dataset = build_latest_dataset()
    if dataset.empty:
        return {
            "total_cases": 0,
            "top_crime_types": [],
            "median_case_duration": None,
            "top_judges": [],
        }

    crime_counts = Counter(
        str(value).upper()
        for value in dataset.get("primary_crime_type", [])
        if str(value).strip()
    )
    judge_counts = Counter(
        str(value).strip()
        for value in dataset.get("judge_name", [])
        if str(value).strip()
    )
    durations = [
        int(value)
        for value in dataset.get("days_to_disposition", [])
        if str(value).strip() not in {"", "nan", "None"}
    ]

    return {
        "total_cases": int(len(dataset)),
        "top_crime_types": [
            {"crime_type": crime_type, "cases": count}
            for crime_type, count in crime_counts.most_common(3)
        ],
        "median_case_duration": median(durations) if durations else None,
        "top_judges": [
            {"judge_name": judge_name, "cases": count}
            for judge_name, count in judge_counts.most_common(3)
        ],
    }


def build_seed_questions(dataset_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    top_types = dataset_summary.get("top_crime_types") or []
    top_crime_type = (top_types[0]["crime_type"].lower() if top_types else "criminal")
    second_crime_type = (top_types[1]["crime_type"].lower() if len(top_types) > 1 else "violent")
    third_crime_type = (top_types[2]["crime_type"].lower() if len(top_types) > 2 else "property")

    top_judges = dataset_summary.get("top_judges") or []
    top_judge_name = top_judges[0]["judge_name"] if top_judges else "assigned judge"
    second_judge_name = top_judges[1]["judge_name"] if len(top_judges) > 1 else "another judge in this court"

    median_duration = dataset_summary.get("median_case_duration")
    timing_text = (
        f"Recent cases in the dataset show a median disposition timeline of about {int(median_duration)} days."
        if median_duration is not None
        else "Use the current dataset to explain that timelines vary significantly by judge, prosecutor, and charge profile."
    )

    total_cases = int(dataset_summary.get("total_cases") or 0)
    size_text = f"Use the current dataset size ({total_cases} tracked cases) when framing confidence and limits." if total_cases else "Acknowledge that confidence depends on available case volume."

    return [
        {
            "title": "What should I expect after I am charged in Cuyahoga County?",
            "question": "What should I realistically expect after I am charged in Cuyahoga County criminal court?",
            "content_type": ContentType.GUIDE,
            "charge_type": None,
            "tags": ["expectations", "process", "criminal-defense"],
        },
        {
            "title": f"How does a former prosecutor approach a {top_crime_type} case?",
            "question": (
                f"How does a former prosecutor turned defense attorney evaluate a {top_crime_type} case in Cuyahoga County?"
            ),
            "content_type": ContentType.FAQ,
            "charge_type": top_crime_type.upper(),
            "tags": ["former-prosecutor", "strategy", top_crime_type],
        },
        {
            "title": "How long do criminal cases usually take?",
            "question": f"How long do Cuyahoga County criminal cases usually take, and what changes that timeline? {timing_text}",
            "content_type": ContentType.FAQ,
            "charge_type": None,
            "tags": ["timeline", "what-to-expect"],
        },
        {
            "title": "What changes when your attorney is a former prosecutor?",
            "question": "What practical advantage does a former prosecutor provide in plea strategy and trial preparation?",
            "content_type": ContentType.FAQ,
            "charge_type": None,
            "tags": ["former-prosecutor", "plea-negotiation", "trial-strategy"],
        },
        {
            "title": "How much does the assigned judge affect outcomes?",
            "question": f"How much can case trajectory vary between {top_judge_name} and {second_judge_name} in this court?",
            "content_type": ContentType.FAQ,
            "charge_type": None,
            "tags": ["judge-patterns", "outcomes", "courtroom-strategy"],
        },
        {
            "title": "When should someone negotiate early instead of waiting?",
            "question": "What case signals suggest negotiating early is better than delaying in Cuyahoga criminal cases?",
            "content_type": ContentType.GUIDE,
            "charge_type": None,
            "tags": ["plea-negotiation", "timing", "risk-management"],
        },
        {
            "title": "What should clients do before the first court date?",
            "question": "What are the highest-impact steps a client should take in the first 7 days after being charged?",
            "content_type": ContentType.GUIDE,
            "charge_type": None,
            "tags": ["first-appearance", "preparation", "checklist"],
        },
        {
            "title": "OVI/DUI cases: what outcomes are realistic?",
            "question": "For OVI/DUI defense in Cuyahoga County, what outcomes are realistic and what factors shift leverage?",
            "content_type": ContentType.FAQ,
            "charge_type": "OTHER",
            "tags": ["ovi", "dui", "traffic-law"],
        },
        {
            "title": "Traffic citations that can escalate",
            "question": "Which traffic-related charges tend to escalate into broader criminal exposure and how can that be contained early?",
            "content_type": ContentType.FAQ,
            "charge_type": "OTHER",
            "tags": ["traffic-law", "risk", "early-action"],
        },
        {
            "title": f"How to approach {second_crime_type} allegations",
            "question": f"What defense preparation priorities are most important in {second_crime_type} cases in this court?",
            "content_type": ContentType.GUIDE,
            "charge_type": second_crime_type.upper(),
            "tags": [second_crime_type, "case-prep", "defense-strategy"],
        },
        {
            "title": f"How to approach {third_crime_type} allegations",
            "question": f"What defense preparation priorities are most important in {third_crime_type} cases in this court?",
            "content_type": ContentType.GUIDE,
            "charge_type": third_crime_type.upper(),
            "tags": [third_crime_type, "case-prep", "defense-strategy"],
        },
        {
            "title": "How confidence should be interpreted in legal analytics",
            "question": f"How should a client interpret recommendation confidence and sample size limits? {size_text}",
            "content_type": ContentType.FAQ,
            "charge_type": None,
            "tags": ["analytics", "confidence", "transparency"],
        },
        {
            "title": "How prosecutors differ in negotiation posture",
            "question": "What prosecutor behavior patterns matter most when evaluating whether a plea offer is likely to improve?",
            "content_type": ContentType.FAQ,
            "charge_type": None,
            "tags": ["prosecutor-patterns", "plea-negotiation", "timing"],
        },
        {
            "title": "What a favorable outcome actually means",
            "question": "Beyond dismissal, what counts as a favorable criminal outcome and how should clients evaluate tradeoffs?",
            "content_type": ContentType.FAQ,
            "charge_type": None,
            "tags": ["outcomes", "decision-making", "client-education"],
        },
        {
            "title": "When trial may be worth the risk",
            "question": "In what case profiles might trial be worth the risk compared to a negotiated plea in Cuyahoga County?",
            "content_type": ContentType.GUIDE,
            "charge_type": None,
            "tags": ["trial", "risk-analysis", "plea-negotiation"],
        },
    ]


async def generate_batch(limit: int) -> List[str]:
    init_db()
    session = SessionLocal()
    try:
        service = KnowledgeBaseService(session)
        dataset_summary = summarize_dataset()
        seeds = build_seed_questions(dataset_summary)[:limit]
        created_slugs: List[str] = []
        for item in seeds:
            content = await service.generate_draft_answer(
                question=item["question"],
                title=item["title"],
                content_type=item["content_type"],
                charge_type=item["charge_type"],
                tags=item["tags"],
                citations=[AARON_BROCKLER_PROFILE["source_url"]],
                source_context={
                    "attorney_profile": AARON_BROCKLER_PROFILE,
                    "dataset_summary": dataset_summary,
                },
                source_metrics=dataset_summary,
            )
            created_slugs.append(content.slug)
        return created_slugs
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate case-grounded knowledge base drafts")
    parser.add_argument("--limit", type=int, default=15, help="Number of seed drafts to generate")
    args = parser.parse_args()

    slugs = asyncio.run(generate_batch(args.limit))
    for slug in slugs:
        print(slug)


if __name__ == "__main__":
    main()