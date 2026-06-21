from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DemoReportResult:
    markdown_path: Path
    html_path: Path
    job_count: int
    reviewed_count: int


def generate_demo_report(
    jobs_path: Path,
    reviews_path: Path,
    output_dir: Path,
) -> DemoReportResult:
    jobs = _load_json_list(jobs_path)
    reviews = _load_json_list(reviews_path)
    reviews_by_job_id = {review["job_id"]: review for review in reviews}

    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "demo.md"
    html_path = output_dir / "demo.html"

    markdown = _render_markdown(jobs, reviews_by_job_id)
    html_report = _render_html(jobs, reviews_by_job_id)

    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(html_report, encoding="utf-8")

    return DemoReportResult(
        markdown_path=markdown_path,
        html_path=html_path,
        job_count=len(jobs),
        reviewed_count=len(reviews),
    )


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return data


def _render_markdown(
    jobs: list[dict[str, Any]],
    reviews_by_job_id: dict[str, dict[str, Any]],
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
        "# RoleLens Demo Report",
        "",
        "Generated from local sample data. No internet access, private CV, live coding-agent review, or scraper output was used.",
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
    else:
        lines.append("- Review: pending")
    lines.append("")
    return lines


def _render_html(
    jobs: list[dict[str, Any]],
    reviews_by_job_id: dict[str, dict[str, Any]],
) -> str:
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

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RoleLens Demo Report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fb;
      --panel: #ffffff;
      --text: #1f2937;
      --muted: #6b7280;
      --line: #d8dee9;
      --accent: #0f766e;
      --accent-soft: #e6f4f1;
      --warn: #9a5b00;
      --warn-soft: #fff4db;
      --avoid: #9f1239;
      --avoid-soft: #ffe4ea;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{
      width: min(1120px, calc(100% - 32px));
      margin: 0 auto;
      padding: 40px 0 56px;
    }}
    header {{
      display: grid;
      gap: 12px;
      margin-bottom: 28px;
    }}
    h1, h2, h3, p {{ margin-top: 0; }}
    h1 {{ margin-bottom: 0; font-size: 34px; letter-spacing: 0; }}
    h2 {{ margin: 32px 0 14px; font-size: 22px; }}
    h3 {{ margin-bottom: 8px; font-size: 18px; }}
    a {{ color: var(--accent); }}
    .lede {{ max-width: 720px; color: var(--muted); }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin: 22px 0;
    }}
    .metric, .job {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .metric {{ padding: 14px; }}
    .metric strong {{ display: block; font-size: 24px; }}
    .metric span {{ color: var(--muted); font-size: 13px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 14px;
    }}
    .job {{ padding: 18px; }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 12px;
      color: var(--muted);
      font-size: 13px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 3px 9px;
      background: #eef1f6;
      color: #394150;
      font-size: 12px;
      font-weight: 650;
    }}
    .category-a, .include {{ background: var(--accent-soft); color: var(--accent); }}
    .category-b, .watch {{ background: var(--warn-soft); color: var(--warn); }}
    .exclude {{ background: var(--avoid-soft); color: var(--avoid); }}
    .score {{ font-size: 32px; font-weight: 750; margin: 8px 0; }}
    .section-list {{ padding-left: 18px; margin: 8px 0 0; }}
    .section-list li {{ margin-bottom: 4px; }}
    .empty {{
      padding: 18px;
      border: 1px dashed var(--line);
      border-radius: 8px;
      color: var(--muted);
      background: rgba(255, 255, 255, 0.55);
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>RoleLens Demo Report</h1>
      <p class="lede">Generated from local sample data. No internet access, private CV, live coding-agent review, or scraper output was used.</p>
    </header>
    <section class="summary" aria-label="Report summary">
      {_metric("Jobs loaded", len(jobs))}
      {_metric("Reviewed", len(reviews_by_job_id))}
      {_metric("Needs review", len(needs_review))}
      {_metric("Watchlist", _count_prefilter(active_jobs, "watch"))}
      {_metric("Recently missing", len(missing_jobs))}
    </section>
    {_html_section("Top Matches", top_matches, reviews_by_job_id)}
    {_html_section("Needs Review", needs_review, reviews_by_job_id)}
    {_html_section("Watchlist", [job for job in active_jobs if job.get("prefilter_status") == "watch"], reviews_by_job_id)}
    {_html_section("Recently Missing / Possibly Closed", missing_jobs, reviews_by_job_id)}
  </main>
</body>
</html>
"""


def _metric(label: str, value: int) -> str:
    return f'<div class="metric"><strong>{value}</strong><span>{html.escape(label)}</span></div>'


def _html_section(
    title: str,
    jobs: list[dict[str, Any]],
    reviews_by_job_id: dict[str, dict[str, Any]],
) -> str:
    if not jobs:
        return f'<section><h2>{html.escape(title)}</h2><div class="empty">No jobs in this section.</div></section>'
    cards = "\n".join(
        _html_job_card(job, reviews_by_job_id.get(job["job_id"])) for job in jobs
    )
    return f'<section><h2>{html.escape(title)}</h2><div class="grid">{cards}</div></section>'


def _html_job_card(job: dict[str, Any], review: dict[str, Any] | None) -> str:
    prefilter = html.escape(job["prefilter_status"])
    review_html = '<p class="empty">Review pending.</p>'
    if review:
        review_html = f"""
        <span class="badge category-{html.escape(review['category']).lower()}">Category {html.escape(review['category'])}</span>
        <div class="score">{int(review['fit_score'])}</div>
        <p><strong>{html.escape(review['role_type'])}</strong></p>
        <p>Coding intensity: {html.escape(review['coding_intensity'])}<br>
        Customer-facing level: {html.escape(review['customer_facing_level'])}</p>
        {_html_list("Reasons", review["reasons"])}
        {_html_list("Risks", review["risks"])}
        {_html_list("Prep", review["prep_actions"])}
        """

    return f"""
    <article class="job">
      <h3>{html.escape(job['company'])} - {html.escape(job['title'])}</h3>
      <div class="meta">
        <span>{html.escape(job['location'])}</span>
        <span>{html.escape(job['source'])}</span>
        <span>{html.escape(job['status'])}</span>
      </div>
      <p><span class="badge {prefilter}">{prefilter}</span></p>
      {review_html}
      <p><a href="{html.escape(job['url'])}">Original JD</a></p>
    </article>
    """


def _html_list(title: str, items: list[str]) -> str:
    escaped_items = "".join(f"<li>{html.escape(item)}</li>" for item in items)
    return f"<p><strong>{html.escape(title)}</strong></p><ul class=\"section-list\">{escaped_items}</ul>"


def _count_prefilter(jobs: list[dict[str, Any]], status: str) -> int:
    return sum(1 for job in jobs if job.get("prefilter_status") == status)
