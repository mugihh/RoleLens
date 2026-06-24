import json
from datetime import date
from pathlib import Path

from rolelens.models import JobRecord, PrefilterStatus
from rolelens.review_queue import export_review_queue


def job_payload(job_id: str, title: str, description: str) -> dict[str, object]:
    return JobRecord(
        job_id=job_id,
        company="Example",
        title=title,
        location="Tokyo, Japan",
        region="Japan",
        url=f"https://example.com/{job_id}",
        source="test",
        prefilter_status=PrefilterStatus.WATCH,
        status="active",
        first_seen=date(2026, 6, 24),
        last_seen=date(2026, 6, 24),
        description=description,
    ).model_dump(mode="json")


def test_export_review_queue_writes_job_json_and_prompt(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs_raw.json"
    jobs_path.write_text(
        json.dumps(
            [
                job_payload(
                    "backend-1",
                    "Backend Software Engineer",
                    "Build product APIs and distributed systems.",
                )
            ]
        ),
        encoding="utf-8",
    )

    result = export_review_queue(jobs_path, tmp_path / "review_queue")

    assert result.exported_count == 1
    assert result.skipped_count == 0
    job_json = tmp_path / "review_queue" / "backend-1.job.json"
    prompt_md = tmp_path / "review_queue" / "backend-1.prompt.md"
    assert job_json.exists()
    assert prompt_md.exists()
    assert json.loads(job_json.read_text(encoding="utf-8"))["prefilter_status"] == "include"
    assert "review_results/backend-1.review.json" in prompt_md.read_text(
        encoding="utf-8"
    )


def test_export_review_queue_skips_excluded_jobs(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs_raw.json"
    jobs_path.write_text(
        json.dumps(
            [
                job_payload(
                    "sales-1",
                    "Sales Engineer",
                    "Support account executives and customer sales motions.",
                )
            ]
        ),
        encoding="utf-8",
    )

    result = export_review_queue(jobs_path, tmp_path / "review_queue")

    assert result.exported_count == 0
    assert result.skipped_count == 1
    assert not (tmp_path / "review_queue" / "sales-1.job.json").exists()


def test_export_review_queue_marks_watch_prompts(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs_raw.json"
    jobs_path.write_text(
        json.dumps(
            [
                job_payload(
                    "fde-1",
                    "Forward Deployed AI Engineer",
                    "Prototype LLM systems with strategic customers.",
                )
            ]
        ),
        encoding="utf-8",
    )

    result = export_review_queue(jobs_path, tmp_path / "review_queue")

    assert result.exported_count == 1
    prompt = (tmp_path / "review_queue" / "fde-1.prompt.md").read_text(
        encoding="utf-8"
    )
    assert "## Prefilter Warning" in prompt
