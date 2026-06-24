from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from rolelens.models import JobRecord, JobStatus, ReviewRecord


@dataclass(frozen=True)
class JobDetection:
    job_id: str
    state: str
    content_hash: str


@dataclass(frozen=True)
class ScanResult:
    detections: list[JobDetection]

    def states_by_job_id(self) -> dict[str, str]:
        return {detection.job_id: detection.state for detection in self.detections}


@dataclass(frozen=True)
class ReviewMetadata:
    job_id: str
    reviewed_at: date
    last_reviewed_hash: str


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.ensure_schema()

    def close(self) -> None:
        self.connection.close()

    def ensure_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
              job_id TEXT PRIMARY KEY,
              payload TEXT NOT NULL,
              content_hash TEXT NOT NULL,
              first_seen TEXT NOT NULL,
              last_seen TEXT NOT NULL,
              status TEXT NOT NULL,
              prefilter_status TEXT NOT NULL,
              last_reviewed_hash TEXT
            );

            CREATE TABLE IF NOT EXISTS reviews (
              job_id TEXT PRIMARY KEY,
              payload TEXT NOT NULL,
              reviewed_at TEXT NOT NULL,
              last_reviewed_hash TEXT NOT NULL,
              FOREIGN KEY(job_id) REFERENCES jobs(job_id)
            );
            """
        )
        self.connection.commit()

    def sync_jobs(self, jobs: list[JobRecord], scan_date: date) -> ScanResult:
        seen_job_ids = {job.job_id for job in jobs}
        detections: list[JobDetection] = []

        for job in jobs:
            content_hash = job_content_hash(job)
            existing = self._get_job_row(job.job_id)
            if existing is None:
                self._insert_job(job, content_hash, scan_date)
                detections.append(
                    JobDetection(job.job_id, "new", content_hash)
                )
                continue

            if existing["content_hash"] != content_hash:
                self._update_job(
                    job=job,
                    content_hash=content_hash,
                    first_seen=date.fromisoformat(existing["first_seen"]),
                    last_seen=scan_date,
                    last_reviewed_hash=existing["last_reviewed_hash"],
                )
                detections.append(
                    JobDetection(job.job_id, "changed", content_hash)
                )
            else:
                self._update_job(
                    job=job,
                    content_hash=content_hash,
                    first_seen=date.fromisoformat(existing["first_seen"]),
                    last_seen=scan_date,
                    last_reviewed_hash=existing["last_reviewed_hash"],
                )
                detections.append(
                    JobDetection(job.job_id, "unchanged", content_hash)
                )

        for row in self.connection.execute(
            "SELECT job_id, content_hash FROM jobs WHERE status = ?",
            (JobStatus.ACTIVE.value,),
        ):
            if row["job_id"] not in seen_job_ids:
                self.connection.execute(
                    "UPDATE jobs SET status = ? WHERE job_id = ?",
                    (JobStatus.MISSING.value, row["job_id"]),
                )
                detections.append(
                    JobDetection(row["job_id"], "missing", row["content_hash"])
                )

        self.connection.commit()
        return ScanResult(detections)

    def import_review(self, review: ReviewRecord) -> ReviewMetadata:
        row = self._get_job_row(review.job_id)
        if row is None:
            raise ValueError(f"unknown job_id: {review.job_id}")

        last_reviewed_hash = row["content_hash"]
        payload = json.dumps(review.model_dump(mode="json"), sort_keys=True)
        self.connection.execute(
            """
            INSERT INTO reviews (job_id, payload, reviewed_at, last_reviewed_hash)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
              payload = excluded.payload,
              reviewed_at = excluded.reviewed_at,
              last_reviewed_hash = excluded.last_reviewed_hash
            """,
            (
                review.job_id,
                payload,
                review.reviewed_at.isoformat(),
                last_reviewed_hash,
            ),
        )
        self.connection.execute(
            "UPDATE jobs SET last_reviewed_hash = ? WHERE job_id = ?",
            (last_reviewed_hash, review.job_id),
        )
        self.connection.commit()
        return ReviewMetadata(
            job_id=review.job_id,
            reviewed_at=review.reviewed_at,
            last_reviewed_hash=last_reviewed_hash,
        )

    def load_review_metadata(self) -> dict[str, ReviewMetadata]:
        rows = self.connection.execute(
            "SELECT job_id, reviewed_at, last_reviewed_hash FROM reviews"
        )
        return {
            row["job_id"]: ReviewMetadata(
                job_id=row["job_id"],
                reviewed_at=date.fromisoformat(row["reviewed_at"]),
                last_reviewed_hash=row["last_reviewed_hash"],
            )
            for row in rows
        }

    def queue_state(self, job_id: str) -> str:
        row = self._get_job_row(job_id)
        if row is None:
            raise ValueError(f"unknown job_id: {job_id}")
        if row["status"] == JobStatus.MISSING.value:
            return "missing"
        if row["last_reviewed_hash"] is None:
            return "unreviewed"
        if row["last_reviewed_hash"] != row["content_hash"]:
            return "needs_rereview"
        return "reviewed"

    def load_jobs(self) -> list[JobRecord]:
        rows = self.connection.execute("SELECT payload FROM jobs ORDER BY job_id")
        return [
            JobRecord.model_validate(json.loads(row["payload"]))
            for row in rows
        ]

    def _get_job_row(self, job_id: str) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()

    def _insert_job(self, job: JobRecord, content_hash: str, scan_date: date) -> None:
        payload = _job_payload(job, JobStatus.ACTIVE)
        self.connection.execute(
            """
            INSERT INTO jobs (
              job_id, payload, content_hash, first_seen, last_seen, status,
              prefilter_status, last_reviewed_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                job.job_id,
                json.dumps(payload, sort_keys=True),
                content_hash,
                scan_date.isoformat(),
                scan_date.isoformat(),
                JobStatus.ACTIVE.value,
                job.prefilter_status.value,
            ),
        )

    def _update_job(
        self,
        job: JobRecord,
        content_hash: str,
        first_seen: date,
        last_seen: date,
        last_reviewed_hash: str | None,
    ) -> None:
        payload = _job_payload(job, JobStatus.ACTIVE)
        self.connection.execute(
            """
            UPDATE jobs
            SET payload = ?,
                content_hash = ?,
                first_seen = ?,
                last_seen = ?,
                status = ?,
                prefilter_status = ?,
                last_reviewed_hash = ?
            WHERE job_id = ?
            """,
            (
                json.dumps(payload, sort_keys=True),
                content_hash,
                first_seen.isoformat(),
                last_seen.isoformat(),
                JobStatus.ACTIVE.value,
                job.prefilter_status.value,
                last_reviewed_hash,
                job.job_id,
            ),
        )


def job_content_hash(job: JobRecord) -> str:
    payload = {
        "company": job.company,
        "title": job.title,
        "location": job.location,
        "region": job.region,
        "url": job.url,
        "source": job.source,
        "description": job.description,
    }
    normalized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _job_payload(job: JobRecord, status: JobStatus) -> dict[str, object]:
    payload = job.model_dump(mode="json")
    payload["status"] = status.value
    return payload
