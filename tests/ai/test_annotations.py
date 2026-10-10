from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from pipeline.ai.annotations import AnnotationError, prepare_annotations, validate_annotations
from pipeline.config import Settings


def _write_test_sources(root: Path) -> Settings:
    raw_dir = root / "data" / "raw"
    raw_dir.mkdir(parents=True)
    records = [
        {
            "doc_id": f"{doc_type}-{index}",
            "doc_type": doc_type,
            "text": f"{doc_type} note for Test Project (B2100): SUB-001 estimates $100.",
        }
        for doc_type in ("RFI", "CO", "LOG")
        for index in (1, 2)
    ]
    correspondence = "".join(json.dumps(record) + "\n" for record in records)
    (raw_dir / "project_correspondence.jsonl").write_text(correspondence, encoding="utf-8")

    with (raw_dir / "jobs_reference.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=(
                "job_id",
                "division",
                "contract_type",
                "original_budget",
                "start_date",
                "planned_days",
                "pct_complete",
                "pm",
            ),
        )
        writer.writeheader()
        writer.writerow(
            {
                "job_id": "B-2100",
                "division": "Building",
                "contract_type": "Lump Sum",
            }
        )

    with (raw_dir / "job_cost_ledger.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=("subcontractor",))
        writer.writeheader()
        writer.writerow({"subcontractor": "Sub-001"})
    return Settings.from_root(root)


def test_prepare_annotations_is_balanced_and_protects_existing_labels(tmp_path: Path) -> None:
    settings = _write_test_sources(tmp_path)
    paths = prepare_annotations(settings, per_type=1, seed=7)

    sample = [json.loads(line) for line in paths.sample.read_text(encoding="utf-8").splitlines()]
    assert len(sample) == 3
    assert {record["doc_type"] for record in sample} == {"RFI", "CO", "LOG"}

    initial = validate_annotations(settings)
    assert initial.sampled_count == 3
    assert initial.todo_count == 3
    assert initial.issues == ()

    with pytest.raises(AnnotationError, match="refusing to overwrite"):
        prepare_annotations(settings, per_type=1, seed=7)


def test_validation_accepts_grounded_event_and_rejects_bad_evidence(tmp_path: Path) -> None:
    settings = _write_test_sources(tmp_path)
    paths = prepare_annotations(settings, per_type=1, seed=7)
    labels = [json.loads(line) for line in paths.labels.read_text(encoding="utf-8").splitlines()]
    labels[0]["review_status"] = "complete"
    labels[0]["events"] = [
        {
            "event_index": 1,
            "job_reference": "Test Project",
            "job_id": "B2100",
            "subcontractor_reference": "SUB-001",
            "subcontractor_id": "SUB001",
            "scope": None,
            "event_type": "potential_cost",
            "amount": 100,
            "financial_impact_type": "cost",
            "amount_status": "estimated",
            "booking_status": "unknown",
            "schedule_impact_days": None,
            "schedule_impact_type": "none",
            "approval_status": "unknown",
            "referenced_date": None,
            "date_context": None,
            "evidence_text": "SUB-001 estimates $100",
        }
    ]
    paths.labels.write_text(
        "".join(json.dumps(record) + "\n" for record in labels),
        encoding="utf-8",
    )

    valid = validate_annotations(settings)
    assert valid.complete_count == 1
    assert valid.event_count == 1
    assert valid.issues == ()

    labels[0]["events"][0]["evidence_text"] = "invented evidence"
    paths.labels.write_text(
        "".join(json.dumps(record) + "\n" for record in labels),
        encoding="utf-8",
    )
    invalid = validate_annotations(settings)
    assert any(issue.path.endswith("evidence_text") for issue in invalid.issues)
