import json
from pathlib import Path

from typer.testing import CliRunner

from rolelens.cli import app
from rolelens.models import JobRecord, PrefilterStatus, ReviewRecord
from rolelens.reports import generate_personal_report, generate_sqlite_report
from rolelens.storage import SQLiteStore


ROOT = Path(__file__).resolve().parents[1]
JOBS_PATH = ROOT / "data" / "sample_jobs.json"
REVIEWS_PATH = ROOT / "data" / "sample_reviews.json"


def write_imported_reviews(reviews_dir: Path) -> None:
    reviews = json.loads(REVIEWS_PATH.read_text(encoding="utf-8"))
    reviews_dir.mkdir()
    for review in reviews[:1]:
        (reviews_dir / f"{review['job_id']}.review.json").write_text(
            json.dumps(review),
            encoding="utf-8",
        )


def test_generate_personal_report_from_imported_reviews(tmp_path: Path) -> None:
    reviews_dir = tmp_path / "reviews"
    write_imported_reviews(reviews_dir)

    result = generate_personal_report(JOBS_PATH, reviews_dir, tmp_path / "reports")

    assert result.job_count == 6
    assert result.reviewed_count == 1
    markdown = result.markdown_path.read_text(encoding="utf-8")
    html = result.html_path.read_text(encoding="utf-8")
    assert "# RoleLens Report" in markdown
    assert "Reviewed jobs: 1" in markdown
    assert "Generated from local jobs and imported agent reviews." in html


def test_report_cli_generates_latest_reports(tmp_path: Path) -> None:
    reviews_dir = tmp_path / "reviews"
    write_imported_reviews(reviews_dir)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "report",
            "--jobs",
            str(JOBS_PATH),
            "--reviews-dir",
            str(reviews_dir),
            "--output-dir",
            str(tmp_path / "reports"),
        ],
    )

    assert result.exit_code == 0
    assert "Generated latest report (6 jobs, 1 reviewed)" in result.output
    assert (tmp_path / "reports" / "latest.md").exists()
    assert (tmp_path / "reports" / "latest.html").exists()


def test_generate_sqlite_report_from_store(tmp_path: Path) -> None:
    database_path = tmp_path / "rolelens.sqlite"
    store = SQLiteStore(database_path)
    try:
        job = JobRecord(
            job_id="backend-1",
            company="Example",
            title="Backend Software Engineer",
            location="Tokyo, Japan",
            region="Japan",
            url="https://example.com/backend-1",
            source="test",
            prefilter_status=PrefilterStatus.INCLUDE,
            status="active",
            first_seen="2026-06-24",
            last_seen="2026-06-24",
            description="Build product APIs.",
        )
        store.sync_jobs([job], job.first_seen)
        store.import_review(
            ReviewRecord(
                job_id="backend-1",
                reviewed_at="2026-06-25",
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
        )
    finally:
        store.close()

    result = generate_sqlite_report(database_path, tmp_path / "reports")

    assert result.job_count == 1
    assert result.reviewed_count == 1
    assert "Backend Software Engineer" in result.markdown_path.read_text(
        encoding="utf-8"
    )
