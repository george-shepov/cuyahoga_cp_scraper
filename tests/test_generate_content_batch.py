from scripts.generate_content_batch import RECOMMENDED_FIRST_BATCH, build_seed_questions


def test_build_seed_questions_starts_with_recommended_first_batch():
    dataset_summary = {
        "total_cases": 250,
        "top_crime_types": [
            {"crime_type": "DRUG", "cases": 90},
            {"crime_type": "VIOLENT", "cases": 70},
            {"crime_type": "PROPERTY", "cases": 50},
        ],
    }

    seeds = build_seed_questions(dataset_summary)

    assert len(seeds) > len(RECOMMENDED_FIRST_BATCH)
    assert seeds[: len(RECOMMENDED_FIRST_BATCH)] == RECOMMENDED_FIRST_BATCH
