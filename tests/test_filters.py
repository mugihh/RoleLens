from datetime import date

from rolelens.filters import prefilter_job
from rolelens.models import JobRecord, PrefilterStatus


def make_job(title: str, description: str) -> JobRecord:
    return JobRecord(
        job_id="job-1",
        company="Example",
        title=title,
        location="Tokyo, Japan",
        region="Japan",
        url="https://example.com/job",
        source="test",
        prefilter_status=PrefilterStatus.WATCH,
        status="active",
        first_seen=date(2026, 6, 24),
        last_seen=date(2026, 6, 24),
        description=description,
    )


def test_prefilter_includes_clear_backend_engineering_role() -> None:
    job = make_job(
        "Backend Software Engineer",
        "Build product services, APIs, and distributed systems.",
    )

    result = prefilter_job(job)

    assert result.status == PrefilterStatus.INCLUDE
    assert "software engineer" in result.positive_matches


def test_prefilter_watches_forward_deployed_ai_engineer() -> None:
    job = make_job(
        "Forward Deployed AI Engineer",
        "Prototype LLM systems with strategic customers.",
    )

    result = prefilter_job(job)

    assert result.status == PrefilterStatus.WATCH
    assert "forward deployed" in result.watch_matches
    assert "ai engineer" in result.watch_matches


def test_prefilter_excludes_sales_engineer_role() -> None:
    job = make_job(
        "Sales Engineer",
        "Support account executives and customer sales motions.",
    )

    result = prefilter_job(job)

    assert result.status == PrefilterStatus.EXCLUDE
    assert "sales engineer" in result.negative_matches


def test_prefilter_watches_mixed_positive_and_customer_facing_signals() -> None:
    job = make_job(
        "Software Engineer, Customer Integrations",
        "Build backend services while supporting implementation engineer workflows.",
    )

    result = prefilter_job(job)

    assert result.status == PrefilterStatus.WATCH
    assert "software engineer" in result.positive_matches
    assert "implementation engineer" in result.negative_matches


def test_prefilter_watches_ambiguous_roles() -> None:
    job = make_job(
        "Technical Specialist",
        "Help teams evaluate AI systems and architecture choices.",
    )

    result = prefilter_job(job)

    assert result.status == PrefilterStatus.WATCH
    assert result.reasons == ["No clear coding or exclude keyword matched"]
