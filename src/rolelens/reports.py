from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from rolelens.models import JobRecord, ReviewRecord
from rolelens.storage import SQLiteStore


_TEMPLATES_DIR = Path(__file__).with_name("templates")
_JINJA_ENV = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


@dataclass(frozen=True)
class ReportResult:
    markdown_path: Path
    html_path: Path
    job_count: int
    reviewed_count: int


def generate_demo_report(
    jobs_path: Path,
    reviews_path: Path,
    output_dir: Path,
) -> ReportResult:
    jobs = [job.model_dump(mode="json") for job in _load_jobs(jobs_path)]
    reviews = [review.model_dump(mode="json") for review in _load_reviews(reviews_path)]
    reviews_by_job_id = {review["job_id"]: review for review in reviews}

    return generate_report(
        jobs=jobs,
        reviews_by_job_id=reviews_by_job_id,
        output_dir=output_dir,
        basename="demo",
        title="RoleLens Demo Report",
        lede="Sample report generated from local demo data.",
    )


def generate_personal_report(
    jobs_path: Path,
    reviews_dir: Path,
    output_dir: Path,
) -> ReportResult:
    jobs = [job.model_dump(mode="json") for job in _load_jobs(jobs_path)]
    reviews = [
        review.model_dump(mode="json")
        for review in _load_review_dir(reviews_dir)
    ]
    reviews_by_job_id = {review["job_id"]: review for review in reviews}

    return generate_latest_report_from_records(jobs, reviews_by_job_id, output_dir)


def generate_sqlite_report(
    database_path: Path,
    output_dir: Path,
) -> ReportResult:
    store = SQLiteStore(database_path)
    try:
        jobs = [job.model_dump(mode="json") for job in store.load_jobs()]
        reviews_by_job_id = {
            review.job_id: review.model_dump(mode="json")
            for review in store.load_reviews()
        }
    finally:
        store.close()

    return generate_latest_report_from_records(jobs, reviews_by_job_id, output_dir)


def generate_latest_report_from_records(
    jobs: list[dict[str, Any]],
    reviews_by_job_id: dict[str, dict[str, Any]],
    output_dir: Path,
) -> ReportResult:
    return generate_report(
        jobs=jobs,
        reviews_by_job_id=reviews_by_job_id,
        output_dir=output_dir,
        basename="latest",
        title="RoleLens Report",
        lede="Generated from local jobs and imported agent reviews.",
    )


def generate_report(
    jobs: list[dict[str, Any]],
    reviews_by_job_id: dict[str, dict[str, Any]],
    output_dir: Path,
    basename: str,
    title: str,
    lede: str,
) -> ReportResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / f"{basename}.md"
    html_path = output_dir / f"{basename}.html"

    markdown = _render_markdown(jobs, reviews_by_job_id, title, lede)
    html_report = _render_html(jobs, reviews_by_job_id, title, lede)

    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(html_report, encoding="utf-8")

    return ReportResult(
        markdown_path=markdown_path,
        html_path=html_path,
        job_count=len(jobs),
        reviewed_count=len(reviews_by_job_id),
    )


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return data


def _load_jobs(path: Path) -> list[JobRecord]:
    return [JobRecord.model_validate(item) for item in _load_json_list(path)]


def _load_reviews(path: Path) -> list[ReviewRecord]:
    return [ReviewRecord.model_validate(item) for item in _load_json_list(path)]


