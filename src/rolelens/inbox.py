from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml

from rolelens.models import JobRecord, JobStatus

# Built-in, generic signal vocabularies. These describe what RoleLens is for —
# early-career technical IC roles — and are tuned at runtime by the candidate
# profile (regions, compensation floor, and large-company list).
ROLE_TERMS: dict[str, tuple[str, ...]] = {
    "ML/NLP": (
        "machine learning",
        "ml engineer",
        "nlp",
        "nlu",
        "llm",
        "language model",
        "ai engineer",
        "applied scientist",
        "data scientist",
    ),
    "Research engineering": ("research engineer",),
    "Software engineering": (
        "software engineer",
        "fullstack engineer",
        "full-stack engineer",
        "backend engineer",
        "back-end engineer",
        "data engineer",
    ),
}
ROLE_SCORES = {"ML/NLP": 28, "Research engineering": 25, "Software engineering": 18}
EARLY_CAREER_TERMS = (
    "new grad",
    "new graduate",
    "graduate",
    "junior",
    "entry level",
    "entry-level",
    "early career",
    "新卒",
)
SENIOR_TERMS = (
    "senior",
    "sr.",
    "sr ",
    "staff",
    "principal",
    "manager",
    "director",
    "lead ",
    "head of",
)
CUSTOMER_TERMS = (
    "customer-facing",
    "client-facing",
    "pre-sales",
    "presales",
    "sales support",
    "customer success",
    "account management",
)
CUSTOMER_TITLE_TERMS = (
    "solution architect",
    "solutions architect",
    "sales engineer",
    "consultant",
    "customer engineer",
    "field engineer",
)
DIRECT_SOURCE_PREFIXES = (
    "private:amazon",
    "private:google",
    "private:greenhouse",
    "private:lever",
    "private:workable",
)
_DEFAULT_MIN_COMPENSATION_JPY = 5_000_000


@dataclass(frozen=True)
class InboxResult:
    output_path: Path
    json_path: Path
    inbox_count: int
    potential_count: int
    archive_count: int


@dataclass
class _ProfileSettings:
    primary_regions: set[str]
    secondary_regions: set[str]
    large_companies: set[str]
    min_compensation_millions: float


@dataclass
class RankedJob:
    job: JobRecord
    score: int
    reasons: list[str]
    risks: list[str]


