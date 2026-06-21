from pathlib import Path

import typer

from rolelens.reports import generate_demo_report

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


if __name__ == "__main__":
    app()
