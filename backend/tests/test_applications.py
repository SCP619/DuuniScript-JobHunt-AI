"""CV and cover letter drafts, checks, approval, export and the user's submission record.

All profile data and jobs here are synthetic.
"""

from __future__ import annotations

import email
import io
import zipfile
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.services import drafting, rendering

JOB = {
    "title": "Data Analyst",
    "company": "Example Analytics Oy",
    "location": "Turku",
    "description": (
        "We are looking for a Data Analyst with strong SQL and Python skills. Experience with Power BI "
        "and Docker is a plus. Finnish is an advantage. Send your application to jobs@example.com."
    ),
    "application_url": "https://example.com/careers/data-analyst",
}

FACTS = [
    {"category": "summary", "subject": "Professional summary",
     "value_text": "Data analyst with synthetic experience in reporting. I enjoy clear dashboards."},
    {"category": "work_experience", "subject": "Data Analyst · Sample Data Ltd, Turku · Contract",
     "value_text": "Data Analyst · Sample Data Ltd, Turku · Contract. Built SQL pipelines for reporting. Cut report time by 40%.",
     "valid_from": "2024-10-01", "valid_until": "2025-06-30"},
    {"category": "work_experience", "subject": "Shop Assistant · Example Store, Tampere",
     "value_text": "Served customers.", "valid_from": "2019-01-01", "valid_until": "2020-12-31"},
    {"category": "education", "subject": "MSc, Example Studies · Example University",
     "value_text": "MSc, Example Studies · Example University. Data analytics track.", "valid_from": "2025-08-01"},
    {"category": "project", "subject": "Example Dashboard",
     "value_text": "Example Dashboard. A SQL and Python dashboard for open data.", "valid_from": "2025-01-01", "valid_until": "2025-12-31"},
    {"category": "skill", "subject": "SQL", "value_text": "SQL"},
    {"category": "skill", "subject": "Python", "value_text": "Python"},
    {"category": "skill", "subject": "Excel", "value_text": "Excel"},
    {"category": "language", "subject": "Finnish", "value_text": "Finnish (native)"},
    {"category": "language", "subject": "English", "value_text": "English (C1)"},
    {"category": "contact", "subject": "GitHub", "value_text": "github.com/testi-example"},
]


@pytest.fixture
def verified(client: TestClient, profile: dict) -> list[dict]:
    ids = []
    for item in FACTS:
        response = client.post("/api/v1/profile/facts", json=item)
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])
    # One unverified fact that must never appear in a draft.
    client.post("/api/v1/profile/facts", json={"category": "skill", "subject": "Kubernetes", "value_text": "Kubernetes"})
    result = client.post("/api/v1/profile/facts/verify", json={"fact_ids": ids})
    assert result.status_code == 200
    return result.json()["facts"]


@pytest.fixture
def job(client: TestClient) -> dict:
    response = client.post("/api/v1/jobs", json=JOB)
    assert response.status_code == 201, response.text
    return response.json()


def _start(client: TestClient, job: dict, **extra) -> dict:  # noqa: ANN003
    response = client.post("/api/v1/applications", json={"job_id": job["id"], **extra})
    assert response.status_code == 201, response.text
    return response.json()


def _fill_motivation(client: TestClient, app: dict) -> dict:
    content = app["cover_letter"]["content"].replace(
        drafting.MOTIVATION_PLACEHOLDER, "I would like to grow as an analyst in Turku."
    )
    response = client.put(f"/api/v1/applications/{app['id']}/drafts/cover_letter", json={"content": content})
    assert response.status_code == 200, response.text
    return response.json()


def _approve_all(client: TestClient, app: dict) -> dict:
    _fill_motivation(client, app)
    for kind in ("cv", "cover_letter"):
        response = client.post(f"/api/v1/applications/{app['id']}/drafts/{kind}/approve", json={"acknowledge_warnings": True})
        assert response.status_code == 200, response.text
    return client.get(f"/api/v1/applications/{app['id']}").json()


# ---------- Builder (pure) ----------


def _views(facts: list[dict]) -> list[drafting.FactView]:
    return [
        drafting.FactView(
            str(i), f["category"], f["subject"], f["value_text"],
            date.fromisoformat(f["valid_from"]) if f.get("valid_from") else None,
            date.fromisoformat(f["valid_until"]) if f.get("valid_until") else None,
        )
        for i, f in enumerate(facts)
    ]


