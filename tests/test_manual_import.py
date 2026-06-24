import json
from datetime import date
from pathlib import Path

from rolelens.manual_import import import_manual_jobs


def test_import_manual_markdown_frontmatter(tmp_path: Path) -> None:
    imports_dir = tmp_path / "imports"
    imports_dir.mkdir()
    manual_file = imports_dir / "paypay.md"
    manual_file.write_text(
        """---
company: Payflow Labs
title: Backend Software Engineer
location: Tokyo, Japan
url: https://example.com/payflow/backend
source: manual
---

Build backend payment systems.
""",
        encoding="utf-8",
    )

    output_path = tmp_path / "jobs_raw.json"
    result = import_manual_jobs(
        imports_dir,
        output_path,
        today=date(2026, 6, 24),
    )

    assert result.imported_count == 1
    assert result.skipped_count == 0
    jobs = json.loads(output_path.read_text(encoding="utf-8"))
    assert jobs[0]["company"] == "Payflow Labs"
    assert jobs[0]["region"] == "Japan"
    assert jobs[0]["prefilter_status"] == "include"
    assert jobs[0]["first_seen"] == "2026-06-24"


def test_import_manual_skips_invalid_files(tmp_path: Path) -> None:
    imports_dir = tmp_path / "imports"
    imports_dir.mkdir()
    (imports_dir / "bad.md").write_text("No frontmatter", encoding="utf-8")

    result = import_manual_jobs(imports_dir, tmp_path / "jobs_raw.json")

    assert result.imported_count == 0
    assert result.skipped_count == 1
    assert "SKIP" in result.messages[0]
