from pathlib import Path

import typer

app = typer.Typer(
    help="RoleLens: a local-first, agent-assisted job radar for technical roles."
)


@app.callback()
def main() -> None:
    """RoleLens command line interface."""


@app.command()
def demo(
    output_dir: Path = typer.Option(
        Path("reports"),
        "--output-dir",
        "-o",
        help="Directory where demo artifacts will be written.",
    ),
) -> None:
    """Generate demo reports from sample data."""
    output_dir.mkdir(parents=True, exist_ok=True)
    typer.echo(f"RoleLens demo placeholder. Reports directory: {output_dir}")


if __name__ == "__main__":
    app()
