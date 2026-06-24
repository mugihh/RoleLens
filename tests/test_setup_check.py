from pathlib import Path

from rolelens.setup_check import run_setup_check


def test_setup_check_reports_missing_private_profile() -> None:
    result = run_setup_check(Path("."))

    assert not result.ok
    assert any("MISSING candidate/profile.yaml" in item for item in result.messages)
    assert any("OK config/sources.yaml" in item for item in result.messages)


def test_setup_check_recommends_cv_md_when_resume_exists(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "candidate"
    candidate_dir.mkdir()
    (candidate_dir / "profile.example.yaml").write_text("target_regions: []\n")
    (candidate_dir / "cv.example.md").write_text("# Example\n")
    (candidate_dir / "chen-yu-resume-2026.tex").write_text("resume source")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "sources.yaml").write_text("companies:\n  example: {}\n")

    for runtime_dir in ["imports/manual", "review_queue", "review_results", "reports"]:
        (tmp_path / runtime_dir).mkdir(parents=True)

    result = run_setup_check(tmp_path)

    assert any(
        "RECOMMENDED create candidate/cv.md from candidate/chen-yu-resume-2026.tex"
        in item
        for item in result.messages
    )