PERSON = drafting.PersonView("Testi Käyttäjä", "testi.kayttaja@example.com", "+358 40 000 0000", "Turku")
JOBVIEW = drafting.JobView(JOB["title"], JOB["company"], JOB["description"], JOB["location"])


def test_cv_templates_order_sections_and_rank_matching_skills() -> None:
    facts = _views(FACTS)
    classic = drafting.build_cv(PERSON, facts, JOBVIEW, "classic").content
    assert classic.startswith("# Testi Käyttäjä\nTurku · testi.kayttaja@example.com · +358 40 000 0000 · github.com/testi-example")
    order = [line for line in classic.splitlines() if line.startswith("## ")]
    assert order == ["## Profile", "## Experience", "## Education", "## Projects", "## Skills", "## Languages"]
    assert "Python, SQL, Excel" in classic  # skills the posting names come first
    assert "*Oct 2024 – Jun 2025*" in classic and "*Since Aug 2025*" in classic and "*2019 – 2020*" in classic
    assert classic.index("Sample Data Ltd") < classic.index("Example Store")  # newest first

    compact = drafting.build_cv(PERSON, facts, JOBVIEW, "compact").content
    assert [line for line in compact.splitlines() if line.startswith("## ")][:2] == ["## Profile", "## Skills"]
    assert "## Projects" not in compact
    projects_first = drafting.build_cv(PERSON, facts, JOBVIEW, "projects_first").content
    assert [line for line in projects_first.splitlines() if line.startswith("## ")][1] == "## Projects"


def test_cover_letter_uses_only_facts_and_leaves_motivation_to_the_user() -> None:
    draft = drafting.build_cover_letter(PERSON, _views(FACTS), JOBVIEW, "standard", date(2026, 11, 10))
    text = draft.content
    assert "10 November 2026" in text
    assert "I am applying for the Data Analyst position at Example Analytics Oy. In short: Data analyst" in text
    assert "In my role as Data Analyst at Sample Data Ltd (Oct 2024 – Jun 2025), I built SQL pipelines for reporting." in text
    assert "Your posting asks for Python and SQL" in text
    assert "A relevant project is Example Dashboard" in text
    assert "Finnish (native)" in text
    assert drafting.MOTIVATION_PLACEHOLDER in text
    assert set(draft.evidence) <= {str(i) for i in range(len(FACTS))}
    short = drafting.build_cover_letter(PERSON, _views(FACTS), JOBVIEW, "short", date(2026, 11, 10)).content
    assert "A relevant project" not in short and drafting.MOTIVATION_PLACEHOLDER in short


def test_claim_check_flags_unsupported_statements() -> None:
    facts = _views(FACTS)
    text = (
        "Testi Käyttäjä · other.person@example.org · +358 50 999 9999\n"
        "I led a team of 12 analysts with Kubernetes and Tableau since 2015. [your reason]\n"
        "I built SQL pipelines (40% faster) in 2024 at github.com/testi-example and evil.example.net."
    )
    issues = drafting.check_draft(text, PERSON, facts, JOBVIEW, date(2026, 11, 10))
    found = {(i.severity, i.code, i.excerpt) for i in issues}
    assert ("error", "placeholder_left", "[your reason]") in found
    assert ("error", "unknown_contact", "other.person@example.org") in found
    assert ("error", "unknown_contact", "+358 50 999 9999") in found
    assert ("warning", "unsupported_date", "2015") in found
    assert ("warning", "unsupported_number", "12") in found
    assert ("warning", "unsupported_skill", "Kubernetes") in found
    assert ("warning", "unsupported_skill", "Tableau") in found
    assert ("warning", "unsupported_link", "evil.example.net") in found
    excerpts = {i.excerpt for i in issues}
    assert "2024" not in excerpts and "40%" not in excerpts and "github.com/testi-example" not in excerpts
    info = [i for i in issues if i.severity == "info"]
    assert any("Power BI" in i.message and "Docker" in i.message for i in info)


