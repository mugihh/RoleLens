from pathlib import Path

from rolelens.update import run_update


def write_manual_job(imports_dir: Path, title: str = "Backend Software Engineer") -> None:
    imports_dir.mkdir(parents=True)
    (imports_dir / "job.md").write_text(
        f"""---
company: Payflow Labs
title: {title}
location: Tokyo, Japan
url: https://example.com/payflow/backend
source: manual
---

Build backend payment systems and product APIs.
""",
        encoding="utf-8",
    )


def test_update_imports_manual_jobs_syncs_sqlite_exports_queue_and_report(
    tmp_path: Path,
) -> None:
    imports_dir = tmp_path / "imports" / "manual"
    write_manual_job(imports_dir)

    result = run_update(
        imports_dir=imports_dir,
        jobs_path=tmp_path / "data" / "jobs_raw.json",
        database_path=tmp_path / "data" / "rolelens.sqlite",
        review_queue_dir=tmp_path / "review_queue",
        reports_dir=tmp_path / "reports",
    )

    job_id = next(iter(result.scan_states))
    assert result.scan_states == {job_id: "new"}
    assert result.queue_result.exported_count == 1
    assert (tmp_path / "review_queue" / f"{job_id}.job.json").exists()
    assert (tmp_path / "reports" / "latest.html").exists()
    assert result.database_path.exists()


def test_update_marks_removed_jobs_missing(tmp_path: Path) -> None:
    imports_dir = tmp_path / "imports" / "manual"
    write_manual_job(imports_dir)
    kwargs = {
        "imports_dir": imports_dir,
        "jobs_path": tmp_path / "data" / "jobs_raw.json",
        "database_path": tmp_path / "data" / "rolelens.sqlite",
        "review_queue_dir": tmp_path / "review_queue",
        "reports_dir": tmp_path / "reports",
    }
    run_update(**kwargs)
    (imports_dir / "job.md").unlink()

    result = run_update(**kwargs)

    job_id = next(iter(result.scan_states))
    assert result.scan_states == {job_id: "missing"}


def test_update_scans_greenhouse_sources_without_blocking_manual_import(
    tmp_path: Path,
) -> None:
    imports_dir = tmp_path / "imports" / "manual"
    write_manual_job(imports_dir)
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(
        """
companies:
  example_greenhouse:
    name: Example Greenhouse
    source_type: greenhouse
    source_id: example
    regions: [Japan]
    status: experimental
    tags: [demo]
""",
        encoding="utf-8",
    )

    def fake_fetch(_url: str) -> dict[str, object]:
        return {
            "jobs": [
                {
                    "id": 123,
                    "title": "Machine Learning Engineer",
                    "absolute_url": "https://example.com/jobs/123",
                    "location": {"name": "Tokyo, Japan"},
                    "content": "<p>Build production ML systems.</p>",
                }
            ]
        }

    result = run_update(
        imports_dir=imports_dir,
        jobs_path=tmp_path / "data" / "jobs_raw.json",
        database_path=tmp_path / "data" / "rolelens.sqlite",
        review_queue_dir=tmp_path / "review_queue",
        reports_dir=tmp_path / "reports",
        sources_path=sources_path,
        fetch_json=fake_fetch,
    )

    assert result.queue_result.exported_count == 2
    assert "greenhouse-example_greenhouse-123" in result.scan_states
    assert any("SCAN example_greenhouse: 1 job(s)" in item for item in result.messages)


def test_update_keeps_manual_import_when_source_scan_fails(tmp_path: Path) -> None:
    imports_dir = tmp_path / "imports" / "manual"
    write_manual_job(imports_dir)
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(
        """
companies:
  broken:
    name: Broken Board
    source_type: greenhouse
    source_id: broken
    regions: [Japan]
    status: experimental
    tags: [demo]
""",
        encoding="utf-8",
    )

    def broken_fetch(_url: str) -> dict[str, object]:
        raise RuntimeError("network down")

    result = run_update(
        imports_dir=imports_dir,
        jobs_path=tmp_path / "data" / "jobs_raw.json",
        database_path=tmp_path / "data" / "rolelens.sqlite",
        review_queue_dir=tmp_path / "review_queue",
        reports_dir=tmp_path / "reports",
        sources_path=sources_path,
        fetch_json=broken_fetch,
    )

    assert result.queue_result.exported_count == 1
    assert any("WARN broken: greenhouse scan failed" in item for item in result.messages)
