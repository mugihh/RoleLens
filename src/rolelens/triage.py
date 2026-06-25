from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from rolelens.filters import prefilter_job
from rolelens.models import JobRecord, PrefilterStatus


@dataclass(frozen=True)
class TriageResult:
    output_path: Path
    likely_count: int
    maybe_count: int
    skip_count: int
    already_reviewed_count: int


def generate_review_plan(
    jobs_path: Path,
    profile_path: Path | None,
    review_results_dir: Path,
    output_path: Path,
    limit: int = 20,
    snippet_chars: int = 600,
) -> TriageResult:
    jobs = _load_jobs(jobs_path)
    profile = _load_profile(profile_path)
    reviewed_ids = _reviewed_job_ids(review_results_dir)

    buckets: dict[str, list[tuple[JobRecord, list[str]]]] = {
        "likely": [],
        "maybe": [],
        "skip": [],
        "already_reviewed": [],
    }
    for job in jobs:
        if job.job_id in reviewed_ids:
            buckets["already_reviewed"].append((job, ["Already reviewed"]))
            continue
        bucket, reasons = _classify_job(job, profile)
        buckets[bucket].append((job, reasons))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        _render_plan(buckets, limit=limit, snippet_chars=snippet_chars),
        encoding="utf-8",
    )
    return TriageResult(
        output_path=output_path,
        likely_count=len(buckets["likely"]),
        maybe_count=len(buckets["maybe"]),
        skip_count=len(buckets["skip"]),
        already_reviewed_count=len(buckets["already_reviewed"]),
    )


def _load_jobs(path: Path) -> list[JobRecord]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return [JobRecord.model_validate(item) for item in data]


def _load_profile(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return data


def _reviewed_job_ids(path: Path) -> set[str]:
    if not path.is_dir():
        return set()
    return {
        review_path.name.removesuffix(".review.json")
        for review_path in path.glob("*.review.json")
    }


def _classify_job(job: JobRecord, profile: dict[str, Any]) -> tuple[str, list[str]]:
    title = job.title.lower()
    text = f"{job.title}\n{job.description[:1200]}".lower()
    target_matches = _profile_matches(text, profile.get("target_roles"))
    avoid_title_matches = _profile_matches(title, profile.get("roles_to_avoid"))
    avoid_text_matches = _profile_matches(text, profile.get("roles_to_avoid"))
    prefilter = prefilter_job(job)

    if avoid_title_matches:
        return "skip", [
            "Title matches profile roles_to_avoid: "
            + ", ".join(avoid_title_matches)
        ]

    if target_matches and not avoid_text_matches:
        return "likely", [
            "Matches profile target_roles: " + ", ".join(target_matches[:4]),
            f"Prefilter status: {prefilter.status}",
        ]

    if prefilter.status == PrefilterStatus.INCLUDE:
        reasons = ["Public prefilter marks this as include"]
        if avoid_text_matches:
            reasons.append(
                "But JD snippet also matches roles_to_avoid: "
                + ", ".join(avoid_text_matches[:4])
            )
        return "maybe", reasons

    if prefilter.status == PrefilterStatus.WATCH:
        return "maybe", ["Public prefilter marks this as watch"]

    return "skip", prefilter.reasons


def _profile_matches(text: str, values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    matches: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = value.lower().strip()
        if normalized and normalized in text:
            matches.append(value)
    return matches


def _render_plan(
    buckets: dict[str, list[tuple[JobRecord, list[str]]]],
    limit: int,
    snippet_chars: int,
) -> str:
    lines = [
        "# RoleLens Review Plan",
        "",
        "Token-saving first pass. Review `likely` jobs first, then selected `maybe` jobs.",
        "This file is not a final fit judgment; it is a plan for agent full review.",
        "",
        "## Summary",
        "",
    ]
    for bucket in ["likely", "maybe", "skip", "already_reviewed"]:
        lines.append(f"- {bucket}: {len(buckets[bucket])}")
    lines.append("")

    for bucket in ["likely", "maybe", "already_reviewed", "skip"]:
        items = buckets[bucket]
        shown = items if bucket in {"skip", "already_reviewed"} else items[:limit]
        lines.extend([f"## {bucket.replace('_', ' ').title()}", ""])
        if bucket in {"likely", "maybe"} and len(items) > limit:
            lines.append(f"Showing top {limit} of {len(items)} jobs.")
            lines.append("")
        for job, reasons in shown:
            lines.extend(
                [
                    f"### {job.company} - {job.title}",
                    "",
                    f"- Job ID: `{job.job_id}`",
                    f"- Location: {job.location}",
                    f"- Source: {job.source}",
                    f"- URL: {job.url}",
                    f"- Reasons: {'; '.join(reasons)}",
                    f"- Snippet: {_snippet(job.description, snippet_chars)}",
                    "",
                ]
            )
    return "\n".join(lines)


def _snippet(text: str, snippet_chars: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= snippet_chars:
        return compact
    return compact[: max(0, snippet_chars - 3)] + "..."