def test_generated_drafts_pass_their_own_check() -> None:
    facts = _views(FACTS)
    for key in drafting.CV_TEMPLATES:
        cv = drafting.build_cv(PERSON, facts, JOBVIEW, key).content
        assert [i for i in drafting.check_draft(cv, PERSON, facts, JOBVIEW, date.today()) if i.severity != "info"] == []
    letter = drafting.build_cover_letter(PERSON, facts, JOBVIEW, "standard", date.today()).content
    issues = [i.code for i in drafting.check_draft(letter, PERSON, facts, JOBVIEW, date.today()) if i.severity != "info"]
    assert issues == ["placeholder_left"]


def test_rendering_pdf_docx_and_text() -> None:
    markdown = drafting.build_cv(PERSON, _views(FACTS), JOBVIEW, "classic").content
    for key in ("classic", "compact", "projects_first"):
        pdf = rendering.to_pdf(markdown, rendering.style_for(key, "cv"))
        assert pdf.startswith(b"%PDF")
    fallback = rendering.to_pdf(markdown + "\nEmoji 🙂 and – dash", rendering.STYLES["classic"], use_system_fonts=False)
    assert fallback.startswith(b"%PDF")
    docx = rendering.to_docx(markdown, rendering.STYLES["compact"])
    with zipfile.ZipFile(io.BytesIO(docx)) as archive:
        body = archive.read("word/document.xml").decode("utf-8")
    assert "Testi Käyttäjä" in body and "EXPERIENCE" in body
    text = rendering.plain_text(markdown)
    assert "#" not in text and "EXPERIENCE" in text and "• Finnish (native)" in text


def test_markdown_subset_is_never_markup() -> None:
    blocks = rendering.parse("# Name\n<script>alert(1)</script>\n**bold** text\n- item\n*Jan 2020 – Feb 2021*")
    assert [b.kind for b in blocks] == ["title", "paragraph", "bullet", "meta"]
    assert blocks[1].text == "<script>alert(1)</script>\nbold text"


# ---------- API ----------


def test_templates_listed(client: TestClient) -> None:
    keys = {(t["kind"], t["key"]) for t in client.get("/api/v1/applications/templates").json()}
    assert keys == {("cv", "utu_rekry"), ("cv", "utu_rekry_fi"), ("cv", "classic"), ("cv", "compact"), ("cv", "projects_first"),
                    ("cover_letter", "utu_rekry"), ("cover_letter", "utu_rekry_fi"), ("cover_letter", "standard"), ("cover_letter", "short")}


def test_needs_verified_facts(client: TestClient, profile: dict, job: dict) -> None:
    client.post("/api/v1/profile/facts", json={"category": "skill", "subject": "SQL", "value_text": "SQL"})
    response = client.post("/api/v1/applications", json={"job_id": job["id"]})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "no_verified_facts"
    assert client.get("/api/v1/applications").json()["total"] == 0


