from __future__ import annotations

import re
from dataclasses import dataclass

from rolelens.models import JobRecord, PrefilterStatus


POSITIVE_KEYWORDS = [
    "software engineer",
    "machine learning engineer",
    "ml engineer",
    "ai engineer",
    "nlp engineer",
    "llm engineer",
    "data engineer",
    "backend engineer",
    "platform engineer",
    "infrastructure engineer",
    "sre",
    "site reliability engineer",
    "research engineer",
    "applied scientist",
    "quant developer",
    "trading systems engineer",
    "search engineer",
    "ranking engineer",
    "recommendation engineer",
]

WATCH_KEYWORDS = [
    "forward deployed engineer",
    "forward deployed",
    "ai engineer",
    "solutions architect",
    "solution architect",
    "implementation engineer",
    "deployment engineer",
    "customer engineer",
]

NEGATIVE_KEYWORDS = [
    "solution engineer",
    "solutions engineer",
    "customer engineer",
    "support engineer",
    "sales engineer",
    "developer advocate",
    "technical account manager",
    "consultant",
    "implementation engineer",
    "deployment engineer",
    "account executive",
    "marketing",
    "recruiter",
    "business development",
]


@dataclass(frozen=True)
class PrefilterResult:
    status: PrefilterStatus
    reasons: list[str]
    positive_matches: list[str]
    watch_matches: list[str]
    negative_matches: list[str]


def prefilter_job(job: JobRecord) -> PrefilterResult:
    title_text = job.title.lower()
    full_text = f"{job.title}\n{job.description}".lower()

    positive_matches = _find_keywords(full_text, POSITIVE_KEYWORDS)
    watch_matches = _find_keywords(full_text, WATCH_KEYWORDS)
    negative_matches = _find_keywords(full_text, NEGATIVE_KEYWORDS)
    title_negative_matches = _find_keywords(title_text, NEGATIVE_KEYWORDS)
    title_watch_matches = _find_keywords(title_text, WATCH_KEYWORDS)

    if title_watch_matches:
        return PrefilterResult(
            status=PrefilterStatus.WATCH,
            reasons=[
                "Title matches watch keyword(s): "
                + ", ".join(title_watch_matches)
            ],
            positive_matches=positive_matches,
            watch_matches=watch_matches,
            negative_matches=negative_matches,
        )

    if title_negative_matches and not positive_matches:
        return PrefilterResult(
            status=PrefilterStatus.EXCLUDE,
            reasons=[
                "Title matches exclude keyword(s): "
                + ", ".join(title_negative_matches)
            ],
            positive_matches=positive_matches,
            watch_matches=watch_matches,
            negative_matches=negative_matches,
        )

    if title_negative_matches and positive_matches:
        return PrefilterResult(
            status=PrefilterStatus.WATCH,
            reasons=[
                "Mixed coding and customer-facing signals: "
                + ", ".join(title_negative_matches)
            ],
            positive_matches=positive_matches,
            watch_matches=watch_matches,
            negative_matches=negative_matches,
        )

    if positive_matches and negative_matches:
        return PrefilterResult(
            status=PrefilterStatus.WATCH,
            reasons=[
                "Positive coding signals appear with possible customer-facing signals"
            ],
            positive_matches=positive_matches,
            watch_matches=watch_matches,
            negative_matches=negative_matches,
        )

    if positive_matches:
        return PrefilterResult(
            status=PrefilterStatus.INCLUDE,
            reasons=[
                "Matches technical coding keyword(s): "
                + ", ".join(positive_matches[:4])
            ],
            positive_matches=positive_matches,
            watch_matches=watch_matches,
            negative_matches=negative_matches,
        )

    if negative_matches:
        return PrefilterResult(
            status=PrefilterStatus.EXCLUDE,
            reasons=[
                "Matches exclude keyword(s): "
                + ", ".join(negative_matches[:4])
            ],
            positive_matches=positive_matches,
            watch_matches=watch_matches,
            negative_matches=negative_matches,
        )

    return PrefilterResult(
        status=PrefilterStatus.WATCH,
        reasons=["No clear coding or exclude keyword matched"],
        positive_matches=positive_matches,
        watch_matches=watch_matches,
        negative_matches=negative_matches,
    )


def _find_keywords(text: str, keywords: list[str]) -> list[str]:
    return [
        keyword
        for keyword in keywords
        if re.search(rf"\b{re.escape(keyword)}\b", text)
    ]
