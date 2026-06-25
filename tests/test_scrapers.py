from datetime import date

from rolelens.scrapers import scan_greenhouse_board


def test_scan_greenhouse_board_normalizes_jobs() -> None:
    def fake_fetch(url: str) -> dict[str, object]:
        assert "boards/example/jobs?content=true" in url
        return {
            "jobs": [
                {
                    "id": 123,
                    "title": "Backend Software Engineer",
                    "absolute_url": "https://example.com/jobs/123",
                    "location": {"name": "Tokyo, Japan"},
                    "content": "&lt;p&gt;Build backend APIs.&lt;/p&gt;&lt;p&gt;Own services.&lt;/p&gt;",
                }
            ]
        }

    jobs = scan_greenhouse_board(
        "example",
        {"name": "Example Co", "source_id": "example"},
        date(2026, 6, 25),
        fake_fetch,
    )

    assert len(jobs) == 1
    assert jobs[0].job_id == "greenhouse-example-123"
    assert jobs[0].company == "Example Co"
    assert jobs[0].region == "Japan"
    assert "Build backend APIs." in jobs[0].description
    assert "<p>" not in jobs[0].description


def test_scan_greenhouse_board_filters_source_regions() -> None:
    def fake_fetch(_url: str) -> dict[str, object]:
        return {
            "jobs": [
                {
                    "id": 123,
                    "title": "Backend Software Engineer",
                    "absolute_url": "https://example.com/jobs/123",
                    "location": {"name": "Palo Alto, CA"},
                    "content": "&lt;p&gt;Build backend APIs.&lt;/p&gt;",
                }
            ]
        }

    jobs = scan_greenhouse_board(
        "example",
        {"name": "Example Co", "source_id": "example", "regions": ["Japan"]},
        date(2026, 6, 25),
        fake_fetch,
    )

    assert jobs == []