def test_full_flow(client: TestClient, verified: list[dict], job: dict) -> None:
    app = _start(client, job, cv_template="compact", letter_template="standard")
    assert app["status"] == "draft"
    assert app["destination"] == JOB["application_url"]
    assert app["contact_emails"] == ["jobs@example.com"]
    assert app["cv"]["template"] == "compact" and app["cv"]["version"] == 1
    assert "Kubernetes" not in app["cv"]["content"]  # unverified facts are never used
    assert set(app["cv"]["evidence_fact_ids"]) <= {f["id"] for f in verified}
    assert client.get(f"/api/v1/jobs/{job['id']}").json()["status"] == "drafting"
    assert client.post("/api/v1/applications", json={"job_id": job["id"]}).json()["error"]["code"] == "application_exists"

    # The letter's placeholder blocks approval.
    blocked = client.post(f"/api/v1/applications/{app['id']}/drafts/cover_letter/approve", json={})
    assert blocked.status_code == 422
    assert blocked.json()["error"]["details"]["issues"][0]["code"] == "placeholder_left"

    # An edit with an unsupported claim needs acknowledgement.
    edited = _fill_motivation(client, app)
    content = edited["content"].replace("Kind regards", "I also know Kubernetes.\n\nKind regards")
    edited = client.put(f"/api/v1/applications/{app['id']}/drafts/cover_letter", json={"content": content}).json()
    assert edited["version"] == 1  # an unapproved draft is edited in place
    assert any(i["code"] == "unsupported_skill" for i in edited["issues"])
    warn = client.post(f"/api/v1/applications/{app['id']}/drafts/cover_letter/approve", json={})
    assert warn.status_code == 409 and warn.json()["error"]["code"] == "warnings_not_acknowledged"
    ok = client.post(f"/api/v1/applications/{app['id']}/drafts/cover_letter/approve", json={"acknowledge_warnings": True})
    assert ok.status_code == 200 and ok.json()["status"] == "approved"

    cv = client.post(f"/api/v1/applications/{app['id']}/drafts/cv/approve", json={"acknowledge_warnings": True})
    assert cv.status_code == 200
    ready = client.get(f"/api/v1/applications/{app['id']}").json()
    assert ready["status"] == "ready" and len(ready["package_hash"]) == 64

    # Editing an approved CV makes a new version and reopens the application.
    changed = client.put(
        f"/api/v1/applications/{app['id']}/drafts/cv", json={"content": ready["cv"]["content"] + "\nExtra line.\n"}
    ).json()
    assert changed["version"] == 2 and changed["status"] == "draft"
    reopened = client.get(f"/api/v1/applications/{app['id']}").json()
    assert reopened["status"] == "draft" and reopened["package_hash"] is None
    client.post(f"/api/v1/applications/{app['id']}/drafts/cv/approve", json={"acknowledge_warnings": True})
    ready = client.get(f"/api/v1/applications/{app['id']}").json()
    assert ready["status"] == "ready"

    package = client.get(f"/api/v1/applications/{app['id']}/package").json()
    assert package["ready"] and package["package_hash"] == ready["package_hash"]
    assert [f["kind"] for f in package["files"]] == ["cv", "cover_letter"]
    assert package["files"][0]["filename"] == "CV - Example Analytics Oy - Data Analyst.pdf"
    assert "Kind regards" in package["cover_letter_text"] and "#" not in package["cover_letter_text"]

    archive = client.get(f"/api/v1/applications/{app['id']}/package.zip")
    assert archive.status_code == 200 and archive.headers["content-type"] == "application/zip"
    assert archive.headers["x-content-type-options"] == "nosniff"
    with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
        names = set(z.namelist())
    assert names == {
        "CV - Example Analytics Oy - Data Analyst.pdf", "CV - Example Analytics Oy - Data Analyst.docx",
        "Cover letter - Example Analytics Oy - Data Analyst.pdf", "Cover letter - Example Analytics Oy - Data Analyst.docx",
        "README.txt",
    }

    eml = client.get(f"/api/v1/applications/{app['id']}/email.eml")
    assert eml.status_code == 200
    message = email.message_from_bytes(eml.content)
    assert message["To"] == "jobs@example.com" and message["X-Unsent"] == "1"
    assert message["Subject"] == "Application: Data Analyst"
    assert len([p for p in message.walk() if p.get_filename()]) == 2

    # Recording: the reviewed hash must match; nothing is sent by DuuniScript.
    stale = client.post(
        f"/api/v1/applications/{app['id']}/submission",
        json={"confirm": True, "package_hash": "0" * 64, "method": "web_form"},
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "package_changed"
    sent = client.post(
        f"/api/v1/applications/{app['id']}/submission",
        json={"confirm": True, "package_hash": ready["package_hash"], "method": "web_form", "confirmation_reference": "REF-1"},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "submitted" and sent.json()["submission_method"] == "web_form"
    assert client.get(f"/api/v1/jobs/{job['id']}").json()["status"] == "applied"

    locked = client.put(f"/api/v1/applications/{app['id']}/drafts/cv", json={"content": "x"})
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "application_locked"
    assert client.delete(f"/api/v1/applications/{app['id']}?confirm=true").status_code == 409
    events = [e["event_type"] for e in client.get(f"/api/v1/applications/{app['id']}/events").json()]
    assert events == ["cover_letter_approved", "cv_approved", "ready", "reopened", "cv_approved", "ready", "submitted_by_user"]
    assert client.post(f"/api/v1/applications/{app['id']}/withdraw").json()["status"] == "withdrawn"


def test_not_ready_package_and_exports(client: TestClient, verified: list[dict], job: dict) -> None:
    app = _start(client, job)
    assert client.get(f"/api/v1/applications/{app['id']}/package").json()["ready"] is False
    assert client.get(f"/api/v1/applications/{app['id']}/package.zip").status_code == 409
    assert client.get(f"/api/v1/applications/{app['id']}/email.eml").status_code == 409
    for fmt, start in (("pdf", b"%PDF"), ("docx", b"PK"), ("md", b"# Testi")):
        response = client.get(f"/api/v1/applications/{app['id']}/drafts/cv/export?format={fmt}")
        assert response.status_code == 200 and response.content.startswith(start)
        assert "(draft)" in response.headers["content-disposition"]
    assert client.get(f"/api/v1/applications/{app['id']}/drafts/cv/export?format=exe").status_code == 422


def test_uploaded_cv_and_no_letter(client: TestClient, verified: list[dict], job: dict) -> None:
    from tests.files import make_pdf

    upload = client.post(
        "/api/v1/documents", files={"file": ("my cv.pdf", io.BytesIO(make_pdf()), "application/pdf")}, data={"category": "cv"}
    ).json()
    app = _start(client, job, cv_source="uploaded", cv_document_id=upload["id"], include_cover_letter=False)
    assert app["cv"]["source"] == "uploaded" and app["cv"]["content"] is None and app["cover_letter"] is None
    assert app["cv"]["document_name"] == "my cv.pdf"
    assert app["cv"]["content_sha256"] == upload["sha256"]
    approved = client.post(f"/api/v1/applications/{app['id']}/drafts/cv/approve", json={})
    assert approved.status_code == 200
    ready = client.get(f"/api/v1/applications/{app['id']}").json()
    assert ready["status"] == "ready"
    export = client.get(f"/api/v1/applications/{app['id']}/drafts/cv/export")
    assert export.content == make_pdf()
    assert client.delete(f"/api/v1/documents/{upload['id']}?confirm=true").json()["error"]["code"] == "document_in_use"

    # Adding a cover letter later creates a draft and reopens the application.
    patched = client.patch(f"/api/v1/applications/{app['id']}", json={"include_cover_letter": True}).json()
    assert patched["status"] == "draft" and patched["cover_letter"]["version"] == 1
    patched = client.patch(f"/api/v1/applications/{app['id']}", json={"include_cover_letter": False}).json()
    assert patched["status"] == "ready" and patched["cover_letter"] is None


def test_regenerate_with_other_template(client: TestClient, verified: list[dict], job: dict) -> None:
    app = _start(client, job)
    response = client.post(f"/api/v1/applications/{app['id']}/drafts/cv/regenerate", json={"template": "projects_first"})
    assert response.status_code == 200
    assert response.json()["version"] == 2 and response.json()["template"] == "projects_first"
    bad = client.post(f"/api/v1/applications/{app['id']}/drafts/cv/regenerate", json={"template": "fancy"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "unknown_template"
    letter = client.post(f"/api/v1/applications/{app['id']}/drafts/cover_letter/regenerate", json={"template": "short"})
    assert letter.json()["template"] == "short"


def test_delete_unsent_and_list(client: TestClient, verified: list[dict], job: dict) -> None:
    app = _start(client, job)
    listed = client.get("/api/v1/applications?status=draft").json()
    assert listed["total"] == 1 and listed["items"][0]["job"]["title"] == "Data Analyst"
    assert client.delete(f"/api/v1/applications/{app['id']}").json()["error"]["code"] == "confirmation_required"
    assert client.delete(f"/api/v1/applications/{app['id']}?confirm=true").status_code == 204
    assert client.get(f"/api/v1/applications/{app['id']}").status_code == 404


def test_merging_jobs_keeps_the_application(client: TestClient, verified: list[dict], job: dict) -> None:
    other = client.post("/api/v1/jobs", json={**JOB, "application_url": None, "location": "Turku, Finland"}).json()
    app = _start(client, job)
    merged = client.post(f"/api/v1/jobs/{job['id']}/merge", json={"into_job_id": other["id"]})
    assert merged.status_code == 200, merged.text
    assert client.get(f"/api/v1/applications/{app['id']}").json()["job"]["id"] == other["id"]


def test_profile_delete_removes_applications(client: TestClient, verified: list[dict], job: dict) -> None:
    _start(client, job)
    response = client.delete("/api/v1/profile?confirm=true")
    assert response.status_code == 200, response.text


def test_slash_in_job_title_keeps_file_names_apart(client: TestClient, verified: list[dict]) -> None:
    job = client.post("/api/v1/jobs", json={**JOB, "title": "Growth Analyst (m/f/d)", "application_url": None}).json()
    app = _approve_all(client, _start(client, job))
    names = [f["filename"] for f in client.get(f"/api/v1/applications/{app['id']}/package").json()["files"]]
    assert names == [
        "CV - Example Analytics Oy - Growth Analyst (m-f-d).pdf",
        "Cover letter - Example Analytics Oy - Growth Analyst (m-f-d).pdf",
    ]
    with zipfile.ZipFile(io.BytesIO(client.get(f"/api/v1/applications/{app['id']}/package.zip").content)) as z:
        assert len(z.namelist()) == 5


# ---------- UTU Rekry templates ----------


def test_utu_cv_layout() -> None:
    facts = [*_views(FACTS),
             drafting.FactView("t1", "achievement", "Board member · Example Student Union", "Board member", date(2024, 1, 1), date(2024, 12, 31)),
             drafting.FactView("r1", "reference", "Example Referee", "Example Referee. Lecturer, Example University")]
    cv = drafting.build_cv(PERSON, facts, JOBVIEW, "utu_rekry", date(2026, 11, 14)).content
    assert "*Curriculum Vitae · 14 November 2026*" in cv
    order = [line[3:] for line in cv.splitlines() if line.startswith("## ")]
    assert order == ["Profile", "Education", "Experience", "Projects", "Positions of trust", "Languages",
                     "IT skills", "References"]
    assert "- Board member · Example Student Union (2024)" in cv
    assert "- Example Referee: Lecturer, Example University" in cv


def test_utu_letter_layout() -> None:
    letter = drafting.build_cover_letter(PERSON, _views(FACTS), JOBVIEW, "utu_rekry", date(2026, 11, 14)).content
    lines = letter.splitlines()
    assert lines[0] == "Job application · 14 November 2026"
    assert "## Data Analyst" in lines and "Example Analytics Oy" in lines
    assert letter.index(drafting.MOTIVATION_PLACEHOLDER) < letter.index("The position calls for")
    assert "As Data Analyst at Sample Data Ltd (Oct 2024 – Jun 2025), I built SQL pipelines" in letter
    assert drafting.UTU_CLOSING in letter
    assert letter.rstrip().endswith("Appendices: CV\nCopies of certificates available when requested")
    assert "Yours sincerely,\nTesti Käyttäjä" in letter
    assert "Data analyst with synthetic experience" not in letter  # the CV profile is not repeated


def test_utu_defaults_same_font_and_length_checks(client: TestClient, verified: list[dict], job: dict) -> None:
    app = _start(client, job)
    assert app["cv"]["template"] == "utu_rekry" and app["cover_letter"]["template"] == "utu_rekry"
    from app.services import rendering

    letter_style = rendering.style_for("utu_rekry", "cover_letter", "utu_rekry")
    assert letter_style.font_files == rendering.STYLES["utu_rekry"].font_files
    assert rendering.style_for("standard", "cover_letter", "classic").docx_font == "Georgia"

    long_text = app["cv"]["content"] + "\n".join(f"\nFiller paragraph number {i}." for i in range(400))
    edited = client.put(f"/api/v1/applications/{app['id']}/drafts/cv", json={"content": long_text}).json()
    assert any(i["code"] == "too_long" for i in edited["issues"])

    sentence = "I built SQL pipelines for reporting and shared the results with the whole team."
    letter = app["cover_letter"]["content"].replace("Kind regards", sentence + "\n\nKind regards")
    client.put(f"/api/v1/applications/{app['id']}/drafts/cover_letter", json={"content": letter + "\n" + sentence})
    cv = client.put(f"/api/v1/applications/{app['id']}/drafts/cv", json={"content": app["cv"]["content"] + "\n" + sentence}).json()
    repeated = [i for i in cv["issues"] if i["code"] == "repeated_in_other_document"]
    assert repeated and repeated[0]["severity"] == "info"
