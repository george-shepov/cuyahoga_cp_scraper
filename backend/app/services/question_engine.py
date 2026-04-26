from __future__ import annotations

from typing import Iterable


def generate_questions(charge_codes: Iterable[str], facts: dict) -> list[str]:
    joined = " ".join(charge_codes)
    questions: list[str] = []

    if "4511.19" in joined:
        questions.extend(
            [
                "Was a chemical test requested?",
                "Was the test refused, failed, or still pending?",
                "Is this the first OVI within 10 years?",
                "Do you have any ALS or immediate suspension paperwork?",
                "Was there an accident, child passenger, or elevated test result?",
            ]
        )

    if "4511.33" in joined:
        questions.append("Was the stop based on marked lanes or another lane allegation?")

    if "4511.21" in joined:
        questions.append("Was speeding part of the stop?")

    if facts.get("cdl"):
        questions.append("Do you hold a CDL or drive for work?")

    if facts.get("chemical_test") == "refused":
        questions.append("What exactly did the officer say before the refusal was recorded?")

    # Stable order + dedupe
    return list(dict.fromkeys(questions))
