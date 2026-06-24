from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from rolelens.models import JobRecord, JobStatus, PrefilterStatus


@dataclass(frozen=True)
class ManualImportResult:
    output_path: Path
    imported_count: int
    skipped_count: int
    messages: list[str]


def import_manual_jobs(
    imports_dir: Path,
    output_path: Path,
    today: date | None = None,
) -> ManualImportResult:
    today = today or date.today()
    messages: list[str] = []
    jobs: list[JobRecord] = []
    skipped_count = 0

    for path in sorted(imports_dir.iterdir()):
        if path.name == ".gitkeep" or path.is_dir():
            continue
        try:
            jobs.extend(_load_manual_file(path, today))
        except ValueError as exc:
            skipped_count += 1
            messages.append(f"SKIP {path}: {exc}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            [job.model_dump(mode="json") for job in jobs],
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return ManualImportResult(
        output_path=output_path,
        imported_count=len(jobs),
        skipped_count=skipped_count,
        messages=messages,
    )


def _load_manual_file(path: Path, today: date) -> list[JobRecord]:
    if path.suffix.lower() == ".md":
        return [_load_markdown_job(path, today)]
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else [data]
        if not all(isinstance(item, dict) for item in items):
            raise ValueError("JSON manual import must be an object or list of objects")
        return [_job_from_mapping(item, today) for item in items]
    raise ValueError("manual import must be .md or .json")


def _load_markdown_job(path: Path, today: date) -> JobRecord:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text)
    data = yaml.safe_load(frontmatter)
    if not isinstance(data, dict):
        raise ValueError("Markdown frontmatter must be a mapping")
    data["description"] = body.strip()
    return _job_from_mapping(data, today)


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise ValueError("Markdown manual import must start with YAML frontmatter")
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        raise ValueError("Markdown manual import frontmatter is not closed")
    return parts[0].removeprefix("---\n"), parts[1]


def _job_from_mapping(data: dict[str, Any], today: date) -> JobRecord:
    company = _required_string(data, "company")
    title = _required_string(data, "title")
    location = _required_string(data, "location")
    url = _required_string(data, "url")
    description = _required_string(data, "description")

    payload = {
        "job_id": data.get("job_id") or _manual_job_id(company, title, url),
        "company": company,
        "title": title,
        "location": location,
        "region": data.get("region") or _infer_region(location),
        "url": url,
        "source": data.get("source") or "manual",
        "prefilter_status": data.get("prefilter_status") or PrefilterStatus.INCLUDE,
        "status": data.get("status") or JobStatus.ACTIVE,
        "first_seen": data.get("first_seen") or today,
        "last_seen": data.get("last_seen") or today,
        "description": description,
    }
    return JobRecord.model_validate(payload)


def _manual_job_id(company: str, title: str, url: str) -> str:
    digest = hashlib.sha1(f"{company}\n{title}\n{url}".encode()).hexdigest()[:10]
    return f"manual-{digest}"


def _infer_region(location: str) -> str:
    normalized = location.lower()
    if "japan" in normalized or "tokyo" in normalized:
        return "Japan"
    if "singapore" in normalized:
        return "Singapore"
    if "taiwan" in normalized or "taipei" in normalized:
        return "Taiwan"
    return "Unknown"


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing required field: {key}")
    return value.strip()
