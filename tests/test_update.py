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
