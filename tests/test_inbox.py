import json
from datetime import date
from pathlib import Path

from rolelens.inbox import generate_inbox
from rolelens.models import JobRecord, PrefilterStatus


def job_payload(
    job_id: str,
    title: str,
    description: str = "Build software.",
    *,
    company: str = "Example",
    region: str = "Japan",
    source: str = "test",
) -> dict[str, object]:
    return JobRecord(
        job_id=job_id,
        company=company,
        title=title,
        location=f"{region} office",
        region=region,
        url=f"https://example.com/{job_id}",
        source=source,
        prefilter_status=PrefilterStatus.WATCH,
        status="active",
        first_seen=date(2026, 6, 25),
        last_seen=date(2026, 6, 25),
        description=description,
    ).model_dump(mode="json")


def _write_profile(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """region_preferences:
  Japan: primary
  Singapore: only_for_large_company_or_high_compensation
target_regions:
  - Japan
  - Singapore
work_authorization:
  minimum_japan_compensation_jpy: 5000000
large_companies:
  - BigCo
""",
        encoding="utf-8",
    )


def _run(tmp_path: Path, jobs: list[dict[str, object]], **kwargs):
    jobs_path = tmp_path / "jobs_raw.json"
    jobs_path.write_text(json.dumps(jobs), encoding="utf-8")
    profile_path = tmp_path / "candidate" / "profile.yaml"
    _write_profile(profile_path)
    return generate_inbox(
        jobs_path=jobs_path,
        profile_path=profile_path,
        review_results_dir=tmp_path / "review_results",
        output_path=tmp_path / "reports" / "inbox.md",
        json_path=tmp_path / "data" / "inbox.json",
        **kwargs,
    )


def test_inbox_ranks_target_role_above_customer_facing(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        [
            job_payload(
                "ml-1", "Machine Learning Engineer, New Grad", company="AlphaCo"
            ),
            job_payload(
                "sales-1",
                "Sales Engineer",
                "Support customers and pre-sales.",
                company="BetaCo",
            ),
        ],
        inbox_size=5,
    )
    data = json.loads((tmp_path / "data" / "inbox.json").read_text())
    assert result.inbox_count == 2
    # The new-grad ML role must rank first; the sales role last.
    assert data["inbox"][0]["job_id"] == "ml-1"
    assert data["inbox"][-1]["job_id"] == "sales-1"
    assert data["inbox"][0]["score"] > data["inbox"][-1]["score"]


def test_inbox_excludes_reviewed_jobs(tmp_path: Path) -> None:
    jobs_path = tmp_path / "jobs_raw.json"
    jobs_path.write_text(
        json.dumps([job_payload("ml-1", "ML Engineer")]), encoding="utf-8"
    )
    profile_path = tmp_path / "candidate" / "profile.yaml"
    _write_profile(profile_path)
    reviews_dir = tmp_path / "review_results"
    reviews_dir.mkdir()
    (reviews_dir / "ml-1.review.json").write_text("{}", encoding="utf-8")

    result = generate_inbox(
        jobs_path=jobs_path,
        profile_path=profile_path,
        review_results_dir=reviews_dir,
        output_path=tmp_path / "reports" / "inbox.md",
        json_path=tmp_path / "data" / "inbox.json",
    )
    assert result.inbox_count == 0


def test_inbox_caps_one_per_company_in_top_picks(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        [
            job_payload("a", "Machine Learning Engineer", company="BigCo"),
            job_payload("b", "NLP Engineer", company="BigCo"),
            job_payload("c", "Data Engineer", company="OtherCo"),
        ],
        inbox_size=5,
    )
    data = json.loads((tmp_path / "data" / "inbox.json").read_text())
    top_companies = [item["company"] for item in data["inbox"]]
    # BigCo appears at most once in the Top picks (one-per-company cap).
    assert top_companies.count("BigCo") == 1


def test_inbox_dedupes_near_identical_titles(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        [
            job_payload("a", "Machine Learning Engineer", company="BigCo"),
            job_payload("b", "Machine Learning Engineer", company="BigCo"),
        ],
    )
    # Same company + near-identical title collapses to a single entry.
    assert result.inbox_count == 1
