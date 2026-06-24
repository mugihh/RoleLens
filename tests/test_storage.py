from datetime import date
from pathlib import Path

import pytest

from rolelens.models import JobRecord, PrefilterStatus, ReviewRecord
from rolelens.storage import SQLiteStore


def make_job(
    job_id: str = "backend-1",
    description: str = "Build backend product APIs.",
) -> JobRecord:
    return JobRecord(
        job_id=job_id,
        company="Example",
        title="Backend Software Engineer",
        location="Tokyo, Japan",
        region="Japan",
        url=f"https://example.com/{job_id}",
        source="test",
        prefilter_status=PrefilterStatus.INCLUDE,
        status="active",
        first_seen=date(2026, 6, 24),
        last_seen=date(2026, 6, 24),
        description=description,
    )


def make_review(job_id: str = "backend-1") -> ReviewRecord:
    return ReviewRecord(
        job_id=job_id,
        reviewed_at=date(2026, 6, 25),
        category="A",
        fit_score=84,
        role_type="Backend Engineer",
        is_real_coding_role=True,
        coding_intensity="high",
        customer_facing_level="low",
        reasons=["Coding-heavy backend role"],
        risks=[],
        prep_actions=["Prepare API design examples"],
        dimensions={},
        compensation_notes="No salary research performed.",
        external_research=[],
    )


def open_store(tmp_path: Path) -> SQLiteStore:
    return SQLiteStore(tmp_path / "rolelens.sqlite")


def test_sync_jobs_detects_new_jobs(tmp_path: Path) -> None:
    store = open_store(tmp_path)

    result = store.sync_jobs([make_job()], date(2026, 6, 24))

    assert result.states_by_job_id() == {"backend-1": "new"}
    assert store.queue_state("backend-1") == "unreviewed"


def test_sync_jobs_detects_changed_jobs(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    store.sync_jobs([make_job()], date(2026, 6, 24))

    result = store.sync_jobs(
        [make_job(description="Build backend APIs and data pipelines.")],
        date(2026, 6, 25),
    )

    assert result.states_by_job_id()["backend-1"] == "changed"


def test_sync_jobs_detects_missing_jobs(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    store.sync_jobs([make_job()], date(2026, 6, 24))

    result = store.sync_jobs([], date(2026, 6, 25))

    assert result.states_by_job_id() == {"backend-1": "missing"}
    assert store.queue_state("backend-1") == "missing"


def test_import_review_marks_job_reviewed(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    store.sync_jobs([make_job()], date(2026, 6, 24))

    metadata = store.import_review(make_review())

    assert metadata.job_id == "backend-1"
    assert store.queue_state("backend-1") == "reviewed"
    assert store.load_review_metadata()["backend-1"].reviewed_at == date(2026, 6, 25)


def test_changed_reviewed_job_needs_rereview(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    store.sync_jobs([make_job()], date(2026, 6, 24))
    store.import_review(make_review())

    store.sync_jobs(
        [make_job(description="Build backend APIs and data pipelines.")],
        date(2026, 6, 25),
    )

    assert store.queue_state("backend-1") == "needs_rereview"


def test_import_review_rejects_unknown_job_id(tmp_path: Path) -> None:
    store = open_store(tmp_path)

    with pytest.raises(ValueError, match="unknown job_id"):
        store.import_review(make_review())
