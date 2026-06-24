from pathlib import Path

import typer

from rolelens.manual_import import import_manual_jobs
from rolelens.reports import generate_demo_report
from rolelens.review_queue import export_review_queue
from rolelens.setup_check import run_setup_check

app = typer.Typer(
    help="RoleLens: a local-first, agent-assisted job radar for technical roles."
)


@app.callback()
def main() -> None:
    """RoleLens command line interface."""


@app.command()
def demo(
    jobs_path: Path = typer.Option(
        Path("data/sample_jobs.json"),
        "--jobs",
        help="Path to demo job records.",
    ),
    reviews_path: Path = typer.Option(
        Path("data/sample_reviews.json"),
        "--reviews",
        help="Path to demo review records.",
    ),
    output_dir: Path = typer.Option(
        Path("reports"),
        "--output-dir",
        "-o",
        help="Directory where demo artifacts will be written.",
    ),
) -> None:
    """Generate demo reports from sample data."""
    result = generate_demo_report(jobs_path, reviews_path, output_dir)
    typer.echo(
        "Generated demo report "
        f"({result.job_count} jobs, {result.reviewed_count} reviewed):"
    )
    typer.echo(f"- {result.markdown_path}")
    typer.echo(f"- {result.html_path}")


@app.command("setup-check")
def setup_check(
    root: Path = typer.Option(
        Path("."),
        "--root",
        help="RoleLens project root to validate.",
    ),
) -> None:
    """Validate local RoleLens setup readiness."""
    result = run_setup_check(root)
    for message in result.messages:
        typer.echo(message)
    if not result.ok:
        raise typer.Exit(code=1)


@app.command("import-manual")
def import_manual(
    imports_dir: Path = typer.Argument(
        Path("imports/manual"),
        help="Directory containing manual Markdown or JSON job imports.",
    ),
    output_path: Path = typer.Option(
        Path("data/jobs_raw.json"),
        "--output",
        help="Path where normalized manual jobs will be written.",
    ),
) -> None:
    """Import manually captured jobs from Markdown frontmatter or JSON."""
    result = import_manual_jobs(imports_dir, output_path)
    for message in result.messages:
        typer.echo(message)
    typer.echo(
        f"Imported {result.imported_count} manual job(s) "
        f"to {result.output_path}"
    )
    if result.skipped_count:
        raise typer.Exit(code=1)


@app.command("export-review-queue")
def export_review_queue_command(
    jobs_path: Path = typer.Option(
        Path("data/jobs_raw.json"),
        "--jobs",
        help="Path to normalized jobs JSON.",
    ),
    output_dir: Path = typer.Option(
        Path("review_queue"),
        "--output-dir",
        "-o",
        help="Directory where review queue files will be written.",
    ),
) -> None:
    """Export machine-readable jobs and agent-readable review prompts."""
    result = export_review_queue(jobs_path, output_dir)
    for message in result.messages:
        typer.echo(message)
    typer.echo(
        f"Exported {result.exported_count} job(s) to {result.output_dir} "
        f"({result.skipped_count} skipped)"
    )


if __name__ == "__main__":
    app()
