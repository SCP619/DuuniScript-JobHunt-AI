from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.adapters.robots import parse_robots
from app.adapters.web_fetch import FetchError
from tests.fake_web import FakeWeb, job_posting_page, synthetic_posting

# ---------- Parser (RFC 9309) ----------


@pytest.mark.parametrize(
    ("robots", "path", "allowed"),
    [
        ("", "/anything", True),
        ("User-agent: *\nDisallow: /", "/tyopaikat/tyo/123", False),
        ("User-agent: *\nDisallow:", "/x", True),  # empty Disallow allows all
        ("User-agent: *\nDisallow: /admin/", "/jobs/1", True),
        ("User-agent: *\nDisallow: /admin/", "/admin/x", False),
        # Longest match wins; Allow wins ties.
        ("User-agent: *\nDisallow: /jobs/\nAllow: /jobs/public/", "/jobs/public/1", True),
        ("User-agent: *\nAllow: /jobs/\nDisallow: /jobs/private/", "/jobs/private/1", False),
        ("User-agent: *\nDisallow: /a\nAllow: /a", "/a", True),
        # Wildcards and end anchors.
        ("User-agent: *\nDisallow: /node/*/apply-external", "/node/55/apply-external", False),
        ("User-agent: *\nDisallow: /node/*/apply-external", "/node/55/view", True),
        ("User-agent: *\nDisallow: /*.pdf$", "/files/cv.pdf", False),
        ("User-agent: *\nDisallow: /*.pdf$", "/files/cv.pdf?x=1", True),
        ("User-agent: *\nDisallow: /?q=admin/", "/?q=admin/users", False),
        # Our own group overrides the * group; other bots' groups are ignored.
        ("User-agent: *\nDisallow: /\n\nUser-agent: DuuniScript\nAllow: /", "/x", True),
        ("User-agent: *\nDisallow: /\n\nUser-agent: Googlebot\nAllow: /", "/x", False),
        ("User-agent: Googlebot\nUser-agent: *\nDisallow: /private", "/private/1", False),
        # Comments and case-insensitive keys.
        ("# hi\nUSER-AGENT: *  # all\nDISALLOW: /secret # no", "/secret", False),
    ],
)
def test_parse_and_match(robots: str, path: str, allowed: bool) -> None:
    assert parse_robots(robots).allows("https://example.com" + path) is allowed


def test_duunitori_style_rules_block_generic_agents() -> None:
    robots = "User-agent: *\nDisallow: /\nUser-agent: AhrefsBot\nDisallow:\nDisallow: /api/\n"
    assert parse_robots(robots).allows("https://example.com/tyopaikat/tyo/abc-123") is False


# ---------- Fetcher integration ----------


JOB = "https://jobs.example.com/positions/1"


def test_disallowed_page_is_not_fetched() -> None:
    web = FakeWeb()
    web.add_robots("https://jobs.example.com", "User-agent: *\nDisallow: /positions/")
    web.add_html(JOB, "<html></html>")
    with pytest.raises(FetchError) as exc:
        web.fetcher().fetch_html(JOB)
    assert exc.value.reason == "robots_disallowed"
    assert exc.value.status_code == 422
    assert web.requests == []


@pytest.mark.parametrize(("status", "fetched"), [(404, True), (410, True), (403, True), (500, False), (503, False)])
def test_robots_http_status_handling(status: int, fetched: bool) -> None:
    web = FakeWeb()
    web.add_robots("https://jobs.example.com", "", status=status)
    web.add_html(JOB, "<html>ok</html>")
    if fetched:
        web.fetcher().fetch_html(JOB)
        assert web.requests == [JOB]
    else:
        with pytest.raises(FetchError) as exc:
            web.fetcher().fetch_html(JOB)
        assert exc.value.reason == "robots_disallowed"
        assert web.requests == []


def test_redirect_to_disallowed_path_is_refused() -> None:
    web = FakeWeb()
    web.add_robots("https://other.example.com", "User-agent: *\nDisallow: /")
    web.add_redirect(JOB, "https://other.example.com/job/1")
    with pytest.raises(FetchError) as exc:
        web.fetcher().fetch_html(JOB)
    assert exc.value.reason == "robots_disallowed"
    assert web.requests == [JOB]


def test_robots_is_cached_per_origin() -> None:
    web = FakeWeb()
    web.add_html(JOB, "<html></html>")
    web.add_html(JOB + "0", "<html></html>")
    fetcher = web.fetcher()
    fetcher.fetch_html(JOB)
    fetcher.fetch_html(JOB + "0")
    assert web.robots_requests == ["https://jobs.example.com/robots.txt"]


def test_import_api_reports_robots_refusal(client: TestClient, fake_web: FakeWeb) -> None:
    fake_web.add_robots("https://jobs.example.com", "User-agent: *\nDisallow: /")
    fake_web.add_html(JOB, job_posting_page(synthetic_posting()))
    response = client.post("/api/v1/jobs/import", json={"url": JOB})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "fetch_failed"
    assert error["details"]["reason"] == "robots_disallowed"
    assert "manually" in error["message"]
    assert fake_web.requests == []
    assert client.get("/api/v1/jobs").json()["total"] == 0
