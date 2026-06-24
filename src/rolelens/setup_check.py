from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SetupCheckResult:
    ok: bool
    messages: list[str]


def run_setup_check(root: Path) -> SetupCheckResult:
    messages: list[str] = []
    ok = True

    profile_path = root / "candidate" / "profile.yaml"
    profile_example_path = root / "candidate" / "profile.example.yaml"
    candidate_dir = root / "candidate"
    cv_path = root / "candidate" / "cv.md"
    cv_example_path = root / "candidate" / "cv.example.md"
    resume_source_paths = _find_resume_sources(candidate_dir)
    sources_path = root / "config" / "sources.yaml"

    if profile_path.exists():
        profile = _load_yaml_mapping(profile_path)
        missing_keys = _missing_keys(
            profile,
            [
                "target_regions",
                "target_roles",
                "roles_to_avoid",
                "target_sources",
                "language_preferences",
                "work_authorization",
                "remote_preferences",
                "compensation_importance",
            ],
        )
        if missing_keys:
            ok = False
            messages.append(
                "candidate/profile.yaml is missing keys: "
                + ", ".join(missing_keys)
            )
        else:
            messages.append("OK candidate/profile.yaml")
    elif profile_example_path.exists():
        ok = False
        messages.append(
            "MISSING candidate/profile.yaml "
            "(start from candidate/profile.example.yaml)"
        )
    else:
        ok = False
        messages.append("MISSING candidate/profile.yaml and profile example")

    if cv_path.exists():
        messages.append("OK candidate/cv.md")
    elif resume_source_paths:
        resume_sources = [
            str(path.relative_to(root))
            for path in resume_source_paths
        ]
        messages.append(
            "RECOMMENDED create candidate/cv.md from "
            + ", ".join(resume_sources)
            + " before agent review"
        )
    elif cv_example_path.exists():
        messages.append(
            "OPTIONAL candidate/cv.md is missing "
            "(candidate/cv.example.md is available)"
        )
    else:
        messages.append("OPTIONAL candidate/cv.md is missing")

    if sources_path.exists():
        sources = _load_yaml_mapping(sources_path)
        companies = sources.get("companies")
        if not isinstance(companies, dict) or not companies:
            ok = False
            messages.append("config/sources.yaml must define companies")
        else:
            messages.append(f"OK config/sources.yaml ({len(companies)} companies)")
    else:
        ok = False
        messages.append("MISSING config/sources.yaml")

    for runtime_dir in ["imports/manual", "review_queue", "review_results", "reports"]:
        path = root / runtime_dir
        if path.is_dir():
            messages.append(f"OK {runtime_dir}/")
        else:
            ok = False
            messages.append(f"MISSING {runtime_dir}/")

    return SetupCheckResult(ok=ok, messages=messages)


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return data


def _missing_keys(data: dict[str, Any], required_keys: list[str]) -> list[str]:
    return [key for key in required_keys if key not in data]


def _find_resume_sources(candidate_dir: Path) -> list[Path]:
    if not candidate_dir.is_dir():
        return []
    return sorted(
        path
        for path in candidate_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".tex", ".pdf"}
    )
