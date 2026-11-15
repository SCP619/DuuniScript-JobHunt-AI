"""Official job feeds and public job APIs. All feed content here is synthetic."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.adapters.job_sources import feeds
from app.persistence.models import JobSource
from app.services import eligibility
from tests.fake_web import FakeWeb
from tests.test_job_alerts import linkedin_email, upload

JOBS = "/api/v1/jobs"
FEEDS = "/api/v1/feeds"
REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
JOBSPRESSO_URL = "https://jobspresso.co/feed/job_feed/"
WWR_URL = "https://weworkremotely.com/remote-jobs.rss"
ABO_URL = "https://abo.rekrytointi.com/paikat/?o=A_RSS&jgid=1"
DESCRIPTION = (
    "<p>We build synthetic test software. You will design data pipelines, review code and "
    "work with a small distributed team.</p><ul><li>Python</li><li>SQL</li></ul>"
)


def remotive_body(*jobs: dict) -> bytes:
    return json.dumps({"0-legal-notice": "synthetic", "job-count": len(jobs), "jobs": list(jobs)}).encode()


def remotive_job(job_id: int, title: str, company: str, where: str, **extra) -> dict:  # noqa: ANN003
    return {
        "id": job_id,
        "url": f"https://remotive.com/remote-jobs/software-dev/{title.lower().replace(' ', '-')}-{job_id}",
        "title": title,
        "company_name": company,
        "job_type": "full_time",
        "publication_date": "2026-11-08T21:47:58",
        "candidate_required_location": where,
        "salary": "",
        "description": DESCRIPTION,
        **extra,
    }


def rss(*items: str, namespaces: str = "") -> bytes:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" {namespaces}><channel>'
        "<title>Synthetic</title>" + "".join(items) + "</channel></rss>"
    ).encode("utf-8")


def add_json(web: FakeWeb, url: str, body: bytes) -> None:
    web.pages[url] = __import__("httpx").Response(200, headers={"content-type": "application/json"}, content=body)


def add_xml(web: FakeWeb, url: str, body: bytes) -> None:
    web.pages[url] = __import__("httpx").Response(
        200, headers={"content-type": "application/rss+xml; charset=utf-8"}, content=body
    )


def sync(client: TestClient, key: str) -> dict:
    response = client.post(f"{FEEDS}/{key}/sync")
    assert response.status_code == 200, response.text
    return response.json()


def all_jobs(client: TestClient, **params) -> list[dict]:  # noqa: ANN003
    return client.get(JOBS, params={"limit": 200, **params}).json()["items"]


# ---------- Eligibility ----------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Worldwide", "yes"),
        ("Anywhere in the World", "yes"),
        ("Europe, USA, Canada", "yes"),
        ("EMEA", "yes"),
        ("Finland", "yes"),
        ("Turku, Southwest Finland, Finland", "yes"),
        ("FI", "yes"),
        ("CET +/- 2 hours", "yes"),
        ("UTC+2", "yes"),
        ("USA", "no"),
        ("USA, Canada, USA timezones", "no"),
        ("LATAM, Canada, USA", "no"),
        ("United States, Canada", "no"),
        ("Asia-Pacific", "no"),
        ("London, UK", "no"),
        ("Europe except Finland", "no"),
        ("Remote", "unknown"),
        ("Munich", "no"),
        ("", "unknown"),
        (None, "unknown"),
    ],
)
def test_availability_from_text(text: str | None, expected: str) -> None:
    assert eligibility.from_text(text) == expected


def test_title_restrictions() -> None:
    assert eligibility.title_restriction("Web Developer (U.S. Based, Remote Contractor)")
    assert eligibility.title_restriction("Support Agent - US only")
    assert eligibility.title_restriction("Engineer, based in the UK")
    assert not eligibility.title_restriction("Customer Success Manager, Nordics")
    assert not eligibility.title_restriction("Usability Researcher")


def test_availability_from_structured_restrictions() -> None:
    assert eligibility.from_restrictions([], []) == "yes"
    assert eligibility.from_restrictions(["Finland", "Sweden"], [1, 2, 3]) == "yes"
    assert eligibility.from_restrictions(["United States"], [-5, -6]) == "no"
    assert eligibility.from_restrictions([], [-8, -5]) == "no"


# ---------- Parsers ----------


def test_remotive_parser() -> None:
    jobs = feeds.parse_remotive(
        remotive_body(
            remotive_job(1, "Data Engineer", "Esimerkki Oy", "Europe"),
            remotive_job(2, "Sales Rep", "Example Inc", "USA only"),
            {"id": 3, "url": "https://evil.example/job", "title": "X", "company_name": "Y"},
        )
    )
    assert [j.title for j in jobs] == ["Data Engineer", "Sales Rep"]  # off-site link dropped
    first = jobs[0]
    assert first.external_id == "1"
    assert first.work_mode == "remote" and first.employment_type == "full_time"
    assert first.published_on.isoformat() == "2026-11-08"
    assert first.description.startswith("We build synthetic test software.") and "- Python" in first.description
    assert first.language == "en"
    assert [j.available_from_finland for j in jobs] == ["yes", "no"]


def test_jobspresso_parser() -> None:
    item = (
        "<item><title>Backend Developer</title><link>https://jobspresso.co/job/backend-developer/</link>"
        "<dc:creator><![CDATA[Esimerkki<br>⚲&nbsp;Europe]]></dc:creator>"
        "<pubDate>Tue, 10 Nov 2026 16:29:43 +0000</pubDate>"
        '<guid isPermaLink="false">https://jobspresso.co/?post_type=job_listing&amp;p=4242</guid>'
        f"<content:encoded><![CDATA[{DESCRIPTION}]]></content:encoded>"
        "<job_listing:job_category><![CDATA[Full Time]]></job_listing:job_category>"
        "<job_listing:company><![CDATA[Esimerkki]]></job_listing:company>"
        "<job_listing:salary><![CDATA[€60k–€70k]]></job_listing:salary></item>"
    )
    ns = (
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/" '
        'xmlns:job_listing="https://jobspresso.co/job_listing"'
    )
    [job] = feeds.parse_jobspresso(rss(item, namespaces=ns))
    assert (job.external_id, job.company, job.location) == ("4242", "Esimerkki", "Europe")
    assert job.employment_type == "full_time" and job.salary_text == "€60k–€70k"
    assert job.available_from_finland == "yes"


def test_weworkremotely_parser_uses_country_list() -> None:
    items = [
        "<item><title>Esimerkki: Data Analyst</title><link>https://weworkremotely.com/remote-jobs/esimerkki-data-analyst</link>"
        "<guid>https://weworkremotely.com/remote-jobs/esimerkki-data-analyst</guid><region>Anywhere in the World</region>"
        "<type>Full-Time</type><pubDate>Thu, 05 Nov 2026 10:00:00 +0000</pubDate>"
        f"<description>{DESCRIPTION.replace('<', '&lt;').replace('>', '&gt;')}</description></item>",
        "<item><title>Example: QA Engineer</title><link>https://weworkremotely.com/remote-jobs/example-qa</link>"
        "<guid>https://weworkremotely.com/remote-jobs/example-qa</guid><region>Anywhere in the World</region>"
        "<country>🇧🇷 Brazil, 🇲🇽 Mexico</country><type>Contract</type></item>",
    ]
    jobs = feeds.parse_weworkremotely(rss(*items))
    assert [(j.company, j.title) for j in jobs] == [("Esimerkki", "Data Analyst"), ("Example", "QA Engineer")]
    assert jobs[0].description.startswith("We build synthetic test software.")
    assert jobs[1].location == "Brazil, Mexico"
    assert [j.available_from_finland for j in jobs] == ["yes", "no"]


def test_himalayas_jobicy_arbeitnow_parsers() -> None:
    himalayas = json.dumps({"jobs": [{
        "title": "Platform Engineer", "companyName": "Esimerkki", "employmentType": "Full Time",
        "locationRestrictions": ["Finland", "Sweden"], "timezoneRestrictions": [1, 2],
        "minSalary": 60000, "maxSalary": 70000, "currency": "EUR", "salaryPeriod": "annual",
        "description": DESCRIPTION, "pubDate": 1794260788,
        "guid": "https://himalayas.app/companies/esimerkki/jobs/platform-engineer",
    }]}).encode()
    [job] = feeds.parse_himalayas(himalayas)
    assert job.available_from_finland == "yes" and job.location == "Finland, Sweden"
    assert job.salary_text == "60 000–70 000 EUR per year"

    jobicy = json.dumps({"jobs": [{
        "id": 77, "url": "https://jobicy.com/jobs/77-support-specialist", "jobTitle": "Support Specialist",
        "companyName": "Example", "jobGeo": "EMEA", "jobType": ["Full-Time"], "pubDate": "2026-11-10T12:45:28+00:00",
        "jobDescription": DESCRIPTION,
    }]}).encode()
    [job] = feeds.parse_jobicy(jobicy)
    assert (job.external_id, job.available_from_finland, job.employment_type) == ("77", "yes", "full_time")

    arbeitnow = json.dumps({"data": [
        {"slug": "onsite-1", "url": "https://www.arbeitnow.com/jobs/a/onsite-1", "title": "On-site", "company_name": "A",
         "remote": False, "location": "Munich", "created_at": 1794326455},
        {"slug": "remote-2", "url": "https://www.arbeitnow.com/jobs/b/remote-2", "title": "Remote Dev", "company_name": "B",
         "remote": True, "location": "Remote", "job_types": ["Full Time"], "created_at": 1794326455,
         "description": DESCRIPTION},
    ]}).encode()
    [job] = feeds.parse_arbeitnow(arbeitnow)  # on-site jobs are left out
    assert (job.external_id, job.available_from_finland) == ("remote-2", "unknown")


def abo_item(job_id: int, title: str) -> str:
    link = f"https://abo.rekrytointi.com/paikat/?o=A_RJ&amp;jgid=1&amp;jid={job_id}"
    return (
        f"<item><title>{title}</title><link>{link}</link>"
        "<description>Ansökningstiden börjar: 10.11.2026 14:00 - Ansökningstiden slutar: 01.12.2026 15:00</description>"
        f"<pubDate>Tue, 10 Nov 2026 12:00:00 +0000</pubDate><guid>{link}</guid>"
        "<laura:startdate><![CDATA[2026-11-10 14:00:00]]></laura:startdate>"
        "<laura:enddate><![CDATA[2026-12-01 15:00:00]]></laura:enddate>"
        "<laura:description><![CDATA[<p>Vi söker en person som är intresserad av forskning och som har "
        "erfarenhet av arbete med data. Arbetet är på heltid och du får en trevlig arbetsplats med "
        "kolleger som är engagerade i det som de gör.</p>]]></laura:description></item>"
    )


def test_abo_akademi_parser() -> None:
    body = rss(abo_item(1055, "Dataskyddsombud"), abo_item(1055, "Dataskyddsombud"),
               namespaces='xmlns:laura="https://abo.rekrytointi.com/#"')
    [job] = feeds.parse_abo_akademi(body)  # the feed repeats items; kept once
    assert (job.external_id, job.company, job.available_from_finland) == ("1055", "Åbo Akademi", "yes")
    assert job.published_on.isoformat() == "2026-11-10"
    assert job.deadline_on.isoformat() == "2026-12-01"
    assert job.deadline_at == datetime(2026, 12, 1, 13, 0, tzinfo=timezone.utc)  # 15:00 Helsinki time
    assert job.description.startswith("Vi söker") and job.language == "sv"


def test_feeds_with_a_dtd_are_refused() -> None:
    body = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><rss><channel><item><title>&a;</title></item></channel></rss>'
    with pytest.raises(feeds.FeedFormatError):
        feeds.parse_jobspresso(body)
    with pytest.raises(feeds.FeedFormatError):
        feeds.parse_remotive(b"<html>not json</html>")


# ---------- Sync ----------


def test_sync_adds_jobs_skips_other_countries_and_respects_the_interval(client: TestClient, fake_web: FakeWeb) -> None:
    add_json(fake_web, REMOTIVE_URL, remotive_body(
        remotive_job(1, "Data Engineer", "Esimerkki Oy", "Europe"),
        remotive_job(2, "Sales Rep", "Example Inc", "USA only"),
        remotive_job(3, "Support Agent", "Testiyhtiö", "Remote"),
    ))
    report = sync(client, "feed_remotive")
    assert report["jobs_found"] == 3
    assert report["jobs_created"] == 2
    assert report["skipped_not_available"] == 1

    jobs = {j["title"]: j for j in all_jobs(client)}
    assert set(jobs) == {"Data Engineer", "Support Agent"}
    assert jobs["Data Engineer"]["available_from_finland"] == "yes"
    assert jobs["Support Agent"]["available_from_finland"] == "unknown"
    assert jobs["Data Engineer"]["work_mode"] == "remote"
    assert jobs["Data Engineer"]["sources"] == ["feed_remotive"]
    detail = client.get(f"{JOBS}/{jobs['Data Engineer']['id']}").json()
    assert detail["description"].startswith("We build synthetic test software.")
    assert detail["listings"][0]["source_url"].startswith("https://remotive.com/remote-jobs/")

    # Remotive asks for at most 4 reads a day: a second check right away is refused.
    again = client.post(f"{FEEDS}/feed_remotive/sync")
    assert again.status_code == 429
    assert again.json()["error"]["code"] == "too_soon"
    assert "next_allowed_at" in again.json()["error"]["details"]
    assert fake_web.requests.count(REMOTIVE_URL) == 1

    # Filters: only jobs open to Finland.
    assert {j["title"] for j in all_jobs(client, available_from_finland="yes")} == {"Data Engineer"}
    both = all_jobs(client, available_from_finland=["yes", "unknown"])
    assert len(both) == 2


def test_known_jobs_are_not_added_twice(client: TestClient, fake_web: FakeWeb) -> None:
    add_json(fake_web, REMOTIVE_URL, remotive_body(remotive_job(1, "Data Engineer", "Esimerkki Oy", "Europe")))
    sync(client, "feed_remotive")
    _make_due(client, "feed_remotive")
    report = sync(client, "feed_remotive")
    assert (report["jobs_created"], report["jobs_already_known"]) == (0, 1)
    assert len(all_jobs(client)) == 1


def test_same_job_from_alert_email_and_feed_is_one_job(client: TestClient, fake_web: FakeWeb) -> None:
    upload(client, linkedin_email(("Data Engineer", "Esimerkki Oy", "Turku, Southwest Finland, Finland", "4100000001")))
    add_json(fake_web, REMOTIVE_URL, remotive_body(remotive_job(1, "Data Engineer", "Esimerkki", "Finland")))
    report = sync(client, "feed_remotive")
    assert report["jobs_merged"] == 1
    [job] = all_jobs(client)
    assert job["sources"] == ["alert_linkedin", "feed_remotive"]
    detail = client.get(f"{JOBS}/{job['id']}").json()
    # The alert email had no description; the feed filled it in.
    assert detail["description"].startswith("We build synthetic test software.")
    assert detail["available_from_finland"] == "yes"


def test_separate_postings_on_one_site_are_not_flagged(client: TestClient, fake_web: FakeWeb) -> None:
    add_json(fake_web, REMOTIVE_URL, remotive_body(
        remotive_job(1, "Product Marketing Manager", "Example", "EMEA"),
        remotive_job(2, "Product Marketing Manager", "Example", "Europe"),
        remotive_job(3, "Senior Product Marketing Manager", "Example", "EMEA"),
    ))
    report = sync(client, "feed_remotive")
    assert (report["jobs_created"], report["jobs_merged"], report["possible_duplicates"]) == (3, 0, 0)


def test_keywords_limit_which_jobs_are_added(client: TestClient, fake_web: FakeWeb, settings) -> None:  # noqa: ANN001
    settings.feed_keywords = "analyst, sql"
    add_json(fake_web, REMOTIVE_URL, remotive_body(
        remotive_job(1, "Data Analyst", "A", "Worldwide", description="<p>Reports.</p>"),
        remotive_job(2, "Chef", "B", "Worldwide", description="<p>Cooking.</p>"),
    ))
    report = sync(client, "feed_remotive")
    assert (report["jobs_created"], report["skipped_keywords"]) == (1, 1)


def test_robots_txt_is_honoured_for_feeds(client: TestClient, fake_web: FakeWeb) -> None:
    fake_web.add_robots("https://jobspresso.co", "User-agent: *\nDisallow: /feed/\n")
    add_xml(fake_web, JOBSPRESSO_URL, rss())
    response = client.post(f"{FEEDS}/feed_jobspresso/sync")
    assert response.status_code == 502
    assert response.json()["error"]["details"]["reason"] == "robots_disallowed"
    assert JOBSPRESSO_URL not in fake_web.requests
    status = {f["key"]: f for f in client.get(FEEDS).json()["feeds"]}
    assert "robots.txt" in status["feed_jobspresso"]["last_error"]
    # A failed check also waits for the interval: no immediate retries.
    assert client.post(f"{FEEDS}/feed_jobspresso/sync").status_code == 429


def test_documented_api_address_is_read_even_if_robots_lists_it(client: TestClient, fake_web: FakeWeb) -> None:
    fake_web.add_robots("https://remotive.com", "User-agent: *\nDisallow: /api/*\n")
    add_json(fake_web, REMOTIVE_URL, remotive_body(remotive_job(1, "Data Engineer", "Esimerkki Oy", "Europe")))
    assert sync(client, "feed_remotive")["jobs_created"] == 1


def test_broken_feed_gives_a_readable_error(client: TestClient, fake_web: FakeWeb) -> None:
    fake_web.add_html(WWR_URL, "<html>moved</html>")
    response = client.post(f"{FEEDS}/feed_weworkremotely/sync")
    assert response.status_code == 502
    assert response.json()["error"]["message"] == "The address did not return a job feed. The site may have changed it."


def test_turning_a_feed_off(client: TestClient, fake_web: FakeWeb) -> None:
    response = client.patch("/api/v1/sources/feed_abo_akademi", json={"enabled": False})
    assert response.status_code == 200 and response.json()["enabled"] is False
    assert client.post(f"{FEEDS}/feed_abo_akademi/sync").status_code == 409
    assert "feed_abo_akademi" not in {r["key"] for r in client.post(f"{FEEDS}/sync").json()}
    assert client.patch("/api/v1/sources/nope", json={"enabled": False}).status_code == 404
    assert client.post(f"{FEEDS}/nope/sync").status_code == 404


def test_sync_due_reads_each_due_feed_once(client: TestClient, fake_web: FakeWeb) -> None:
    add_xml(fake_web, ABO_URL, rss(abo_item(1055, "Dataskyddsombud"), namespaces='xmlns:laura="https://abo.rekrytointi.com/#"'))
    results = {r["key"]: r for r in client.post(f"{FEEDS}/sync").json()}
    assert results["feed_abo_akademi"]["jobs_created"] == 1
    assert results["feed_remotive"]["error"]  # no fake feed: a readable error, others still run
    assert len(results) == len(feeds.SITES)
    assert client.post(f"{FEEDS}/sync").json() == []  # nothing is due any more
    status = client.get(FEEDS).json()
    abo = next(f for f in status["feeds"] if f["key"] == "feed_abo_akademi")
    assert abo["jobs"] == 1 and abo["next_allowed_at"] and abo["attribution"]
    [job] = all_jobs(client)
    assert job["deadline_on"] == "2026-12-01" and job["available_from_finland"] == "yes"


def _make_due(client: TestClient, key: str) -> None:
    with client.app.state.session_factory() as session:
        source = session.scalar(select(JobSource).where(JobSource.key == key))
        source.last_success_at = datetime.now(timezone.utc) - timedelta(days=1)
        session.commit()


def test_manual_and_imported_jobs_get_availability(client: TestClient) -> None:
    created = client.post(JOBS, json={"title": "Kokki", "company": "Ravintola", "location": "Turku"}).json()
    assert created["available_from_finland"] == "yes"
    changed = client.patch(f"{JOBS}/{created['id']}", json={"location": "Austin, TX"}).json()
    assert changed["available_from_finland"] == "no"
    other = client.post(JOBS, json={"title": "Writer", "company": "Somewhere"}).json()
    assert other["available_from_finland"] == "unknown"


def test_more_places_are_recognised() -> None:
    from app.services.eligibility import from_text

    for place in ("Lieto", "Seinäjoki", "Sein�joki", "Hanko", "Kirkkonummi", "Kouvola", "Lempäälä"):
        assert from_text(place) == "yes", place
    for place in ("Vienna", "Wiener Neudorf", "Amsterdam", "Warsaw", "Iowa", "Washington, DC", "Serbia", "Berlin"):
        assert from_text(place) == "no", place
    for text in ("Remote", "Apply with resume & profile"):
        assert from_text(text) == "unknown", text


def test_reassess_script_only_changes_unknown(client) -> None:  # noqa: ANN001
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "reassess", Path(__file__).resolve().parents[2] / "scripts" / "reassess_availability.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from app.persistence.models import Job

    with client.app.state.session_factory() as session:
        for title, location, value in (("A", "Vienna", "unknown"), ("B", "Lieto", "unknown"),
                                       ("C", "Vienna", "yes"), ("D", "Remote", "unknown")):
            session.add(Job(title=title, company=f"{title} Oy", location=location, available_from_finland=value,
                            content_hash=title))
        session.commit()
        assert dict(module.reassess(session, dry_run=True)) == {"no": 1, "yes": 1}
        assert dict(module.reassess(session)) == {"no": 1, "yes": 1}
        values = {j.title: j.available_from_finland for j in session.query(Job)}
    assert values == {"A": "no", "B": "yes", "C": "yes", "D": "unknown"}