def generate_inbox(
    jobs_path: Path,
    profile_path: Path | None,
    review_results_dir: Path,
    output_path: Path,
    json_path: Path,
    inbox_size: int = 5,
    potential_size: int = 20,
) -> InboxResult:
    """Build a small, zero-LLM job inbox from the broad local job pool.

    The collection layer stays broad; this narrows daily attention to a Top N
    that needs a quick decision, a Potential pool to browse, and a searchable
    archive that needs no action. It calls no model and consumes no tokens.
    """
    jobs = _load_jobs(jobs_path)
    profile = _load_profile(profile_path)
    settings = _profile_settings(profile)
    reviewed_ids = _reviewed_job_ids(review_results_dir)

    active = [
        job
        for job in jobs
        if job.status == JobStatus.ACTIVE and job.job_id not in reviewed_ids
    ]
    ranked = _dedupe_ranked([_rank_job(job, settings) for job in active])
    inbox, remaining = _select_with_company_cap(ranked, inbox_size, per_company=1)
    potential, archive = _select_with_company_cap(
        remaining, potential_size, per_company=2
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        _render_markdown(inbox, potential, archive_count=len(archive)),
        encoding="utf-8",
    )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(
            {
                "inbox": [_serialize(item) for item in inbox],
                "potential": [_serialize(item) for item in potential],
                "archive_count": len(archive),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return InboxResult(
        output_path=output_path,
        json_path=json_path,
        inbox_count=len(inbox),
        potential_count=len(potential),
        archive_count=len(archive),
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


def _profile_settings(profile: dict[str, Any]) -> _ProfileSettings:
    region_prefs = profile.get("region_preferences")
    primary: set[str] = set()
    secondary: set[str] = set()
    if isinstance(region_prefs, dict):
        for region, preference in region_prefs.items():
            if not isinstance(region, str):
                continue
            if str(preference).lower() == "primary":
                primary.add(region)
            else:
                secondary.add(region)
    target_regions = profile.get("target_regions")
    if isinstance(target_regions, list):
        for region in target_regions:
            if isinstance(region, str) and region not in primary:
                secondary.add(region)

    large_companies = {
        _normalize_company(name)
        for name in profile.get("large_companies", [])
        if isinstance(name, str) and name.strip()
    }

    work_auth = profile.get("work_authorization")
    minimum_jpy = _DEFAULT_MIN_COMPENSATION_JPY
    if isinstance(work_auth, dict):
        candidate = work_auth.get("minimum_japan_compensation_jpy")
        if isinstance(candidate, (int, float)) and candidate > 0:
            minimum_jpy = float(candidate)

    return _ProfileSettings(
        primary_regions=primary,
        secondary_regions=secondary - primary,
        large_companies=large_companies,
        min_compensation_millions=minimum_jpy / 1_000_000,
    )


def _rank_job(job: JobRecord, settings: _ProfileSettings) -> RankedJob:
    title_lower = job.title.lower()
    text = f"{job.title}\n{job.description[:5000]}".lower()
    score = 0
    reasons: list[str] = []
    risks: list[str] = []

    role = next(
        (
            name
            for name, terms in ROLE_TERMS.items()
            if any(term in title_lower for term in terms)
        ),
        None,
    )
    if role is not None:
        score += ROLE_SCORES[role]
        reasons.append(f"{role} title match")
    else:
        score -= 30
        risks.append("Title is not one of the core target engineering roles")

    if any(term in title_lower for term in EARLY_CAREER_TERMS):
        score += 35
        reasons.append("Explicit new-grad, junior, or early-career signal")

    if settings.primary_regions and job.region in settings.primary_regions:
        score += 14
        reasons.append(f"{job.region} is a primary target region")

    large_company = _is_large_company(job.company, settings.large_companies)
    if large_company:
        score += 15
        reasons.append("Large-company or strong engineering-brand signal")

    salary = _highest_salary_millions(text)
    meets_salary = salary is not None and salary >= settings.min_compensation_millions
    if meets_salary:
        score += min(14, int(salary))
        reasons.append(f"Compensation signal around {salary:g}M+")

    if job.source.startswith(DIRECT_SOURCE_PREFIXES):
        score += 6
        reasons.append("Direct company/ATS source")

    if any(term in title_lower for term in SENIOR_TERMS):
        score -= 32
        risks.append("Title suggests seniority above the preferred level")

    years = _minimum_years(text)
    if years >= 5:
        score -= 25
        risks.append(f"JD appears to request at least {years} years of experience")
    elif years >= 3:
        score -= 12
        risks.append(f"JD appears to request around {years}+ years of experience")

    if any(term in text for term in CUSTOMER_TERMS):
        score -= 20
        risks.append("JD contains customer-facing or account-facing signals")
    if any(term in title_lower for term in CUSTOMER_TITLE_TERMS):
        score -= 45
        risks.insert(0, "Title strongly suggests a customer-facing role")

    if (
        job.region in settings.secondary_regions
        and not large_company
        and not meets_salary
    ):
        score -= 24
        risks.append(
            f"{job.region} is a secondary region without a clear "
            "large-company or compensation signal"
        )

    if any(term in text for term in ("visa", "relocation", "overseas")):
        score += 7
        reasons.append("Visa or overseas-relocation signal")

    if not risks:
        risks.append("Seniority, compensation, and visa details still need confirmation")
    if not reasons:
        reasons.append("Broad technical-role match; retained for discovery coverage")
    return RankedJob(job=job, score=score, reasons=reasons[:3], risks=risks[:2])


def _dedupe_ranked(items: list[RankedJob]) -> list[RankedJob]:
    kept: list[RankedJob] = []
    for item in sorted(items, key=_sort_key, reverse=True):
        if any(_is_duplicate(item, existing) for existing in kept):
            continue
        kept.append(item)
    return kept


def _is_duplicate(left: RankedJob, right: RankedJob) -> bool:
    if _normalize_company(left.job.company) != _normalize_company(right.job.company):
        return False
    ratio = SequenceMatcher(
        None,
        _normalize_text(left.job.title),
        _normalize_text(right.job.title),
    ).ratio()
    return ratio >= 0.88


def _select_with_company_cap(
    items: list[RankedJob], size: int, *, per_company: int
) -> tuple[list[RankedJob], list[RankedJob]]:
    selected: list[RankedJob] = []
    remaining: list[RankedJob] = []
    counts: dict[str, int] = {}
    for item in items:
        company = _normalize_company(item.job.company)
        if len(selected) < size and counts.get(company, 0) < per_company:
            selected.append(item)
            counts[company] = counts.get(company, 0) + 1
        else:
            remaining.append(item)
    return selected, remaining


def _render_markdown(
    inbox: list[RankedJob],
    potential: list[RankedJob],
    *,
    archive_count: int,
) -> str:
    lines = [
        "# Job Inbox",
        "",
        "A zero-LLM shortlist from the broad local job pool.",
        "Only open full JDs for jobs you may actually apply to.",
        "",
        "## Today: Top picks",
        "",
    ]
    for index, item in enumerate(inbox, start=1):
        lines.extend(_render_item(item, index=index, compact=False))
    lines.extend(["## Potential pool", ""])
    for index, item in enumerate(potential, start=1):
        lines.extend(_render_item(item, index=index, compact=True))
    lines.extend(
        [
            "## Background archive",
            "",
            f"- {archive_count} additional deduplicated jobs remain searchable.",
            "- They require no action and are not sent to an agent.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_item(item: RankedJob, *, index: int, compact: bool) -> list[str]:
    job = item.job
    lines = [
        f"### {index}. {job.company} - {job.title}",
        "",
        f"- Score: {item.score}",
        f"- Location: {job.location}",
        f"- Why: {'; '.join(item.reasons)}",
        f"- Main risk: {item.risks[0]}",
        f"- URL: {job.url}",
    ]
    if not compact:
        lines.extend(
            [
                f"- Job ID: `{job.job_id}`",
                "- Decision: `apply / keep / ignore`",
            ]
        )
    lines.append("")
    return lines


def _serialize(item: RankedJob) -> dict[str, Any]:
    return {
        "job_id": item.job.job_id,
        "company": item.job.company,
        "title": item.job.title,
        "location": item.job.location,
        "url": item.job.url,
        "score": item.score,
        "reasons": item.reasons,
        "risks": item.risks,
    }


def _sort_key(item: RankedJob) -> tuple[int, int, str]:
    direct = int(item.job.source.startswith(DIRECT_SOURCE_PREFIXES))
    return item.score, direct, item.job.last_seen.isoformat()


def _is_large_company(company: str, large_companies: set[str]) -> bool:
    if not large_companies:
        return False
    normalized = _normalize_company(company)
    if not normalized:
        return False
    return any(
        name in normalized or normalized in name for name in large_companies
    )


def _normalize_company(value: str) -> str:
    normalized = _normalize_text(value)
    for suffix in (" incorporated", " inc", " corporation", " corp", " ltd", " g k"):
        normalized = normalized.removesuffix(suffix)
    return normalized.strip()


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _minimum_years(text: str) -> int:
    values = [
        int(value)
        for value in re.findall(
            r"(\d{1,2})\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:professional\s+)?experience",
            text,
        )
    ]
    return min(values) if values else 0


def _highest_salary_millions(text: str) -> float | None:
    values: list[float] = []
    for value in re.findall(r"(?:¥|jpy\s*)(\d+(?:\.\d+)?)\s*m", text, flags=re.IGNORECASE):
        values.append(float(value))
    for value in re.findall(
        r"(\d+(?:\.\d+)?)\s*(?:million|百万円)", text, flags=re.IGNORECASE
    ):
        values.append(float(value))
    return max(values) if values else None
