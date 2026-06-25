import json
from datetime import date
from pathlib import Path

from rolelens.models import JobRecord, PrefilterStatus
from rolelens.triage import generate_review_plan


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
        first_seen=date(2026, 6, 25),
        last_seen=date(2026, 6, 25),
        description=description,
    ).model_dump(mode="json")


def test_generate_review_plan_uses_profile_targets_and_avoids(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs_raw.json"
    profile_path = tmp_path / "candidate" / "profile.yaml"
    output_path = tmp_path / "reports" / "review_plan.md"
    profile_path.parent.mkdir()
    profile_path.write_text(
        """target_roles:
  - Machine Learning Engineer
roles_to_avoid:
  - Sales Engineer
""",
        encoding="utf-8",
    )
    jobs_path.write_text(
        json.dumps(
            [
                job_payload(
                    "ml-1",
                    "Machine Learning Engineer",
                    "Build model evaluation pipelines.",
                ),
                job_payload(
                    "sales-1",
                    "Sales Engineer",
                    "Support sales teams.",
                ),
            ]
        ),
        encoding="utf-8",
    )

    result = generate_review_plan(
        jobs_path=jobs_path,
        profile_path=profile_path,
        review_results_dir=tmp_path / "review_results",
        output_path=output_path,
    )

    text = output_path.read_text(encoding="utf-8")
    assert result.likely_count == 1
    assert result.skip_count == 1
    assert "Matches profile target_roles: Machine Learning Engineer" in text
    assert "Title matches profile roles_to_avoid: Sales Engineer" in text


def test_generate_review_plan_tracks_already_reviewed_jobs(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs_raw.json"
    reviews_dir = tmp_path / "review_results"
    output_path = tmp_path / "reports" / "review_plan.md"
    reviews_dir.mkdir()
    jobs_path.write_text(
        json.dumps(
            [
                job_payload(
                    "backend-1",
                    "Backend Software Engineer",
                    "Build APIs and services.",
                )
            ]
        ),
        encoding="utf-8",
    )
    (reviews_dir / "backend-1.review.json").write_text("{}", encoding="utf-8")

    result = generate_review_plan(
        jobs_path=jobs_path,
        profile_path=None,
        review_results_dir=reviews_dir,
        output_path=output_path,
    )

    assert result.already_reviewed_count == 1
    assert "Already reviewed" in output_path.read_text(encoding="utf-8")
