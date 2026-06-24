import json
from pathlib import Path

from typer.testing import CliRunner

from rolelens.cli import app
from rolelens.reports import generate_personal_report


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
