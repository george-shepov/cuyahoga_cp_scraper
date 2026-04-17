import importlib.util
import json
from pathlib import Path


def import_query_jobs_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "scripts" / "query_jobs.py"
    spec = importlib.util.spec_from_file_location("query_jobs", str(module_path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_latest_dataset_uses_embedded_charge_table(monkeypatch, tmp_path):
    qj = import_query_jobs_module()

    repo_root = tmp_path
    out_dir = repo_root / "out" / "2023"
    out_dir.mkdir(parents=True)

    case_path = out_dir / "2023-685132_20251112_171855.json"
    case_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "year": 2023,
                    "number": 685132,
                    "exists": True,
                    "case_id": "CR-23-685132-A",
                    "scraped_at": "2025-11-12T17:18:55.652163+00:00",
                },
                "summary": {
                    "case_id": "CR-23-685132-A",
                    "fields": {
                        "Status:": "DEFN LVJAIL",
                        "Judge Name:": "HOLLIE L GALLAGHER",
                        "Name:": "TAYLOR THOMPSON",
                        "embedded_table_0": {
                            "format": "csv",
                            "data": "Type,Statute,Charge Description,Disposition\r\nINDICT,2925.03.A(1),TRAFFICKING OFFENSE,NOLLE"
                        },
                    },
                },
                "docket": [],
                "costs": [],
                "attorneys": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(qj, "REPO_ROOT", repo_root)
    monkeypatch.setattr(qj, "OUT_DIR", repo_root / "out")

    dataset = qj.build_latest_dataset()

    assert len(dataset) == 1
    row = dataset.iloc[0]
    assert row["primary_crime_type"] == "DRUG"
    assert row["crime_types"] == "DRUG"
    assert row["charge_count"] == 1


def test_build_latest_dataset_uses_docket_charge_language(monkeypatch, tmp_path):
    qj = import_query_jobs_module()

    repo_root = tmp_path
    out_dir = repo_root / "out" / "2023"
    out_dir.mkdir(parents=True)

    case_path = out_dir / "2023-681622_20251117_122709.json"
    case_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "year": 2023,
                    "number": 681622,
                    "exists": True,
                    "case_id": "CR-23-681622-A",
                    "scraped_at": "2025-11-17T12:27:09.254796+00:00",
                },
                "summary": {"case_id": None},
                "docket": [
                    {
                        "description": "DEFENDANT ENTERS A PLEA OF GUILTY TO CARRYING CONCEALED WEAPONS R.C. 2923.12 A(1) M1."
                    }
                ],
                "costs": [],
                "attorneys": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(qj, "REPO_ROOT", repo_root)
    monkeypatch.setattr(qj, "OUT_DIR", repo_root / "out")

    dataset = qj.build_latest_dataset()

    assert len(dataset) == 1
    row = dataset.iloc[0]
    assert row["primary_crime_type"] == "VIOLENT"
    assert row["crime_types"] == "VIOLENT"
    assert row["charge_count"] == 1


def test_build_latest_dataset_falls_back_to_other_when_no_signal(monkeypatch, tmp_path):
    qj = import_query_jobs_module()

    repo_root = tmp_path
    out_dir = repo_root / "out" / "2023"
    out_dir.mkdir(parents=True)

    case_path = out_dir / "2023-683207_20251118_125326.json"
    case_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "year": 2023,
                    "number": 683207,
                    "exists": True,
                    "case_id": "CR-23-683207-A",
                    "scraped_at": "2025-11-18T12:53:26.000000+00:00",
                },
                "summary": {"case_id": None},
                "docket": [],
                "costs": [],
                "attorneys": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(qj, "REPO_ROOT", repo_root)
    monkeypatch.setattr(qj, "OUT_DIR", repo_root / "out")

    dataset = qj.build_latest_dataset()

    assert len(dataset) == 1
    row = dataset.iloc[0]
    assert row["primary_crime_type"] == "OTHER"
    assert row["crime_types"] == "OTHER"
    assert row["charge_count"] == 0


def test_build_latest_dataset_prefers_specific_type_over_other(monkeypatch, tmp_path):
    qj = import_query_jobs_module()

    repo_root = tmp_path
    out_dir = repo_root / "out" / "2023"
    out_dir.mkdir(parents=True)

    case_path = out_dir / "2023-687626_20260417_010415.json"
    case_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "year": 2023,
                    "number": 687626,
                    "exists": True,
                    "case_id": "CR-23-687626-A",
                    "scraped_at": "2026-04-17T01:04:15.000000+00:00",
                },
                "summary": {
                    "case_id": "CR-23-687626-A",
                    "fields": {
                        "Status:": "CASE CLOSED",
                        "Judge Name:": "ANDREW J. SANTOLI",
                        "Name:": "ROBERT LEE GORDON",
                        "embedded_table_0": {
                            "format": "csv",
                            "data": "Type,Statute,Charge Description,Disposition\r\nINDICT,2919.25.A,DOMESTIC VIOLENCE (PC),DISM OTHER"
                        },
                    },
                },
                "docket": [
                    {"description": "REPARATION FEE RC 2937.22 $25"},
                    {"description": "DATE OF OFFENSE 12/10/2022"}
                ],
                "costs": [],
                "attorneys": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(qj, "REPO_ROOT", repo_root)
    monkeypatch.setattr(qj, "OUT_DIR", repo_root / "out")

    dataset = qj.build_latest_dataset()

    assert len(dataset) == 1
    row = dataset.iloc[0]
    assert row["primary_crime_type"] == "VIOLENT"
    assert row["crime_types"] == "VIOLENT"
    assert row["charge_count"] == 1


def test_build_latest_dataset_ignores_non_charge_docket_entries(monkeypatch, tmp_path):
    qj = import_query_jobs_module()

    repo_root = tmp_path
    out_dir = repo_root / "out" / "2023"
    out_dir.mkdir(parents=True)

    case_path = out_dir / "2023-677527_20260417_010527.json"
    case_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "year": 2023,
                    "number": 677527,
                    "exists": True,
                    "case_id": "CR-23-677527-A",
                    "scraped_at": "2026-04-17T01:05:27.000000+00:00",
                },
                "summary": {"case_id": "CR-23-677527-A"},
                "docket": [
                    {"description": "REPARATION FEE RC 2937.22 $25"},
                    {"description": "DATE OF OFFENSE 12/10/2022"},
                    {"description": "DEFENDANT ENTERS A PLEA OF GUILTY TO DISORDERLY CONDUCT R.C. 2917.11 A(5) M4."}
                ],
                "costs": [],
                "attorneys": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(qj, "REPO_ROOT", repo_root)
    monkeypatch.setattr(qj, "OUT_DIR", repo_root / "out")

    dataset = qj.build_latest_dataset()

    assert len(dataset) == 1
    row = dataset.iloc[0]
    assert row["crime_types"] == "OTHER"
    assert row["charge_count"] == 1