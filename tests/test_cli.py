from typer.testing import CliRunner

from rolelens.cli import app


PUBLIC_COMMANDS = [
    "demo",
    "setup-check",
    "update",
    "triage",
    "import-manual",
    "import-reviews",
    "report",
]

INTERNAL_COMMANDS = [
    "export-review-queue",
    "scan",
    "diff",
    "queue",
    "scrape",
]


def _visible_command_names() -> set[str]:
    names: set[str] = set()
    for command in app.registered_commands:
        if command.hidden:
            continue
        if command.name is not None:
            names.add(command.name)
        else:
            names.add(command.callback.__name__.replace("_", "-"))
    return names


def test_v1_public_command_surface() -> None:
    assert _visible_command_names() == set(PUBLIC_COMMANDS)


def test_help_shows_v1_public_commands() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in PUBLIC_COMMANDS:
        assert command in result.output


def test_internal_commands_are_not_public() -> None:
    assert not _visible_command_names().intersection(INTERNAL_COMMANDS)


def test_help_hides_export_review_queue() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "export-review-queue" not in result.output


def test_import_manual_private_root_uses_overlay_defaults(tmp_path) -> None:
    private_root = tmp_path / "private"
    imports_dir = private_root / "imports" / "manual"
    imports_dir.mkdir(parents=True)
    (imports_dir / "job.md").write_text(
        """---
company: Example
title: Software Engineer
location: Tokyo, Japan
url: https://example.com/job
source: manual
---

Build Python services and developer tools.
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        ["import-manual", "--private-root", str(private_root)],
    )

    assert result.exit_code == 0
    assert (private_root / "data" / "jobs_raw.json").exists()
    assert "Imported 1 manual job(s)" in result.output


def test_import_manual_explicit_paths_override_private_root(tmp_path) -> None:
    private_root = tmp_path / "private"
    explicit_imports = tmp_path / "explicit_imports"
    explicit_output = tmp_path / "explicit_data" / "jobs.json"
    explicit_imports.mkdir()
    (explicit_imports / "job.md").write_text(
        """---
company: Explicit
title: Backend Engineer
location: Tokyo, Japan
url: https://example.com/explicit
source: manual
---

Build backend systems.
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "import-manual",
            str(explicit_imports),
            "--output",
            str(explicit_output),
            "--private-root",
            str(private_root),
        ],
    )

    assert result.exit_code == 0
    assert explicit_output.exists()
    assert not (private_root / "data" / "jobs_raw.json").exists()


def test_report_private_root_uses_overlay_database_and_reports(tmp_path) -> None:
    private_root = tmp_path / "private"
    imports_dir = private_root / "imports" / "manual"
    imports_dir.mkdir(parents=True)
    (imports_dir / "job.md").write_text(
        """---
company: Example
title: Machine Learning Engineer
location: Tokyo, Japan
url: https://example.com/ml
source: manual
---

Build ML evaluation pipelines.
""",
        encoding="utf-8",
    )
    update_result = CliRunner().invoke(
        app,
        ["update", "--private-root", str(private_root), "--no-scan-sources"],
    )
    assert update_result.exit_code == 0

    report_result = CliRunner().invoke(
        app,
        ["report", "--private-root", str(private_root)],
    )

    assert report_result.exit_code == 0
    assert (private_root / "reports" / "latest.html").exists()
    assert (private_root / "reports" / "latest.md").exists()


def test_triage_private_root_writes_review_plan(tmp_path) -> None:
    private_root = tmp_path / "private"
    imports_dir = private_root / "imports" / "manual"
    candidate_dir = private_root / "candidate"
    imports_dir.mkdir(parents=True)
    candidate_dir.mkdir(parents=True)
    (candidate_dir / "profile.yaml").write_text(
        """target_roles:
  - Machine Learning Engineer
roles_to_avoid:
  - Sales Engineer
""",
        encoding="utf-8",
    )
    (imports_dir / "ml.md").write_text(
        """---
company: Example
title: Machine Learning Engineer
location: Tokyo, Japan
url: https://example.com/ml
source: manual
---

Build ML evaluation pipelines.
""",
        encoding="utf-8",
    )
    (imports_dir / "sales.md").write_text(
        """---
company: Example
title: Sales Engineer
location: Tokyo, Japan
url: https://example.com/sales
source: manual
---

Support sales teams.
""",
        encoding="utf-8",
    )
    update_result = CliRunner().invoke(
        app,
        ["update", "--private-root", str(private_root), "--no-scan-sources"],
    )
    assert update_result.exit_code == 0

    result = CliRunner().invoke(
        app,
        ["triage", "--private-root", str(private_root), "--limit", "5"],
    )

    assert result.exit_code == 0
    review_plan = private_root / "reports" / "review_plan.md"
    assert review_plan.exists()
    text = review_plan.read_text(encoding="utf-8")
    assert "## Likely" in text
    assert "Machine Learning Engineer" in text
    assert "Title matches profile roles_to_avoid" in text
