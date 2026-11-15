"""English-first import, posting language and the language filter. Synthetic data only."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.adapters.job_sources.jsonld import parse_job_posting
from app.adapters.job_sources.language import alternate_url, detect_language, primary_language
from app.services.job_service import IMPORT_FAILURE_MESSAGES
from tests.fake_web import FakeWeb, job_posting_page
from tests.fake_web import synthetic_posting as _synthetic_posting

JOBS = "/api/v1/jobs"
IMPORT = "/api/v1/jobs/import"
FI_URL = "https://jobs.example.com/tyopaikka/kehittaja-123"
EN_URL = "https://jobs.example.com/en/job/kehittaja-123"

def synthetic_posting(**overrides) -> dict:  # noqa: ANN003
    """The shared synthetic posting, but without a stated language unless a test sets one."""
    return _synthetic_posting(**{"inLanguage": None, **overrides})


FINNISH = (
    "Haemme tiimiimme kehittäjää. Sinulla on kokemusta Pythonista ja olet valmis oppimaan. "
    "Tarjoamme mielenkiintoisen työn ja meillä on hyvä yhteishenki. Tehtäviin kuuluu myös testausta, "
    "joka tehdään yhdessä tiimin kanssa."
)
ENGLISH = (
    "We are looking for a developer to join our team. You will have experience with Python and "
    "you are ready to learn. We offer interesting work and a friendly team."
)
SWEDISH = (
    "Vi söker en utvecklare till vår grupp. Du har erfarenhet av Python och är redo att lära dig. "
    "Vi erbjuder ett intressant arbete och du kommer att trivas med oss."
)


def alternates(en: str = EN_URL, fi: str = FI_URL) -> str:
    return f'<link rel="alternate" hreflang="en" href="{en}"><link rel="alternate" hreflang="fi" href="{fi}">'


# ---------- Detection ----------


def test_detect_language() -> None:
    assert detect_language(FINNISH) == "fi"
    assert detect_language(ENGLISH) == "en"
    assert detect_language(SWEDISH) == "sv"
    assert detect_language("Python, SQL, Docker") is None  # too little text to tell
    assert detect_language(None) is None
    # Evenly mixed text is not claimed for either language.
    assert detect_language("We are a team and you will work with us. " + FINNISH[:90]) in (None, "en")


def test_primary_language_and_stated_language() -> None:
    assert primary_language("fi-FI") == "fi"
    assert primary_language("EN") == "en"
    assert primary_language("Finnish") is None
    # The page's own statement wins over detection.
    parsed = parse_job_posting(job_posting_page(synthetic_posting(description=ENGLISH, inLanguage="fi-FI")))
    assert parsed.language == "fi"
    parsed = parse_job_posting(job_posting_page(synthetic_posting(description=FINNISH)))
    assert parsed.language == "fi"
    parsed = parse_job_posting(job_posting_page(synthetic_posting(description="<p>Python</p>")))
    assert parsed.language is None


def test_alternate_url() -> None:
    html = '<head><link rel="alternate" hreflang="en-GB" href="/en/job/1"></head>'
    assert alternate_url(html, "https://jobs.example.com/fi/1", "en") == "https://jobs.example.com/en/job/1"
    assert alternate_url("<link rel='stylesheet' hreflang='en' href='/x.css'>", "https://a.example", "en") is None
    assert alternate_url("<p>no links</p>", "https://a.example", "en") is None


# ---------- Import ----------


def test_import_asks_for_english(client: TestClient, fake_web: FakeWeb) -> None:
    fake_web.add_html(FI_URL, job_posting_page(synthetic_posting(description=ENGLISH)))
    assert client.post(IMPORT, json={"url": FI_URL}).status_code == 201
    assert fake_web.request_headers[0]["accept-language"].startswith("en")


def test_import_uses_real_english_version(client: TestClient, fake_web: FakeWeb, settings) -> None:  # noqa: ANN001
    fake_web.add_html(FI_URL, job_posting_page(synthetic_posting(description=FINNISH), alternates()))
    fake_web.add_html(
        EN_URL,
        job_posting_page(synthetic_posting(title="Developer (synthetic)", description=ENGLISH), alternates()),
    )
    job = client.post(IMPORT, json={"url": FI_URL}).json()
    assert job["title"] == "Developer (synthetic)"
    assert job["language"] == "en"
    assert job["canonical_url"] == EN_URL
    assert job["listings"][0]["source_url"] == EN_URL
    snapshot = next((settings.app_data_dir / "source_snapshots").glob("*.json")).read_text(encoding="utf-8")
    assert FI_URL in snapshot  # the original-language address is kept for provenance
    # Importing either address again is a duplicate.
    assert client.post(IMPORT, json={"url": EN_URL}).status_code == 409
    assert client.post(IMPORT, json={"url": FI_URL}).status_code == 409


def test_english_page_with_finnish_advert_is_not_used(client: TestClient, fake_web: FakeWeb) -> None:
    # Like several Finnish boards: the "English" page only translates the menus.
    fake_web.add_html(FI_URL, job_posting_page(synthetic_posting(description=FINNISH), alternates()))
    fake_web.add_html(EN_URL, job_posting_page(synthetic_posting(description=FINNISH), alternates()))
    job = client.post(IMPORT, json={"url": FI_URL}).json()
    assert job["language"] == "fi"
    assert job["canonical_url"] == FI_URL


def test_english_alternate_must_be_same_site_and_same_posting(client: TestClient, fake_web: FakeWeb) -> None:
    other_site = "https://elsewhere.example.org/en/job/1"
    fake_web.add_html(FI_URL, job_posting_page(synthetic_posting(description=FINNISH), alternates(en=other_site)))
    fake_web.add_html(other_site, job_posting_page(synthetic_posting(description=ENGLISH)))
    assert client.post(IMPORT, json={"url": FI_URL}).json()["canonical_url"] == FI_URL
    assert other_site not in fake_web.requests

    fi2, en2 = FI_URL + "-b", EN_URL + "-b"
    fake_web.add_html(
        fi2,
        job_posting_page(
            synthetic_posting(title="Toinen tehtävä", description=FINNISH, identifier="JOB-9"),
            alternates(en=en2, fi=fi2),
        ),
    )
    fake_web.add_html(en2, job_posting_page(synthetic_posting(description=ENGLISH, identifier="JOB-10")))
    assert client.post(IMPORT, json={"url": fi2}).json()["canonical_url"] == fi2


def test_english_version_failure_keeps_original(client: TestClient, fake_web: FakeWeb) -> None:
    fake_web.add_html(FI_URL, job_posting_page(synthetic_posting(description=FINNISH), alternates()))
    fake_web.add_robots("https://jobs.example.com", "User-agent: *\nDisallow: /en/\n")
    job = client.post(IMPORT, json={"url": FI_URL}).json()  # English page missing and disallowed
    assert job["canonical_url"] == FI_URL
    assert EN_URL not in fake_web.requests
    # A failed English fetch is not an import failure.
    assert {s["key"]: s for s in client.get("/api/v1/sources").json()}["url_import"]["last_error"] is None


def test_english_posting_does_not_fetch_alternates(client: TestClient, fake_web: FakeWeb) -> None:
    fake_web.add_html(EN_URL, job_posting_page(synthetic_posting(description=ENGLISH), alternates()))
    client.post(IMPORT, json={"url": EN_URL})
    assert fake_web.requests == [EN_URL]


# ---------- Filter and errors ----------


def test_language_filter(client: TestClient) -> None:
    en = client.post(JOBS, json={"title": "A", "company": "X", "language": "en"}).json()
    en_gb = client.post(JOBS, json={"title": "B", "company": "X", "language": "en-GB"}).json()
    fi = client.post(JOBS, json={"title": "C", "company": "X", "language": "fi"}).json()
    unknown = client.post(JOBS, json={"title": "D", "company": "X"}).json()

    def ids(language: str) -> set[str]:
        return {j["id"] for j in client.get(JOBS, params={"language": language}).json()["items"]}

    assert ids("en") == {en["id"], en_gb["id"]}
    assert ids("EN") == {en["id"], en_gb["id"]}
    assert ids("fi") == {fi["id"]}
    assert ids("unknown") == {unknown["id"]}
    assert client.get(JOBS, params={"language": "english!"}).status_code == 422


def test_failure_messages_are_sentences() -> None:
    from importlib import import_module

    migration = import_module("migrations.versions.0004_readable_source_errors")
    assert migration.MESSAGES == IMPORT_FAILURE_MESSAGES
    for message in IMPORT_FAILURE_MESSAGES.values():
        assert message.endswith(".") and len(message) <= 200 and "_" not in message


def test_robots_refusal_is_recorded_readably(client: TestClient, fake_web: FakeWeb) -> None:
    fake_web.add_robots("https://jobs.example.com", "User-agent: *\nDisallow: /\n")
    assert client.post(IMPORT, json={"url": FI_URL}).status_code == 422
    last_error = {s["key"]: s for s in client.get("/api/v1/sources").json()}["url_import"]["last_error"]
    assert last_error == IMPORT_FAILURE_MESSAGES["robots_disallowed"]


def test_language_is_in_list_items(client: TestClient) -> None:
    client.post(JOBS, json={"title": "A", "company": "X", "language": "fi"})
    assert client.get(JOBS).json()["items"][0]["language"] == "fi"
