from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rolelens.filters import PrefilterResult, prefilter_job
from rolelens.models import JobRecord, PrefilterStatus


@dataclass(frozen=True)
class ReviewQueueResult:
    output_dir: Path
    exported_count: int
    skipped_count: int
    messages: list[str]


def export_review_queue(
    jobs_path: Path,
    output_dir: Path,
) -> ReviewQueueResult:
    jobs = _load_jobs(jobs_path)
    return export_review_queue_for_jobs(jobs, output_dir)


def export_review_queue_for_jobs(
    jobs: list[JobRecord],
    output_dir: Path,
    queue_states: dict[str, str] | None = None,
) -> ReviewQueueResult:
    queue_states = queue_states or {}
    output_dir.mkdir(parents=True, exist_ok=True)

    exported_count = 0
    skipped_count = 0
    messages: list[str] = []

    for job in jobs:
        queue_state = queue_states.get(job.job_id, "unreviewed")
        if queue_state not in {"new", "changed", "unreviewed", "needs_rereview"}:
            skipped_count += 1
            messages.append(f"SKIP {job.job_id}: queue_state={queue_state}")
            continue

        prefilter = prefilter_job(job)
        if prefilter.status == PrefilterStatus.EXCLUDE:
            skipped_count += 1
            messages.append(f"SKIP {job.job_id}: {', '.join(prefilter.reasons)}")
            continue

        normalized_job = job.model_copy(update={"prefilter_status": prefilter.status})
        job_path = output_dir / f"{normalized_job.job_id}.job.json"
        prompt_path = output_dir / f"{normalized_job.job_id}.prompt.md"

        job_payload = normalized_job.model_dump(mode="json")
        job_payload["prefilter_reasons"] = prefilter.reasons
        job_payload["prefilter_matches"] = {
            "positive": prefilter.positive_matches,
            "watch": prefilter.watch_matches,
            "negative": prefilter.negative_matches,
        }
        job_payload["queue_state"] = queue_state

        job_path.write_text(
            json.dumps(job_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        prompt_path.write_text(
            _render_review_prompt(normalized_job, prefilter, queue_state),
            encoding="utf-8",
        )
        exported_count += 1
        messages.append(f"EXPORT {normalized_job.job_id}: {prefilter.status}")

    return ReviewQueueResult(
        output_dir=output_dir,
        exported_count=exported_count,
        skipped_count=skipped_count,
        messages=messages,
    )


def _load_jobs(path: Path) -> list[JobRecord]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return [JobRecord.model_validate(item) for item in data]


def _render_review_prompt(
    job: JobRecord,
    prefilter: PrefilterResult,
    queue_state: str,
) -> str:
    warning = ""
    if prefilter.status == PrefilterStatus.WATCH:
        warning = (
            "\n## Prefilter Warning\n\n"
            "This role is on the watchlist. Pay special attention to whether it "
            "is a real coding role or primarily customer-facing.\n"
        )

    return f"""# RoleLens JD Review

Review this job description using the candidate profile and private CV context.

Do not browse or perform external salary, visa, sponsorship, or company research
unless the user explicitly authorized it. Leave `external_research` empty unless
external research was explicitly authorized.

## Job Metadata

- Job ID: `{job.job_id}`
- Company: {job.company}
- Title: {job.title}
- Location: {job.location}
- Region: {job.region}
- Source: {job.source}
- URL: {job.url}
- Prefilter status: {prefilter.status}
- Prefilter reasons: {'; '.join(prefilter.reasons)}
- Queue state: {queue_state}
{warning}
## Rubric

Judge:

- Is this actually a coding role?
- Is it product/platform/internal engineering, or customer-facing?
- How much long-term code ownership is implied?
- Does it involve production systems?
- Is NLP, LLM, or ML relevant?
- Is backend, platform, or data infrastructure experience required?
- Is the seniority realistic for an early-career master's student?
- Does the role support the user's target regions, language needs, and work authorization preferences?
- What should the candidate prepare before applying?

Use categories:

- `A`: priority apply
- `B`: conditional
- `C`: avoid by default

## Expected Output

Write one JSON file to `review_results/{job.job_id}.review.json` with this shape:

```json
{{
  "job_id": "{job.job_id}",
  "reviewed_at": "YYYY-MM-DD",
  "category": "A",
  "fit_score": 86,
  "role_type": "Product ML Engineer",
  "is_real_coding_role": true,
  "coding_intensity": "high",
  "customer_facing_level": "low",
  "reasons": ["Reason grounded in the JD"],
  "risks": ["Risk or tradeoff grounded in the JD"],
  "prep_actions": ["Concrete prep action"],
  "dimensions": {{
    "nlp_relevance": "high",
    "ml_relevance": "high",
    "english_friendliness": "unknown",
    "visa_or_pr_relevance": "unknown",
    "compensation_signal": "unknown"
  }},
  "compensation_notes": "No salary research performed.",
  "external_research": []
}}
```

## Job Description

{job.description}
"""
