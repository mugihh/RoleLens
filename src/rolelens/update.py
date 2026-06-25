from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from rolelens.manual_import import import_manual_jobs
from rolelens.models import JobRecord
from rolelens.reports import ReportResult, generate_latest_report_from_records
from rolelens.review_queue import ReviewQueueResult, export_review_queue_for_jobs
from rolelens.scrapers import FetchJson, scan_configured_sources
from rolelens.storage import SQLiteStore


@dataclass(frozen=True)
class UpdateResult:
    imported_jobs_path: Path
    database_path: Path
    scan_states: dict[str, str]
    queue_result: ReviewQueueResult
    report_result: ReportResult
    messages: list[str]


def run_update(
    imports_dir: Path,
    jobs_path: Path,
    database_path: Path,
    review_queue_dir: Path,
    reports_dir: Path,
    sources_path: Path | None = None,
    fetch_json: FetchJson | None = None,
    scan_date: date | None = None,
) -> UpdateResult:
    scan_date = scan_date or date.today()
    import_result = import_manual_jobs(imports_dir, jobs_path, today=scan_date)
    manual_jobs = _load_jobs_from_import(import_result.output_path)
    messages = list(import_result.messages)

    scraped_jobs: list[JobRecord] = []
    if sources_path is not None:
        source_result = scan_configured_sources(sources_path, scan_date, fetch_json)
        scraped_jobs = source_result.jobs
        messages.extend(source_result.messages)

    jobs = _normalize_prefilter_statuses([*manual_jobs, *scraped_jobs])
    _write_jobs(import_result.output_path, jobs)

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
        messages=messages,
    )


def _load_jobs_from_import(path: Path) -> list[JobRecord]:
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return [JobRecord.model_validate(item) for item in data]


def _write_jobs(path: Path, jobs: list[JobRecord]) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [job.model_dump(mode="json") for job in jobs],
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _normalize_prefilter_statuses(jobs: list[JobRecord]) -> list[JobRecord]:
    from rolelens.filters import prefilter_job

    return [
        job.model_copy(update={"prefilter_status": prefilter_job(job).status})
        for job in jobs
    ]


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
