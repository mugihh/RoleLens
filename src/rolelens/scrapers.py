from __future__ import annotations

import html
import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

import yaml

from rolelens.models import JobRecord, JobStatus, PrefilterStatus


FetchJson = Callable[[str], dict[str, Any]]


@dataclass(frozen=True)
class SourceScanResult:
    jobs: list[JobRecord]
    messages: list[str]


def scan_configured_sources(
    sources_path: Path,
    scan_date: date,
    fetch_json: FetchJson | None = None,
) -> SourceScanResult:
    if not sources_path.exists():
        return SourceScanResult(jobs=[], messages=[f"SKIP missing {sources_path}"])

    fetch_json = fetch_json or _fetch_json
    config = yaml.safe_load(sources_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"Expected YAML mapping in {sources_path}")
    companies = config.get("companies", {})
    if not isinstance(companies, dict):
        raise ValueError("config/sources.yaml must define a companies mapping")

    jobs: list[JobRecord] = []
    messages: list[str] = []
    for source_key, source in companies.items():
        if not isinstance(source, dict):
            messages.append(f"SKIP {source_key}: invalid source config")
            continue
        if source.get("source_type") != "greenhouse":
            messages.append(f"SKIP {source_key}: source_type={source.get('source_type')}")
            continue
        if source.get("status") not in {"supported", "experimental"}:
            messages.append(f"SKIP {source_key}: status={source.get('status')}")
            continue

        try:
            source_jobs = scan_greenhouse_board(source_key, source, scan_date, fetch_json)
        except Exception as exc:
            messages.append(f"WARN {source_key}: greenhouse scan failed: {exc}")
            continue
        jobs.extend(source_jobs)
        messages.append(f"SCAN {source_key}: {len(source_jobs)} job(s)")

    return SourceScanResult(jobs=jobs, messages=messages)


def scan_greenhouse_board(
    source_key: str,
    source: dict[str, Any],
    scan_date: date,
    fetch_json: FetchJson,
) -> list[JobRecord]:
    source_id = _required_string(source, "source_id")
    company_name = _required_string(source, "name")
    url = f"https://boards-api.greenhouse.io/v1/boards/{source_id}/jobs?content=true"
    data = fetch_json(url)
    raw_jobs = data.get("jobs")
    if not isinstance(raw_jobs, list):
        raise ValueError("Greenhouse response missing jobs list")

    jobs: list[JobRecord] = []
    for raw_job in raw_jobs:
        if not isinstance(raw_job, dict):
            continue
        job = _greenhouse_job_to_record(source_key, company_name, raw_job, scan_date)
        if _matches_source_regions(job, source):
            jobs.append(job)
    return jobs


def _greenhouse_job_to_record(
    source_key: str,
    company_name: str,
    raw_job: dict[str, Any],
    scan_date: date,
) -> JobRecord:
    raw_id = raw_job.get("id")
    title = _coerce_string(raw_job.get("title")) or "Untitled Role"
    location = _extract_location(raw_job)
    url = _coerce_string(raw_job.get("absolute_url")) or ""
    description = _strip_html(_coerce_string(raw_job.get("content")) or "")
    if not description:
        description = title

    return JobRecord(
        job_id=f"greenhouse-{source_key}-{raw_id or _slug(title)}",
        company=company_name,
        title=title,
        location=location,
        region=_infer_region(location),
        url=url,
        source=f"greenhouse:{source_key}",
        prefilter_status=PrefilterStatus.WATCH,
        status=JobStatus.ACTIVE,
        first_seen=scan_date,
        last_seen=scan_date,
        description=description,
    )


def _fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "RoleLens/0.1"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_location(raw_job: dict[str, Any]) -> str:
    location = raw_job.get("location")
    if isinstance(location, dict):
        value = _coerce_string(location.get("name"))
        if value:
            return value
    return "Unknown"


def _strip_html(value: str) -> str:
    text = html.unescape(value)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _matches_source_regions(job: JobRecord, source: dict[str, Any]) -> bool:
    regions = source.get("regions")
    if not isinstance(regions, list) or not regions:
        return True
    normalized_regions = {str(region).lower() for region in regions}
    return job.region.lower() in normalized_regions


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
    value = _coerce_string(data.get(key))
    if not value:
        raise ValueError(f"missing required source field: {key}")
    return value


def _coerce_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, int):
        return str(value)
    return None


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "job"
