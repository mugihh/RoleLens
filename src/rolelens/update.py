from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from rolelens.manual_import import import_manual_jobs
from rolelens.models import JobRecord
from rolelens.reports import ReportResult, generate_latest_report_from_records
from rolelens.review_queue import ReviewQueueResult, export_review_queue_for_jobs
from rolelens.storage import SQLiteStore


@dataclass(frozen=True)
class UpdateResult:
    imported_jobs_path: Path
    database_path: Path
    scan_states: dict[str, str]
    queue_result: ReviewQueueResult
    report_result: ReportResult


def run_update(
    imports_dir: Path,
    jobs_path: Path,
    database_path: Path,
    review_queue_dir: Path,
    reports_dir: Path,
    scan_date: date | None = None,
) -> UpdateResult:
    scan_date = scan_date or date.today()
    import_result = import_manual_jobs(imports_dir, jobs_path, today=scan_date)
    jobs = _load_jobs_from_import(import_result.output_path)

    store = SQLiteStore(database_path)
    try:
        scan_result = store.sync_jobs(jobs, scan_date)
        stored_jobs = store.load_jobs()
        queue_states = _queue_states_for_jobs(store, stored_jobs, scan_result.states_by_job_id())
        queue_result = export_review_queue_for_jobs(
            stored_jobs,
            review_queue_dir,
            queue_states=queue_states,
        )
        reviews_by_job_id = {
            review.job_id: review.model_dump(mode="json")
            for review in store.load_reviews()
        }
        report_result = generate_latest_report_from_records(
            [job.model_dump(mode="json") for job in stored_jobs],
            reviews_by_job_id,
            reports_dir,
        )
    finally:
        store.close()

    return UpdateResult(
        imported_jobs_path=import_result.output_path,
        database_path=database_path,
        scan_states=scan_result.states_by_job_id(),
        queue_result=queue_result,
        report_result=report_result,
    )


def _load_jobs_from_import(path: Path) -> list[JobRecord]:
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return [JobRecord.model_validate(item) for item in data]


def _queue_states_for_jobs(
    store: SQLiteStore,
    jobs: list[JobRecord],
    scan_states: dict[str, str],
) -> dict[str, str]:
    states: dict[str, str] = {}
    for job in jobs:
        scan_state = scan_states.get(job.job_id)
        if scan_state in {"new", "changed", "missing"}:
            states[job.job_id] = scan_state
        else:
            states[job.job_id] = store.queue_state(job.job_id)
    return states
