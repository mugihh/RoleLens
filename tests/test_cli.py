from typer.testing import CliRunner

from rolelens.cli import app


PUBLIC_COMMANDS = [
    "demo",
    "setup-check",
    "update",
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
