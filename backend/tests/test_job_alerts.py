"""Job alert emails, cross-site duplicate matching and merging. Synthetic emails only."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime

import pytest
from fastapi.testclient import TestClient

from app.adapters.job_sources.email_alerts import message_key, parse_alert_email
from app.adapters.mailbox import MailboxError, imap_date
from app.services import alert_service
from app.services.job_matching import Posting, company_key, compare, title_key
from tests.fake_web import FakeWeb, job_posting_page, synthetic_posting

JOBS = "/api/v1/jobs"
ALERTS = "/api/v1/job-alerts"
RECEIVED = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
SEPARATOR = "-" * 57


def alert_email(
    sender: str,
    *,
    text: str | None = None,
    html: str | None = None,
    dkim_domain: str | None = None,
    message_id: str = "<alert-1@mail.example>",
) -> bytes:
    msg = EmailMessage()
    domain = sender.rpartition("@")[2]
    msg["Authentication-Results"] = (
        f"mx.google.com; dkim=pass header.i=@{dkim_domain or domain} header.s=s1; spf=pass"
        if dkim_domain != ""
        else "mx.google.com; dkim=fail header.i=@unknown.example"
    )
    msg["From"] = f"Job Alerts <{sender}>"
    msg["To"] = "testi.kayttaja@example.com"
    msg["Subject"] = "Synthetic job alert"
    msg["Date"] = format_datetime(RECEIVED)
    msg["Message-ID"] = message_id
    msg.set_content(text or "See the HTML version.")
    if html:
        msg.add_alternative(html, subtype="html")
    return msg.as_bytes()


def linkedin_text(*cards: tuple[str, str, str, str]) -> str:
    blocks = ["Your job alert for synthetic roles in Finland"]
    for i, (title, company, location, job_id) in enumerate(cards):
        lines = [title, company, location, "", "1 school alum"]
        if i == 0:
            blocks[0] = "\n".join([blocks[0], *lines])
        else:
            blocks.append("\n".join(lines))
        blocks[-1] += (
            f"\nView job: https://www.linkedin.com/comm/jobs/view/{job_id}/?trackingId=abc&otpToken=SECRET123\n"
        )
        blocks.append(SEPARATOR)
    return "\n\n".join(blocks) + "\nThis email was intended for Testi Käyttäjä\n"


def linkedin_email(*cards: tuple[str, str, str, str], message_id: str = "<li-1@mail.example>", **kw) -> bytes:  # noqa: ANN003
    return alert_email("jobalerts-noreply@linkedin.com", text=linkedin_text(*cards), message_id=message_id, **kw)


def glassdoor_card(company: str, title: str, location: str, listing_id: str, age: str, rating: bool = True) -> str:
    link = f"https://www.glassdoor.com/partner/jobListing.htm?pos=101&amp;jobListingId={listing_id}&amp;uido=X"
    parts = [f"<td>{company}</td>"]
    if rating:
        parts.append("<td>3.8 ★</td>")
    parts += [f"<td><b>{title}</b></td>", f"<td>{location}</td>", "<td>Easy Apply</td>", f"<td>{age}</td>"]
    return f'<a href="{link}"><table><tr>{"".join(parts)}</tr></table></a>'


def glassdoor_email(*cards: str, message_id: str = "<gd-1@mail.example>") -> bytes:
    html = (
        "<html><head><style>a{color:red}</style></head><body><h1>Your job listings</h1>"
        + "".join(cards)
        + '<a href="https://www.glassdoor.com/Job/turku-jobs.htm">See more jobs</a></body></html>'
    )
    return alert_email("noreply@glassdoor.com", html=html, message_id=message_id)


def upload(client: TestClient, *emails: bytes) -> dict:
    files = [("files", (f"alert{i}.eml", raw, "message/rfc822")) for i, raw in enumerate(emails)]
    response = client.post(f"{ALERTS}/emails", files=files)
    assert response.status_code == 200, response.text
    return response.json()


def all_jobs(client: TestClient) -> list[dict]:
    return client.get(JOBS, params={"limit": 200}).json()["items"]


def job_detail(client: TestClient, job_id: str) -> dict:
    return client.get(f"{JOBS}/{job_id}").json()


# ---------- Parsing ----------


def test_linkedin_alert_cards() -> None:
    parsed = parse_alert_email(
        linkedin_email(
            ("Asiakasneuvoja", "Esimerkki Oy", "Turku", "1001"),
            ("Data Analyst", "Example Analytics", "Helsinki", "1002"),
        )
    )
    assert parsed.result == "parsed" and parsed.site.key == "alert_linkedin"
    assert [(j.title, j.company, j.location) for j in parsed.jobs] == [
        ("Asiakasneuvoja", "Esimerkki Oy", "Turku"),
        ("Data Analyst", "Example Analytics", "Helsinki"),
    ]
    first = parsed.jobs[0]
    assert first.link == "https://www.linkedin.com/jobs/view/1001/"  # sign-in token dropped
    assert first.external_id == "1001" and first.posted_on is None


def test_glassdoor_alert_cards() -> None:
    parsed = parse_alert_email(
        glassdoor_email(
            glassdoor_card("Example Pharma (FI)", "Process Technician", "Turku", "501", "3d"),
            glassdoor_card("Synthetic Labs", "QA Engineer", "Espoo", "502", "14h", rating=False),
            glassdoor_card("Old Corp", "Analyst", "Vantaa", "503", "30d+"),
        )
    )
    jobs = {j.external_id: j for j in parsed.jobs}
    assert set(jobs) == {"501", "502", "503"}  # "See more jobs" is not a posting
    assert (jobs["501"].company, jobs["501"].title, jobs["501"].location) == (
        "Example Pharma (FI)", "Process Technician", "Turku",
    )
    assert jobs["501"].posted_on == date(2026, 11, 7)
    assert jobs["502"].posted_on == date(2026, 11, 9)  # 12:00 minus 14 hours
    assert jobs["503"].posted_on is None  # "30d+" is not a date
    assert jobs["501"].canonical_url is None and "jobListingId=501" in jobs["501"].link


def test_sender_must_be_a_verified_job_site() -> None:
    card = ("Developer", "Example Oy", "Turku", "1")
    assert parse_alert_email(linkedin_email(card, dkim_domain="")).result == "unverified_sender"
    assert parse_alert_email(linkedin_email(card, dkim_domain="evil.example")).result == "unverified_sender"
    lookalike = alert_email("alerts@linkedin.com.evil.example", text=linkedin_text(card))
    assert parse_alert_email(lookalike).result == "unknown_sender"
    assert parse_alert_email(alert_email("friend@example.com", text="hello")).result == "unknown_sender"


def test_only_links_on_the_sites_own_domain_become_jobs() -> None:
    text = linkedin_text(("Developer", "Example Oy", "Turku", "1")).replace(
        "https://www.linkedin.com/comm/jobs/view/1/", "https://linkedin.evil.example/comm/jobs/view/1/"
    )
    parsed = parse_alert_email(alert_email("jobalerts-noreply@linkedin.com", text=text))
    assert parsed.jobs == [] and parsed.result == "no_jobs"


def test_message_key_and_imap_date() -> None:
    assert message_key(b"Message-ID: <a@b>\r\n\r\nbody") == "<a@b>"
    assert message_key(b"Subject: x\r\n\r\nbody").startswith("sha256:")
    assert imap_date(date(2026, 3, 5)) == "05-Mar-2026"


# ---------- Matching ----------


def test_normalisation() -> None:
    assert company_key("Example Pharma (FI)") == company_key("example pharma oy") == "example pharma"
    assert company_key("Hedin Automotive Finland Oy") == company_key("Hedin Automotive Oy")
    assert title_key("Data Engineer (f/m/x)") == title_key("data engineer")


def test_compare_rules() -> None:
    base = Posting("Example Oy", "Data Analyst", "Turku", None, date(2026, 11, 1))
    assert compare(Posting("Example Ltd", "Data analyst", "Turku", None, date(2026, 11, 5)), base) == "same"
    assert compare(Posting("Other Oy", "Data Analyst", "Turku"), base) == "different"
    assert compare(Posting("Example Oy", "Sales Manager", "Turku"), base) == "different"
    assert compare(Posting("Example Oy", "Data Analyst", "Oulu"), base) == "possible"
    assert compare(Posting("Example Oy", "Data Analyst", "Turku", None, date(2027, 3, 1)), base) == "possible"
    assert compare(Posting("Example Oy", "Senior Data Analyst", "Turku"), base) == "possible"
    english = "We are looking for a data analyst to join our team in Turku. " * 6
    finnish = "Haemme joukkoomme data-analyytikkoa Turun toimistollemme. Tehtäviin kuuluu raportointi. " * 6
    a = Posting("Example Oy", "Data Analyst", "Turku", english)
    assert compare(Posting("Example Oy", "Data Analyst", "Turku", english), a) == "same"
    assert compare(Posting("Example Oy", "Data Analyst", "Turku", finnish), a) == "possible"


# ---------- Intake ----------


def test_alert_email_creates_jobs_once(client: TestClient, settings) -> None:  # noqa: ANN001
    email = linkedin_email(("Asiakasneuvoja", "Esimerkki Oy", "Turku", "1001"))
    report = upload(client, email)
    assert report["jobs_created"] == 1 and report["emails_checked"] == 1
    job = job_detail(client, all_jobs(client)[0]["id"])
    assert job["sources"] == ["alert_linkedin"]
    assert job["canonical_url"] == "https://www.linkedin.com/jobs/view/1001/"
    assert job["listings"][0]["external_id"] == "1001"
    assert job["description"] is None and job["published_on"] is None
    snapshot = next((settings.app_data_dir / "source_snapshots").glob("*.json")).read_text(encoding="utf-8")
    assert "SECRET123" not in snapshot and "Testi" not in snapshot

    again = upload(client, email)
    assert again["emails_already_read"] == 1 and again["jobs_created"] == 0
    # A later email listing the same posting only refreshes it.
    later = upload(client, linkedin_email(("Asiakasneuvoja", "Esimerkki Oy", "Turku", "1001"), message_id="<li-2@x>"))
    assert later["jobs_already_known"] == 1 and len(all_jobs(client)) == 1


def test_same_job_on_two_sites_is_one_job(client: TestClient) -> None:
    upload(client, linkedin_email(("Process Technician", "Example Pharma Oy", "Turku", "1001")))
    report = upload(
        client, glassdoor_email(glassdoor_card("Example Pharma (FI)", "Process Technician", "Turku", "501", "3d"))
    )
    assert report["jobs_merged"] == 1 and report["jobs_created"] == 0
    [summary] = all_jobs(client)
    job = job_detail(client, summary["id"])
    assert job["sources"] == ["alert_glassdoor", "alert_linkedin"]
    assert len(job["listings"]) == 2
    assert job["published_on"] == "2026-11-07"  # filled in from the Glassdoor card


def test_same_title_in_another_city_is_flagged_not_merged(client: TestClient) -> None:
    upload(client, linkedin_email(("Myyjä", "Esimerkkikauppa Oy", "Turku", "1001")))
    report = upload(client, glassdoor_email(
        glassdoor_card("Esimerkkikauppa Oy", "Myyjä", "Oulu", "2002", "1d"), message_id="<gd-2@x>"
    ))
    assert report["jobs_created"] == 1 and report["possible_duplicates"] == 1
    jobs = {j["location"]: j for j in all_jobs(client)}
    assert jobs["Oulu"]["possible_duplicate_of"] == jobs["Turku"]["id"]
    assert jobs["Turku"]["possible_duplicate_of"] is None


def test_separate_postings_on_one_site_are_flagged_only_after_applying(client: TestClient) -> None:
    upload(client, linkedin_email(("Myyjä", "Esimerkkikauppa Oy", "Turku", "1001")))
    report = upload(client, linkedin_email(("Myyjä", "Esimerkkikauppa Oy", "Oulu", "1002"), message_id="<li-2@x>"))
    assert report["jobs_created"] == 1 and report["possible_duplicates"] == 0  # the site lists two postings
    turku = next(j for j in all_jobs(client) if j["location"] == "Turku")
    client.patch(f"{JOBS}/{turku['id']}", json={"status": "applied"})
    report = upload(client, linkedin_email(("Myyjä", "Esimerkkikauppa Oy", "Turku", "1003"), message_id="<li-3@x>"))
    assert report["jobs_merged"] == 1 and report["jobs_created"] == 0  # a repost (same place) joins the job
    again = next(j for j in all_jobs(client) if j["location"] == "Turku")
    assert again["id"] == turku["id"] and again["status"] == "applied"
    assert len(all_jobs(client)) == 2


def test_url_import_completes_an_alert_job(client: TestClient, fake_web: FakeWeb) -> None:
    upload(client, linkedin_email(("Ohjelmistokehittäjä (synthetic)", "Esimerkki Oy", "Turku", "1001")))
    url = "https://jobs.example.com/job/42"
    fake_web.add_html(url, job_posting_page(synthetic_posting()))
    response = client.post(f"{JOBS}/import", json={"url": url})
    assert response.status_code == 200  # added to the job already in the list
    job = response.json()
    assert len(all_jobs(client)) == 1
    assert job["description"] and len(job["listings"]) == 2
    assert job["canonical_url"] == "https://www.linkedin.com/jobs/view/1001/"  # first address kept


def test_manual_entry_of_a_known_job_is_flagged(client: TestClient) -> None:
    first = client.post(JOBS, json={"title": "Data Analyst", "company": "Example Oy"}).json()
    second = client.post(JOBS, json={"title": "Data analyst", "company": "Example Ltd"}).json()
    other = client.post(JOBS, json={"title": "Chef", "company": "Example Oy"}).json()
    assert second["possible_duplicate_of"] == first["id"]
    assert other["possible_duplicate_of"] is None


def test_merge_and_dismiss(client: TestClient) -> None:
    keep = client.post(JOBS, json={"title": "Data Analyst", "company": "Example Oy", "url": "https://a.example/1"}).json()
    dup = client.post(
        JOBS, json={"title": "Data Analyst", "company": "Example Oy", "location": "Turku", "url": "https://b.example/2"}
    ).json()
    client.patch(f"{JOBS}/{dup['id']}", json={"status": "applied", "user_notes": "Applied on 1 Nov"})

    merged = client.post(f"{JOBS}/{dup['id']}/merge", json={"into_job_id": keep["id"]})
    assert merged.status_code == 200
    job = merged.json()
    assert job["status"] == "applied"  # the application is not lost
    assert job["location"] == "Turku" and job["user_notes"] == "Applied on 1 Nov"
    assert len(job["listings"]) == 2
    assert client.get(f"{JOBS}/{dup['id']}").status_code == 404
    assert client.post(f"{JOBS}/{keep['id']}/merge", json={"into_job_id": keep["id"]}).status_code == 422

    flagged = client.post(JOBS, json={"title": "Data Analyst", "company": "Example Oy"}).json()
    assert flagged["possible_duplicate_of"] == keep["id"]
    cleared = client.patch(f"{JOBS}/{flagged['id']}", json={"possible_duplicate_of": None}).json()
    assert cleared["possible_duplicate_of"] is None
    assert client.patch(f"{JOBS}/{flagged['id']}", json={"possible_duplicate_of": keep["id"]}).status_code == 422


def test_upload_rejects_other_files(client: TestClient) -> None:
    response = client.post(f"{ALERTS}/emails", files=[("files", ("cv.pdf", b"%PDF", "application/pdf"))])
    assert response.status_code == 422


# ---------- Mailbox sync ----------


class FakeMailbox:
    def __init__(self, emails: list[bytes], error: str | None = None) -> None:
        self.emails, self.error = emails, error
        self.since: date | None = None
        self.skipped: list[str] = []

    def fetch_since(self, since: date, skip: Callable[[str], bool]) -> Iterator[bytes]:
        self.since = since
        if self.error:
            raise MailboxError(self.error)
        for raw in self.emails:
            key = message_key(raw)
            if skip(key):
                self.skipped.append(key)
                continue
            yield raw


def use_mailbox(client: TestClient, mailbox: FakeMailbox | None) -> None:
    client.app.state.mailbox_factory = lambda: mailbox


def test_sync_reads_new_alerts(client: TestClient) -> None:
    emails = [
        linkedin_email(("Data Analyst", "Example Oy", "Turku", "1")),
        glassdoor_email(glassdoor_card("Example Oy", "Data Analyst", "Turku", "9", "1d")),
        alert_email("newsletter@example.com", text="Not a job alert"),
    ]
    mailbox = FakeMailbox(emails)
    use_mailbox(client, mailbox)
    report = client.post(f"{ALERTS}/sync").json()
    assert report["emails_checked"] == 3 and report["emails_not_alerts"] == 1
    assert report["jobs_created"] == 1 and report["jobs_merged"] == 1
    # The look-back uses the UTC date (stored times are UTC), not the local one.
    assert mailbox.since == datetime.now(timezone.utc).date() - timedelta(days=30)  # first run looks back 30 days

    status = client.get(ALERTS).json()
    assert status["configured"] is True and status["emails_read"] == 3
    assert status["last_sync_at"] is not None and status["last_error"] is None
    sites = {s["key"]: s for s in status["sites"]}
    assert sites["alert_linkedin"]["emails_read"] == 1 and sites["alert_linkedin"]["format_verified"] is True
    assert sites["alert_duunitori"]["format_verified"] is False

    second = FakeMailbox(emails)
    use_mailbox(client, second)
    report = client.post(f"{ALERTS}/sync").json()
    assert report["emails_checked"] == 0 and len(second.skipped) == 3  # skipped before download
    assert second.since >= datetime.now(timezone.utc).date() - timedelta(days=2)


def test_sync_errors_are_readable(client: TestClient) -> None:
    use_mailbox(client, None)
    response = client.post(f"{ALERTS}/sync")
    assert response.status_code == 409 and response.json()["error"]["code"] == "mailbox_not_configured"
    assert client.get(ALERTS).json()["configured"] is False

    use_mailbox(client, FakeMailbox([], error="auth_failed"))
    response = client.post(f"{ALERTS}/sync")
    assert response.status_code == 502 and response.json()["error"]["details"]["reason"] == "auth_failed"
    status = client.get(ALERTS).json()
    assert status["last_error"] == alert_service.MAILBOX_FAILURE_MESSAGES["auth_failed"]


@pytest.mark.parametrize("reason", ["folder_missing", "connection_failed", "timeout", "search_failed"])
def test_every_mailbox_failure_has_a_sentence(client: TestClient, reason: str) -> None:
    use_mailbox(client, FakeMailbox([], error=reason))
    assert client.post(f"{ALERTS}/sync").status_code == 502
    message = client.get(ALERTS).json()["last_error"]
    assert message.endswith(".") and "_" not in message


# ---------- IMAP reader (fake server) ----------


class FakeImap:
    instances: list[FakeImap] = []

    def __init__(self, host: str, port: int, ssl_context=None, timeout=None) -> None:  # noqa: ANN001
        self.selected: tuple[str, bool] | None = None
        self.fetches: list[str] = []
        self.logged_out = False
        FakeImap.instances.append(self)

    def login(self, user: str, password: str) -> None:
        import imaplib

        if password != "app-password":
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")

    def select(self, folder: str, readonly: bool = False) -> tuple[str, list]:
        self.selected = (folder, readonly)
        return ("OK", [b"2"]) if folder == '"DuuniScript"' else ("NO", [b"no such folder"])

    def search(self, charset, *criteria: str) -> tuple[str, list]:  # noqa: ANN001
        assert criteria == ("SINCE", "01-Nov-2026")
        return "OK", [b"1 2"]

    def fetch(self, number: bytes, parts: str) -> tuple[str, list]:
        self.fetches.append(parts)
        message_id = b"<old@x>" if number == b"1" else b"<new@x>"
        if "HEADER.FIELDS" in parts:
            return "OK", [(number + b" (BODY[HEADER.FIELDS (MESSAGE-ID)] {20}", b"Message-ID: " + message_id), b" RFC822.SIZE 900)"]
        return "OK", [(number + b" (BODY[] {10}", b"Message-ID: " + message_id + b"\r\n\r\nbody"), b")"]

    def logout(self) -> None:
        self.logged_out = True


def test_imap_reader_is_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    import imaplib

    from app.adapters.mailbox import ImapMailbox

    monkeypatch.setattr(imaplib, "IMAP4_SSL", FakeImap)
    FakeImap.instances.clear()
    box = ImapMailbox("imap.example.com", 993, "user@example.com", "app-password", "DuuniScript")
    emails = list(box.fetch_since(date(2026, 11, 1), lambda mid: mid == "<old@x>"))
    assert emails == [b"Message-ID: <new@x>\r\n\r\nbody"]  # the known email is never downloaded
    server = FakeImap.instances[-1]
    assert server.selected == ('"DuuniScript"', True) and server.logged_out
    assert all("PEEK" in parts for parts in server.fetches)  # nothing is marked as read

    with pytest.raises(MailboxError) as error:
        list(ImapMailbox("imap.example.com", 993, "u", "wrong", "DuuniScript").fetch_since(date(2026, 11, 1), bool))
    assert error.value.reason == "auth_failed"
    with pytest.raises(MailboxError) as error:
        list(ImapMailbox("imap.example.com", 993, "u", "app-password", "Other").fetch_since(date(2026, 11, 1), bool))
    assert error.value.reason == "folder_missing"


def test_valtiolle_alert_links_are_recognised() -> None:
    from app.adapters.job_sources.email_alerts import SITES_BY_KEY

    site = SITES_BY_KEY["alert_valtiolle"]
    assert site.verified is False  # no real Valtiolle alert email has been checked yet
    assert site.link.match("https://valtiolle.fi/fi/tyopaikat/tutkija-123456/").group(1) == "123456"
    assert site.link.match("https://www.valtiolle.fi/en/jobs/researcher-98765").group(1) == "98765"
    assert site.link.match("https://evil.example/valtiolle.fi/fi/tyopaikat/123456") is None
