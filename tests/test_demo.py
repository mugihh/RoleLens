from pathlib import Path

from typer.testing import CliRunner

from rolelens.cli import app
from rolelens.reports import generate_demo_report


ROOT = Path(__file__).resolve().parents[1]
JOBS_PATH = ROOT / "data" / "sample_jobs.json"
REVIEWS_PATH = ROOT / "data" / "sample_reviews.json"


def test_generate_demo_report_writes_markdown_and_html(tmp_path: Path) -> None:
    result = generate_demo_report(JOBS_PATH, REVIEWS_PATH, tmp_path)

    assert result.job_count == 6
    assert result.reviewed_count == 3
    assert result.markdown_path.exists()
    assert result.html_path.exists()

    markdown = result.markdown_path.read_text(encoding="utf-8")
    html = result.html_path.read_text(encoding="utf-8")

    assert "Jobs loaded: 6" in markdown
    assert "Needs review: 1" in markdown
    assert "PayPay - Backend Software Engineer" in markdown
    assert "<title>RoleLens Demo Report</title>" in html


def test_demo_cli_generates_reports(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "demo",
            "--jobs",
            str(JOBS_PATH),
            "--reviews",
            str(REVIEWS_PATH),
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "Generated demo report (6 jobs, 3 reviewed)" in result.output
    assert (tmp_path / "demo.md").exists()
    assert (tmp_path / "demo.html").exists()
