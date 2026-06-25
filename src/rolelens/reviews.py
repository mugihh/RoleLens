from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from rolelens.models import (
    JobRecord,
    ReviewRecord,
    review_consistency_warnings,
)
from rolelens.storage import SQLiteStore


@dataclass(frozen=True)
class ImportReviewsResult:
    output_dir: Path
    imported_count: int
    skipped_count: int
    warning_count: int
    messages: list[str]


def import_reviews(
    review_results_dir: Path,
    jobs_path: Path,
    output_dir: Path,
    database_path: Path | None = None,
) -> ImportReviewsResult:
    known_jobs = _load_known_jobs(jobs_path)
    known_job_ids = {job.job_id for job in known_jobs}
    output_dir.mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(database_path) if database_path is not None else None
    if store is not None:
        store.sync_jobs(known_jobs, date.today())

    imported_count = 0
    skipped_count = 0
    warning_count = 0
    messages: list[str] = []

    try:
        for path in sorted(review_results_dir.glob("*.review.json")):
            try:
                review = _load_review(path)
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                skipped_count += 1
                messages.append(f"SKIP {path}: {exc}")
                continue

            if review.job_id not in known_job_ids:
                skipped_count += 1
                messages.append(f"SKIP {path}: unknown job_id {review.job_id}")
                continue

            warnings = review_consistency_warnings(review)
            for warning in warnings:
                warning_count += 1
                messages.append(f"WARN {review.job_id}: {warning}")

            output_path = output_dir / f"{review.job_id}.review.json"
            output_path.write_text(
                json.dumps(
                    review.model_dump(mode="json"),
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            if store is not None:
                store.import_review(review)
                messages.append(f"SQLITE {review.job_id}: {database_path}")
            imported_count += 1
            messages.append(f"IMPORT {review.job_id}: {output_path}")
    finally:
        if store is not None:
            store.close()

    return ImportReviewsResult(
        output_dir=output_dir,
        imported_count=imported_count,
        skipped_count=skipped_count,
        warning_count=warning_count,
        messages=messages,
    )


def _load_known_jobs(path: Path) -> list[JobRecord]:
    if not path.exists():
        raise ValueError(
            f"Jobs file not found: {path}. "
            "Run `rolelens import-manual imports/manual/` first, "
            "or pass `--jobs data/sample_jobs.json` for demo/sample reviews."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return [JobRecord.model_validate(item) for item in data]


def _load_review(path: Path) -> ReviewRecord:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("review result must be a JSON object")
    return ReviewRecord.model_validate(data)
