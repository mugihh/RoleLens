import json
from datetime import date
from pathlib import Path

import pytest

from rolelens.models import JobRecord, PrefilterStatus
from rolelens.reviews import import_reviews
from rolelens.storage import SQLiteStore


def write_jobs(path: Path) -> None:
    jobs = [
        JobRecord(
            job_id="backend-1",
            company="Example",
            title="Backend Software Engineer",
            location="Tokyo, Japan",
            region="Japan",
            url="https://example.com/backend-1",
            source="test",
            prefilter_status=PrefilterStatus.INCLUDE,
            status="active",
            first_seen=date(2026, 6, 24),
            last_seen=date(2026, 6, 24),
            description="Build product APIs.",
        ).model_dump(mode="json")
    ]
    path.write_text(json.dumps(jobs), encoding="utf-8")


def valid_review(job_id: str = "backend-1") -> dict[str, object]:
    return {
        "job_id": job_id,
        "reviewed_at": "2026-06-24",
        "category": "A",
        "fit_score": 84,
        "role_type": "Backend Engineer",
        "is_real_coding_role": True,
        "coding_intensity": "high",
        "customer_facing_level": "low",
        "reasons": ["Coding-heavy backend role"],
        "risks": [],
        "prep_actions": ["Prepare API design examples"],
        "dimensions": {
            "nlp_relevance": "low",
            "ml_relevance": "low",
            "english_friendliness": "unknown",
            "visa_or_pr_relevance": "unknown",
            "compensation_signal": "unknown",
        },
        "compensation_notes": "No salary research performed.",
        "external_research": [],
    }


def test_import_reviews_validates_and_persists_reviews(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs_raw.json"
    write_jobs(jobs_path)
    review_results_dir = tmp_path / "review_results"
    review_results_dir.mkdir()
    (review_results_dir / "backend-1.review.json").write_text(
        json.dumps(valid_review()),
        encoding="utf-8",
    )

    result = import_reviews(review_results_dir, jobs_path, tmp_path / "reviews")

    assert result.imported_count == 1
    assert result.skipped_count == 0
    persisted = json.loads(
        (tmp_path / "reviews" / "backend-1.review.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted["fit_score"] == 84


def test_import_reviews_updates_sqlite_review_metadata(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs_raw.json"
    write_jobs(jobs_path)
    database_path = tmp_path / "rolelens.sqlite"
    store = SQLiteStore(database_path)
    store.sync_jobs(
        [JobRecord.model_validate(json.loads(jobs_path.read_text())[0])],
        date(2026, 6, 24),
    )
    store.close()
    review_results_dir = tmp_path / "review_results"
    review_results_dir.mkdir()
    (review_results_dir / "backend-1.review.json").write_text(
        json.dumps(valid_review()),
        encoding="utf-8",
    )

    result = import_reviews(
        review_results_dir,
        jobs_path,
        tmp_path / "reviews",
        database_path=database_path,
    )

    store = SQLiteStore(database_path)
    try:
        assert result.imported_count == 1
        assert store.queue_state("backend-1") == "reviewed"
        assert store.load_review_metadata()["backend-1"].reviewed_at == date(2026, 6, 24)
    finally:
        store.close()


def test_import_reviews_warns_but_imports_consistency_issues(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs_raw.json"
    write_jobs(jobs_path)
    review_results_dir = tmp_path / "review_results"
    review_results_dir.mkdir()
    review = valid_review()
    review["category"] = "A"
    review["fit_score"] = 62
    (review_results_dir / "backend-1.review.json").write_text(
        json.dumps(review),
        encoding="utf-8",
    )

    result = import_reviews(review_results_dir, jobs_path, tmp_path / "reviews")

    assert result.imported_count == 1
    assert result.warning_count == 1
    assert "category A usually expects fit_score >= 70" in result.messages[0]


def test_import_reviews_skips_unknown_job_ids(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs_raw.json"
    write_jobs(jobs_path)
    review_results_dir = tmp_path / "review_results"
    review_results_dir.mkdir()
    (review_results_dir / "unknown.review.json").write_text(
        json.dumps(valid_review("unknown")),
        encoding="utf-8",
    )

    result = import_reviews(review_results_dir, jobs_path, tmp_path / "reviews")

    assert result.imported_count == 0
    assert result.skipped_count == 1
    assert "unknown job_id unknown" in result.messages[0]


def test_import_reviews_explains_missing_jobs_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Jobs file not found"):
        import_reviews(
            tmp_path / "review_results",
            tmp_path / "missing_jobs_raw.json",
            tmp_path / "reviews",
        )
