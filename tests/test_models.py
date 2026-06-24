import pytest
from pydantic import ValidationError

from rolelens.models import (
    JobRecord,
    ReviewRecord,
    review_consistency_warnings,
    validate_reviews_reference_known_jobs,
)


def valid_job() -> dict[str, object]:
    return {
        "job_id": "mercari-ml-platform-001",
        "company": "Mercari",
        "title": "Machine Learning Engineer",
        "location": "Tokyo, Japan",
        "region": "Japan",
        "url": "https://example.com/job",
        "source": "demo",
        "prefilter_status": "include",
        "status": "active",
        "first_seen": "2026-06-21",
        "last_seen": "2026-06-21",
        "description": "Build production ML systems.",
    }


def valid_review() -> dict[str, object]:
    return {
        "job_id": "mercari-ml-platform-001",
        "reviewed_at": "2026-06-21",
        "category": "A",
        "fit_score": 88,
        "role_type": "Product ML Engineer",
        "is_real_coding_role": True,
        "coding_intensity": "high",
        "customer_facing_level": "low",
        "reasons": ["Production ML role"],
        "risks": ["May require deployment depth"],
        "prep_actions": ["Prepare ML deployment examples"],
        "dimensions": {"ml_relevance": "high"},
        "compensation_notes": "Demo signal only.",
        "external_research": [],
    }


def test_job_record_accepts_supported_prefilter_statuses() -> None:
    job = JobRecord.model_validate(valid_job())

    assert job.prefilter_status == "include"
    assert job.status == "active"


def test_job_record_rejects_unknown_prefilter_status() -> None:
    payload = valid_job()
    payload["prefilter_status"] = "maybe"

    with pytest.raises(ValidationError):
        JobRecord.model_validate(payload)


def test_review_record_validates_score_range() -> None:
    payload = valid_review()
    payload["fit_score"] = 101

    with pytest.raises(ValidationError):
        ReviewRecord.model_validate(payload)


def test_review_consistency_warnings_flag_mismatched_category_and_score() -> None:
    payload = valid_review()
    payload["category"] = "A"
    payload["fit_score"] = 62
    review = ReviewRecord.model_validate(payload)

    assert review_consistency_warnings(review) == [
        "category A usually expects fit_score >= 70"
    ]


def test_review_consistency_warnings_flag_non_coding_a_role() -> None:
    payload = valid_review()
    payload["is_real_coding_role"] = False
    review = ReviewRecord.model_validate(payload)

    assert review_consistency_warnings(review) == [
        "category A usually requires is_real_coding_role = true"
    ]


def test_validate_reviews_reference_known_jobs_warns_on_unknown_job_id() -> None:
    job = JobRecord.model_validate(valid_job())
    payload = valid_review()
    payload["job_id"] = "unknown-job"
    review = ReviewRecord.model_validate(payload)

    assert validate_reviews_reference_known_jobs([job], [review]) == [
        "review references unknown job_id: unknown-job"
    ]
