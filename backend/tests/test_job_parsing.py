"""Unit tests for URL handling, the safe fetcher and the JSON-LD JobPosting parser."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

from app.adapters.job_sources.jsonld import NoJobPosting, html_to_text, parse_job_posting
from app.adapters.web_fetch import FetchError
from app.core.errors import AppError
from app.persistence.models import EmploymentType, WorkMode
from app.services.urls import canonicalize_url, validate_http_url
from tests.fake_web import FakeWeb, job_posting_page, synthetic_posting

# ---------- URLs ----------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("HTTPS://Jobs.Example.COM/Job/123/?utm_source=x&b=2&a=1#apply", "https://jobs.example.com/Job/123?a=1&b=2"),
        ("https://example.com:443/", "https://example.com/"),
        ("http://example.com:8080/x", "http://example.com:8080/x"),
        ("https://example.com/job?id=5&fbclid=abc&gclid=z", "https://example.com/job?id=5"),
    ],
)
def test_canonicalize_url(raw: str, expected: str) -> None:
    assert canonicalize_url(raw) == expected


@pytest.mark.parametrize(
    "bad",
    ["", "javascript:alert(1)", "file:///C:/Windows/win.ini", "ftp://example.com/x", "https://user:pw@example.com/",
     "/relative/path", "https://example.com:99999/", "https://" + "a" * 2000 + ".com"],
)
def test_validate_http_url_rejects(bad: str) -> None:
    with pytest.raises(AppError):
        validate_http_url(bad)


# ---------- Safe fetcher ----------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.5/job",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://localhost/",
        "http://printer.local/",
        "http://100.64.0.1/",
    ],
)
def test_fetcher_blocks_private_destinations(url: str) -> None:
    web = FakeWeb()
    with pytest.raises(FetchError) as exc:
        web.fetcher().fetch_html(url)
    assert exc.value.reason == "blocked_address"
    assert web.requests == []


def test_fetcher_blocks_hostnames_resolving_to_private_addresses() -> None:
    web = FakeWeb(dns={"intranet.example.com": ["10.1.2.3"]})
    with pytest.raises(FetchError) as exc:
        web.fetcher().fetch_html("https://intranet.example.com/job")
    assert exc.value.reason == "blocked_address"
    assert web.requests == []


def test_fetcher_blocks_non_standard_ports() -> None:
    with pytest.raises(FetchError) as exc:
        FakeWeb().fetcher().fetch_html("https://example.com:8443/job")
    assert exc.value.reason == "blocked_port"


def test_fetcher_blocks_redirect_to_private_address() -> None:
    web = FakeWeb()
    web.add_redirect("https://jobs.example.com/a", "http://127.0.0.1/admin")
    with pytest.raises(FetchError) as exc:
        web.fetcher().fetch_html("https://jobs.example.com/a")
    assert exc.value.reason == "blocked_address"
    assert web.requests == ["https://jobs.example.com/a"]


def test_fetcher_follows_safe_redirects() -> None:
    web = FakeWeb()
    web.add_redirect("https://jobs.example.com/short", "/jobs/123")
    web.add_html("https://jobs.example.com/jobs/123", "<html>ok</html>")
    result = web.fetcher().fetch_html("https://jobs.example.com/short")
    assert result.final_url == "https://jobs.example.com/jobs/123"


def test_fetcher_redirect_loop() -> None:
    web = FakeWeb()
    web.add_redirect("https://example.com/a", "https://example.com/b")
    web.add_redirect("https://example.com/b", "https://example.com/a")
    with pytest.raises(FetchError) as exc:
        web.fetcher(max_redirects=3).fetch_html("https://example.com/a")
    assert exc.value.reason == "too_many_redirects"


@pytest.mark.parametrize(
    ("setup", "reason"),
    [
        (lambda w: w.add_html("https://example.com/x", "{}", content_type="application/json"), "not_html"),
        (lambda w: w.add_html("https://example.com/x", "gone", status=410), "http_status"),
        (lambda w: w.add_html("https://example.com/x", "a" * 5000), "too_large"),
    ],
)
def test_fetcher_failures(setup, reason: str) -> None:  # noqa: ANN001
    web = FakeWeb()
    setup(web)
    with pytest.raises(FetchError) as exc:
        web.fetcher(max_bytes=1000).fetch_html("https://example.com/x")
    assert exc.value.reason == reason


def test_fetcher_sends_honest_user_agent_without_personal_data() -> None:
    import httpx

    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")

    from app.adapters.web_fetch import SafeFetcher

    SafeFetcher(transport=httpx.MockTransport(handler), resolver=lambda h: ["93.184.216.34"]).fetch_html(
        "https://example.com/"
    )
    assert seen["user-agent"].startswith("DuuniScript/")
    assert "cookie" not in seen and "authorization" not in seen


# ---------- JSON-LD parser ----------


def test_parse_full_posting() -> None:
    parsed = parse_job_posting(job_posting_page(synthetic_posting()))
    assert parsed.title == "Ohjelmistokehittäjä (synthetic)"
    assert parsed.company == "Esimerkki Oy"
    assert parsed.description == "Synthetic role.\n\n- Python\n- SQL"
    assert parsed.location == "Turku, Varsinais-Suomi, FI"
    assert parsed.employment_type == EmploymentType.FULL_TIME
    assert parsed.work_mode is None  # never assumed
    assert parsed.salary_text == "3500–4200 EUR / month"
    assert parsed.external_id == "JOB-123"
    assert parsed.language == "fi"
    assert parsed.published_on == date(2026, 11, 1)
    assert parsed.deadline_on == date(2026, 11, 30)
    assert parsed.deadline_at == datetime(2026, 11, 30, 21, 59, tzinfo=timezone.utc)


def test_missing_dates_stay_unknown() -> None:
    parsed = parse_job_posting(job_posting_page(synthetic_posting(datePosted=None, validThrough=None)))
    assert parsed.published_on is None
    assert parsed.deadline_on is None
    assert parsed.deadline_at is None


def test_deadline_without_timezone_keeps_only_the_date() -> None:
    parsed = parse_job_posting(job_posting_page(synthetic_posting(validThrough="2026-12-01T16:00:00")))
    assert parsed.deadline_on == date(2026, 12, 1)
    assert parsed.deadline_at is None


def test_garbage_dates_ignored() -> None:
    parsed = parse_job_posting(job_posting_page(synthetic_posting(datePosted="last week", validThrough="2026-13-45")))
    assert parsed.published_on is None and parsed.deadline_on is None


def test_graph_and_type_list_and_remote() -> None:
    posting = synthetic_posting(**{"@type": ["JobPosting", "Thing"], "jobLocationType": "TELECOMMUTE"})
    page = job_posting_page({"@context": "https://schema.org", "@graph": [{"@type": "WebPage"}, posting]})
    parsed = parse_job_posting(page)
    assert parsed.work_mode == WorkMode.REMOTE


def test_multiple_locations_and_string_org() -> None:
    posting = synthetic_posting(
        hiringOrganization="Esimerkki Oy",
        jobLocation=[
            {"address": {"addressLocality": "Turku", "addressCountry": {"name": "Finland"}}},
            {"address": {"addressLocality": "Helsinki", "addressCountry": "Finland"}},
            {"address": {"addressLocality": "Turku", "addressCountry": {"name": "Finland"}}},
        ],
    )
    parsed = parse_job_posting(job_posting_page(posting))
    assert parsed.company == "Esimerkki Oy"
    assert parsed.location == "Turku, Finland; Helsinki, Finland"


def test_escaped_html_description() -> None:
    parsed = parse_job_posting(job_posting_page(synthetic_posting(description="&lt;p&gt;Hello &amp;amp; welcome&lt;/p&gt;")))
    assert parsed.description == "Hello & welcome"


def test_malformed_block_skipped_and_valid_block_used() -> None:
    page = (
        '<script type="application/ld+json">{not json</script>'
        f'<script type="application/ld+json">{json.dumps(synthetic_posting())}</script>'
    )
    assert parse_job_posting(page).title.startswith("Ohjelmistokehittäjä")


@pytest.mark.parametrize(
    ("page", "reason"),
    [
        ("<html><body>No data</body></html>", "no_structured_data"),
        (job_posting_page({"@type": "Organization", "name": "x"}), "no_job_posting"),
        (job_posting_page(synthetic_posting(title=None)), "missing_title_or_company"),
        (job_posting_page(synthetic_posting(hiringOrganization=None)), "missing_title_or_company"),
    ],
)
def test_no_usable_posting(page: str, reason: str) -> None:
    with pytest.raises(NoJobPosting) as exc:
        parse_job_posting(page)
    assert exc.value.reason == reason


def test_script_and_style_content_removed_from_description() -> None:
    text = html_to_text("<p>Role</p><script>alert('x')</script><style>p{}</style><p>Details</p>")
    assert text == "Role\n\nDetails"


# ---------- Shapes observed on real Finnish job boards (synthetic values) ----------


def test_finnish_free_text_employment_type_and_text_salary() -> None:
    """Kuntarekry/Valtiolle style: Finnish free-text employment type, salary as a sentence."""
    posting = synthetic_posting(
        employmentType="Kokoaikatyö, 3-vuorotyö, Työpaikka, Vakinainen, Työsuhde",
        baseSalary={"@type": "MonetaryAmount", "currency": "EUR", "value": "Tehtäväkohtainen palkka 3000 eur/kk"},
        datePosted="2026-11-10T00:00:00+02:00",
    )
    parsed = parse_job_posting(job_posting_page(posting))
    assert parsed.employment_type == EmploymentType.FULL_TIME
    assert parsed.salary_text == "Tehtäväkohtainen palkka 3000 eur/kk"  # publisher's wording, nothing appended
    assert parsed.published_on == date(2026, 11, 10)  # date as published, not shifted to UTC


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Vakinainen, Virkasuhde, Asiantuntijataso", None),  # permanence words are not working time
        ("Osa-aikatyö, Määräaikainen", EmploymentType.PART_TIME),
        ("Heltid, Tillsvidare", EmploymentType.FULL_TIME),
        ("Kokoaikatyö, Osa-aikatyö", None),  # contradictory: stay unknown
        (["FULL_TIME", "OTHER"], EmploymentType.FULL_TIME),
        ("FULL_TIME, PART_TIME", EmploymentType.FULL_TIME),
        ("Harjoittelu", EmploymentType.INTERNSHIP),
    ],
)
def test_employment_type_mapping(value, expected) -> None:  # noqa: ANN001
    parsed = parse_job_posting(job_posting_page(synthetic_posting(employmentType=value)))
    assert parsed.employment_type == expected


@pytest.mark.parametrize(
    ("salary", "expected"),
    [
        # Jobly style: structure present but amounts empty -> no salary, not "EUR".
        ({"currency": "EUR", "value": {"minValue": "", "maxValue": "", "unitText": ""}}, None),
        ({"currency": "EUR", "value": {"minValue": "n/a", "unitText": "MONTH"}}, None),
        ({"currency": "EUR", "value": {"minValue": 3000, "maxValue": 3000, "unitText": "MONTH"}}, "3000 EUR / month"),
        ({"currency": "EUR", "value": {"value": "2800", "unitText": "MONTH"}}, "2800 EUR / month"),
        ({"currency": "EUR", "value": 3500}, "3500 EUR"),
        ({"currency": "EUR", "value": True}, None),
        ("Palkka TES:n mukaan", "Palkka TES:n mukaan"),
    ],
)
def test_salary_shapes(salary, expected) -> None:  # noqa: ANN001
    parsed = parse_job_posting(job_posting_page(synthetic_posting(baseSalary=salary)))
    assert parsed.salary_text == expected


def test_country_only_locations_are_dropped_when_a_city_is_given() -> None:
    """Jobly style: one city plus repeated country-only places."""
    posting = synthetic_posting(
        jobLocation=[
            {"@type": "Place", "address": {"addressCountry": "FI", "addressLocality": "Turku"}},
            {"@type": "Place", "address": {"addressCountry": "FI"}},
            {"@type": "Place", "address": {"addressCountry": "FI"}},
        ]
    )
    assert parse_job_posting(job_posting_page(posting)).location == "Turku, FI"


def test_country_only_location_kept_when_nothing_more_specific() -> None:
    posting = synthetic_posting(jobLocation=[{"address": {"addressCountry": "FI"}}])
    assert parse_job_posting(job_posting_page(posting)).location == "FI"


def test_run_together_source_text_is_not_rewritten() -> None:
    """Some boards strip paragraph breaks themselves; we keep the publisher's text as-is."""
    posting = synthetic_posting(description="Ensimmäinen lause.Toinen lause.")
    assert parse_job_posting(job_posting_page(posting)).description == "Ensimmäinen lause.Toinen lause."