def _load_review_dir(path: Path) -> list[ReviewRecord]:
    if not path.exists():
        return []
    reviews: list[ReviewRecord] = []
    for review_path in sorted(path.glob("*.review.json")):
        data = json.loads(review_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object in {review_path}")
        reviews.append(ReviewRecord.model_validate(data))
    return reviews


def _render_markdown(
    jobs: list[dict[str, Any]],
    reviews_by_job_id: dict[str, dict[str, Any]],
    title: str,
    lede: str,
) -> str:
    active_jobs = [job for job in jobs if job.get("status") != "missing"]
    missing_jobs = [job for job in jobs if job.get("status") == "missing"]
    needs_review = [
        job
        for job in active_jobs
        if job["job_id"] not in reviews_by_job_id
        and job.get("prefilter_status") in {"include", "watch"}
    ]
    reviewed_jobs = [
        job for job in active_jobs if job["job_id"] in reviews_by_job_id
    ]
    top_matches = sorted(
        reviewed_jobs,
        key=lambda job: reviews_by_job_id[job["job_id"]].get("fit_score", 0),
        reverse=True,
    )

    lines = [
        f"# {title}",
        "",
        lede,
        "",
        "## Summary",
        "",
        f"- Jobs loaded: {len(jobs)}",
        f"- Reviewed jobs: {len(reviews_by_job_id)}",
        f"- Needs review: {len(needs_review)}",
        f"- Watchlist jobs: {_count_prefilter(active_jobs, 'watch')}",
        f"- Recently missing: {len(missing_jobs)}",
        "",
        "## Top Matches",
        "",
    ]

    _extend_markdown_cards(lines, top_matches, reviews_by_job_id)

    lines.extend(["## Needs Review", ""])
    if needs_review:
        _extend_markdown_cards(lines, needs_review, reviews_by_job_id)
    else:
        lines.append("No active jobs need review.")
        lines.append("")

    lines.extend(["## Watchlist", ""])
    watch_jobs = [job for job in active_jobs if job.get("prefilter_status") == "watch"]
    if watch_jobs:
        _extend_markdown_cards(lines, watch_jobs, reviews_by_job_id)
    else:
        lines.append("No watchlist jobs in this demo.")
        lines.append("")

    lines.extend(["## Recently Missing / Possibly Closed", ""])
    if missing_jobs:
        _extend_markdown_cards(lines, missing_jobs, reviews_by_job_id)
    else:
        lines.append("No recently missing jobs in this demo.")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _extend_markdown_cards(
    lines: list[str],
    jobs: list[dict[str, Any]],
    reviews_by_job_id: dict[str, dict[str, Any]],
) -> None:
    for job in jobs:
        lines.extend(_markdown_job_card(job, reviews_by_job_id.get(job["job_id"])))


def _markdown_job_card(job: dict[str, Any], review: dict[str, Any] | None) -> list[str]:
    lines = [
        f"### {job['company']} - {job['title']}",
        "",
        f"- Location: {job['location']}",
        f"- Source: {job['source']}",
        f"- Prefilter: {job['prefilter_status']}",
        f"- Status: {job['status']}",
        f"- Original JD: {job['url']}",
    ]
    if review:
        lines.extend(
            [
                f"- Category: {review['category']}",
                f"- Fit score: {review['fit_score']}",
                f"- Role type: {review['role_type']}",
                f"- Coding intensity: {review['coding_intensity']}",
                f"- Customer-facing level: {review['customer_facing_level']}",
                f"- Reasons: {'; '.join(review['reasons'])}",
                f"- Risks: {'; '.join(review['risks'])}",
                f"- Prep actions: {'; '.join(review['prep_actions'])}",
            ]
        )
        if review.get("cv_tweaks"):
            lines.append(f"- CV tweaks: {'; '.join(review['cv_tweaks'])}")
    else:
        lines.append("- Review: pending")
    lines.append("")
    return lines


def _render_html(
    jobs: list[dict[str, Any]],
    reviews_by_job_id: dict[str, dict[str, Any]],
    title: str,
    lede: str,
) -> str:
    context = _build_report_context(jobs, reviews_by_job_id, title, lede)
    template = _JINJA_ENV.get_template("report.html.j2")
    return template.render(context).rstrip() + "\n"


def _build_report_context(
    jobs: list[dict[str, Any]],
    reviews_by_job_id: dict[str, dict[str, Any]],
    title: str,
    lede: str,
) -> dict[str, Any]:
    active_jobs = [job for job in jobs if job.get("status") != "missing"]
    missing_jobs = [job for job in jobs if job.get("status") == "missing"]
    reviewed_jobs = [
        job for job in active_jobs if job["job_id"] in reviews_by_job_id
    ]
    needs_review = [
        job
        for job in active_jobs
        if job["job_id"] not in reviews_by_job_id
        and job.get("prefilter_status") in {"include", "watch"}
    ]
    top_matches = sorted(
        reviewed_jobs,
        key=lambda job: reviews_by_job_id[job["job_id"]].get("fit_score", 0),
        reverse=True,
    )
    watch_jobs = [
        job for job in active_jobs if job.get("prefilter_status") == "watch"
    ]

    return {
        "title": title,
        "lede": lede,
        "metrics": [
            {"label": "Jobs loaded", "value": len(jobs)},
            {"label": "Reviewed", "value": len(reviews_by_job_id)},
            {"label": "Needs review", "value": len(needs_review)},
            {"label": "Watchlist", "value": _count_prefilter(active_jobs, "watch")},
            {"label": "Recently missing", "value": len(missing_jobs)},
        ],
        "sections": [
            _report_section("01", "Top Matches", top_matches, reviews_by_job_id),
            _report_section("02", "Needs Review", needs_review, reviews_by_job_id),
            _report_section("03", "Watchlist", watch_jobs, reviews_by_job_id),
            _report_section(
                "04",
                "Recently Missing / Possibly Closed",
                missing_jobs,
                reviews_by_job_id,
            ),
        ],
    }


def _report_section(
    number: str,
    title: str,
    jobs: list[dict[str, Any]],
    reviews_by_job_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "jobs": [
            _report_job(job, reviews_by_job_id.get(job["job_id"]))
            for job in jobs
        ],
    }


def _report_job(
    job: dict[str, Any], review: dict[str, Any] | None
) -> dict[str, Any]:
    prefilter_status = job["prefilter_status"]
    item = {
        "company": job["company"],
        "title": job["title"],
        "location": job["location"],
        "source": job["source"],
        "status": job["status"],
        "url": job["url"],
        "prefilter_status": prefilter_status,
        "prefilter_label": _prefilter_label(prefilter_status),
        "review": review,
        "fit_score_display": "-",
        "score_label": "pending",
        "detail_blocks": [],
        "cv_tweaks": [],
    }
    if review is not None:
        item.update(
            {
                "fit_score_display": int(review["fit_score"]),
                "score_label": "fit score",
                "detail_blocks": [
                    {"title": "Reasons", "items": review["reasons"]},
                    {"title": "Risks", "items": review["risks"]},
                    {"title": "Prep", "items": review["prep_actions"]},
                ],
                "cv_tweaks": review.get("cv_tweaks", []),
            }
        )
    return item


def _prefilter_label(status: str) -> str:
    return {
        "include": "Review",
        "watch": "Watch",
        "exclude": "Skip",
    }.get(status, status)


def _count_prefilter(jobs: list[dict[str, Any]], status: str) -> int:
    return sum(1 for job in jobs if job.get("prefilter_status") == status)
