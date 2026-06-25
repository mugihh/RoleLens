from pathlib import Path

import typer

from rolelens.manual_import import import_manual_jobs
from rolelens.reports import (
    generate_demo_report,
    generate_personal_report,
    generate_sqlite_report,
)
from rolelens.review_queue import export_review_queue
from rolelens.reviews import import_reviews
from rolelens.setup_check import run_setup_check
from rolelens.update import run_update

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


@app.command("update")
def update_command(
    imports_dir: Path = typer.Option(
        Path("imports/manual"),
        "--imports-dir",
        help="Directory containing manual Markdown or JSON job imports.",
    ),
    jobs_path: Path = typer.Option(
        Path("data/jobs_raw.json"),
        "--jobs-output",
        help="Path where normalized imported jobs will be written.",
    ),
    database_path: Path = typer.Option(
        Path("data/rolelens.sqlite"),
        "--database",
        help="Local SQLite database path.",
    ),
    review_queue_dir: Path = typer.Option(
        Path("review_queue"),
        "--review-queue-dir",
        help="Directory where review queue files will be written.",
    ),
    reports_dir: Path = typer.Option(
        Path("reports"),
        "--reports-dir",
        help="Directory where preliminary latest reports will be written.",
    ),
    sources_path: Path = typer.Option(
        Path("config/sources.yaml"),
        "--sources",
        help="Source config for supported scanners.",
    ),
    scan_sources: bool = typer.Option(
        True,
        "--scan-sources/--no-scan-sources",
        help="Scan configured sources in addition to manual imports.",
    ),
) -> None:
    """Prepare review queue and preliminary report from local sources."""
    result = run_update(
        imports_dir=imports_dir,
        jobs_path=jobs_path,
        database_path=database_path,
        review_queue_dir=review_queue_dir,
        reports_dir=reports_dir,
        sources_path=sources_path if scan_sources else None,
    )
    typer.echo(f"Updated database: {result.database_path}")
    for message in result.messages:
        typer.echo(message)
    for job_id, state in sorted(result.scan_states.items()):
        typer.echo(f"{state.upper()} {job_id}")
    typer.echo(
        f"Exported {result.queue_result.exported_count} review queue job(s) "
        f"to {result.queue_result.output_dir}"
    )
    typer.echo(f"Generated preliminary report: {result.report_result.html_path}")


@app.command("export-review-queue", hidden=True)
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


@app.command("import-reviews")
def import_reviews_command(
    review_results_dir: Path = typer.Argument(
        Path("review_results"),
        help="Directory containing agent-generated *.review.json files.",
    ),
    jobs_path: Path = typer.Option(
        Path("data/jobs_raw.json"),
        "--jobs",
        help="Path to normalized jobs JSON used to validate job IDs.",
    ),
    output_dir: Path = typer.Option(
        Path("data/reviews"),
        "--output-dir",
        "-o",
        help="Directory where validated reviews will be stored.",
    ),
    database_path: Path = typer.Option(
        Path("data/rolelens.sqlite"),
        "--database",
        help="Local SQLite database path to update with review metadata.",
    ),
) -> None:
    """Validate and persist agent-generated review JSON."""
    try:
        result = import_reviews(
            review_results_dir,
            jobs_path,
            output_dir,
            database_path=database_path,
        )
    except ValueError as exc:
        typer.echo(f"ERROR {exc}", err=True)
        raise typer.Exit(code=1) from exc
    for message in result.messages:
        typer.echo(message)
    typer.echo(
        f"Imported {result.imported_count} review(s) to {result.output_dir} "
        f"({result.warning_count} warning(s), {result.skipped_count} skipped)"
    )
    if result.skipped_count:
        raise typer.Exit(code=1)


@app.command("report")
def report_command(
    database_path: Path = typer.Option(
        Path("data/rolelens.sqlite"),
        "--database",
        help="Local SQLite database path.",
    ),
    jobs_path: Path | None = typer.Option(
        None,
        "--jobs",
        help="Optional legacy path to normalized jobs JSON.",
    ),
    reviews_dir: Path | None = typer.Option(
        None,
        "--reviews-dir",
        help="Optional legacy directory containing imported *.review.json files.",
    ),
    output_dir: Path = typer.Option(
        Path("reports"),
        "--output-dir",
        "-o",
        help="Directory where latest report files will be written.",
    ),
) -> None:
    """Generate latest personal reports from local jobs and imported reviews."""
    try:
        if jobs_path is not None:
            result = generate_personal_report(
                jobs_path,
                reviews_dir or Path("data/reviews"),
                output_dir,
            )
        else:
            result = generate_sqlite_report(database_path, output_dir)
    except ValueError as exc:
        typer.echo(f"ERROR {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        "Generated latest report "
        f"({result.job_count} jobs, {result.reviewed_count} reviewed):"
    )
    typer.echo(f"- {result.markdown_path}")
    typer.echo(f"- {result.html_path}")


if __name__ == "__main__":
    app()
