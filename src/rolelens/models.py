from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PrefilterStatus(StrEnum):
    INCLUDE = "include"
    WATCH = "watch"
    EXCLUDE = "exclude"


class JobStatus(StrEnum):
    ACTIVE = "active"
    MISSING = "missing"


class ReviewCategory(StrEnum):
    A = "A"
    B = "B"
    C = "C"


class SignalLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class JobRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    company: str = Field(min_length=1)
    title: str = Field(min_length=1)
    location: str = Field(min_length=1)
    region: str = Field(min_length=1)
    url: str = Field(min_length=1)
    source: str = Field(min_length=1)
    prefilter_status: PrefilterStatus
    status: JobStatus = JobStatus.ACTIVE
    first_seen: date
    last_seen: date
    description: str = Field(min_length=1)

    @field_validator("job_id")
    @classmethod
    def normalize_job_id(cls, value: str) -> str:
        return value.strip()


class ReviewRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    reviewed_at: date
    category: ReviewCategory
    fit_score: int = Field(ge=0, le=100)
    role_type: str = Field(min_length=1)
    is_real_coding_role: bool
    coding_intensity: SignalLevel
    customer_facing_level: SignalLevel
    reasons: list[str] = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)
    prep_actions: list[str] = Field(default_factory=list)
    cv_tweaks: list[str] = Field(default_factory=list)
    dimensions: dict[str, str] = Field(default_factory=dict)
    compensation_notes: str = ""
    external_research: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("job_id")
    @classmethod
    def normalize_job_id(cls, value: str) -> str:
        return value.strip()


def review_consistency_warnings(review: ReviewRecord) -> list[str]:
    warnings: list[str] = []

    if review.category == ReviewCategory.A and review.fit_score < 70:
        warnings.append("category A usually expects fit_score >= 70")
    if review.category == ReviewCategory.B and (
        review.fit_score < 40 or review.fit_score > 85
    ):
        warnings.append("category B usually expects 40 <= fit_score <= 85")
    if review.category == ReviewCategory.C and review.fit_score > 70:
        warnings.append("category C usually expects fit_score <= 70")
    if not review.is_real_coding_role and review.category == ReviewCategory.A:
        warnings.append("category A usually requires is_real_coding_role = true")

    return warnings


def validate_reviews_reference_known_jobs(
    jobs: list[JobRecord],
    reviews: list[ReviewRecord],
) -> list[str]:
    known_job_ids = {job.job_id for job in jobs}
    warnings: list[str] = []

    for review in reviews:
        if review.job_id not in known_job_ids:
            warnings.append(f"review references unknown job_id: {review.job_id}")

    return warnings
