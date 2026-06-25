from typer.testing import CliRunner

from rolelens.cli import app


def test_help_hides_export_review_queue() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "export-review-queue" not in result.output
    assert "update" in result.output
