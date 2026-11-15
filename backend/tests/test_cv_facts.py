"""Fact suggestions from CV text. All CV text here is synthetic."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.persistence.models import FactCategory
from app.services.cv_facts import suggest_facts

PDF_STYLE_CV = """Testi Käyttäjä
Data Analytics
+358 40 000 0000 · testi.kayttaja@example.com · github.com/testi-example · linkedin.com/in/testi-example
Based in Turku
PROFILE
Data analyst with synthetic experience in pipelines and reporting
for non-technical readers.
EXPERIENCE
Data Analyst · Example Analytics Oy, Turku · Contract Oct 2024 – Jun 2025
Built data pipelines and warehousing for internal systems.
Ran self-hosted analytics stacks.
Junior Developer · Sample Software Ltd, Helsinki Sep 2022 – Present
Developed reporting tools in Python.
PROJECTS
Example Dashboard · open data visualisation 2025
Built with Python, DuckDB and React.
EDUCATION
MSc (Tech), Example Studies ·
Example University
Aug 2025 – exp. 2027
Dean's list 2025–2026 · 60 of 120 ECTS
BSc, Computer Science · Sample College, Tampere 2019 – 2022
CGPA 3.5 / 4.0 · thesis published at Example Conference 2023
SKILLS
Analysis SQL, PostgreSQL, Python (pandas, NumPy), Excel, statistical
analysis, survey analysis
Tools Git, Docker
Languages Finnish (native) · English (C1) · Swedish (basic)
Certificates Example Data Certificate (2024) · Sample Cloud Basics (2023)
RECOMMENDATIONS
Referee Person, Example Company, referee@example.com
"""

WEB_STYLE_CV = """Testi Käyttäjä

Personal email testi.kayttaja@example.com

Phone (+358) 40 000 0000

Projects

Example Tracker

Built with Python and FastAPI.

A synthetic project that tracks example data and reports it.

Experience

Data Analyst

Example Analytics Oy, Turku. Contract, October 2024 to June 2025.

Built pipelines for internal systems.

Languages

Finnish (native) English (C1 to C2)
"""


def _by(items, category):  # noqa: ANN001, ANN202
    return [s for s in items if s.category == category]


def test_contact_details() -> None:
    items = suggest_facts(PDF_STYLE_CV)
    contact = {s.subject: s.value_text for s in _by(items, FactCategory.CONTACT)}
    assert contact["Email"] == "testi.kayttaja@example.com"
    assert contact["Phone"] == "+358 40 000 0000"
    assert contact["GitHub"] == "github.com/testi-example"
    assert contact["LinkedIn"] == "linkedin.com/in/testi-example"
    assert "(+358) 40 000 0000" in [s.value_text for s in _by(suggest_facts(WEB_STYLE_CV), FactCategory.CONTACT)]


def test_experience_entries_with_dates() -> None:
    work = _by(suggest_facts(PDF_STYLE_CV), FactCategory.WORK_EXPERIENCE)
    assert [w.subject for w in work] == [
        "Data Analyst · Example Analytics Oy, Turku · Contract",
        "Junior Developer · Sample Software Ltd, Helsinki",
    ]
    assert (work[0].valid_from, work[0].valid_until) == (date(2024, 10, 1), date(2025, 6, 30))
    assert "Ran self-hosted analytics stacks." in work[0].value_text
    assert (work[1].valid_from, work[1].valid_until) == (date(2022, 9, 1), None)  # "Present"


def test_education_keeps_expected_end_unknown_and_ignores_lone_years() -> None:
    education = _by(suggest_facts(PDF_STYLE_CV), FactCategory.EDUCATION)
    assert len(education) == 2
    assert education[0].subject == "MSc (Tech), Example Studies · Example University"
    assert (education[0].valid_from, education[0].valid_until) == (date(2025, 8, 1), None)
    assert "Dean's list" in education[0].value_text
    assert (education[1].valid_from, education[1].valid_until) == (date(2019, 1, 1), date(2022, 12, 31))
    assert "thesis published" in education[1].value_text  # a detail, not a third entry


def test_skills_languages_and_certificates() -> None:
    items = suggest_facts(PDF_STYLE_CV)
    skills = [s.subject for s in _by(items, FactCategory.SKILL)]
    assert "Python (pandas, NumPy)" in skills  # commas inside brackets do not split
    assert "statistical analysis" in skills  # wrapped line joined
    assert "PostgreSQL" in skills and "Docker" in skills
    languages = {s.subject: s.value_text for s in _by(items, FactCategory.LANGUAGE)}
    assert languages == {"Finnish": "Finnish (native)", "English": "English (C1)", "Swedish": "Swedish (basic)"}
    certificates = [s.subject for s in _by(items, FactCategory.CERTIFICATION)]
    assert certificates == ["Example Data Certificate (2024)", "Sample Cloud Basics (2023)"]


def test_references_are_never_suggested() -> None:
    values = " ".join(s.value_text for s in suggest_facts(PDF_STYLE_CV))
    assert "referee@example.com" not in values and "Referee Person" not in values


def test_web_page_cv_layout() -> None:
    items = suggest_facts(WEB_STYLE_CV)
    projects = _by(items, FactCategory.PROJECT)
    assert [p.subject for p in projects] == ["Example Tracker"]
    assert "tracks example data" in projects[0].value_text
    work = _by(items, FactCategory.WORK_EXPERIENCE)
    assert work[0].subject.startswith("Data Analyst · Example Analytics Oy")
    assert (work[0].valid_from, work[0].valid_until) == (date(2024, 10, 1), date(2025, 6, 30))
    assert {s.subject for s in _by(items, FactCategory.LANGUAGE)} == {"Finnish", "English"}


def test_text_without_sections_gives_contacts_only() -> None:
    items = suggest_facts("Just a note with no headings. Call +358 40 111 2222.")
    assert [s.category for s in items] == [FactCategory.CONTACT]


# ---------- API ----------


def _upload(client: TestClient, text: str, name: str = "cv.txt") -> dict:
    response = client.post(
        "/api/v1/documents",
        files={"file": (name, text.encode("utf-8"), "text/plain")},
        data={"category": "cv"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_suggest_import_and_verify(client: TestClient, profile: dict) -> None:
    document = _upload(client, PDF_STYLE_CV)
    response = client.get(f"/api/v1/documents/{document['id']}/fact-suggestions")
    assert response.status_code == 200
    body = response.json()
    assert body["parser_version"] == "cv-facts-1"
    assert all(not item["already_in_profile"] for item in body["items"])
    chosen = [i for i in body["items"] if i["category"] in ("work_experience", "skill")][:4]
    payload = {
        "document_id": document["id"],
        "items": [{k: i[k] for k in ("category", "subject", "value_text", "valid_from", "valid_until", "excerpt")} for i in chosen],
    }
    imported = client.post("/api/v1/profile/facts/import", json=payload)
    assert imported.status_code == 201, imported.text
    result = imported.json()
    assert result["created"] == 4 and result["skipped_existing"] == 0
    assert {f["verification_status"] for f in result["facts"]} == {"unverified"}
    evidence = client.get(f"/api/v1/profile/facts/{result['facts'][0]['id']}/evidence").json()
    assert evidence[0]["document_id"] == document["id"] and evidence[0]["source_type"] == "document"

    again = client.post("/api/v1/profile/facts/import", json=payload).json()
    assert again["created"] == 0 and again["skipped_existing"] == 4
    marked = client.get(f"/api/v1/documents/{document['id']}/fact-suggestions").json()["items"]
    assert sum(i["already_in_profile"] for i in marked) == 4

    ids = [f["id"] for f in result["facts"]]
    verified = client.post("/api/v1/profile/facts/verify", json={"fact_ids": ids})
    assert verified.status_code == 200
    assert verified.json()["verified"] == 4
    assert {f["verification_status"] for f in verified.json()["facts"]} == {"verified"}
    assert client.post("/api/v1/profile/facts/verify", json={"fact_ids": ids}).json()["verified"] == 0


def test_verify_refuses_unknown_ids(client: TestClient, fact: dict) -> None:
    response = client.post(
        "/api/v1/profile/facts/verify", json={"fact_ids": [fact["id"], "00000000-0000-4000-8000-999999999999"]}
    )
    assert response.status_code == 404
    assert client.get(f"/api/v1/profile/facts/{fact['id']}").json()["verification_status"] == "unverified"


def test_suggestions_need_extracted_text(client: TestClient, profile: dict) -> None:
    import io

    from tests.files import make_pdf

    response = client.post(
        "/api/v1/documents", files={"file": ("scan.pdf", io.BytesIO(make_pdf(None)), "application/pdf")}, data={"category": "cv"}
    )
    assert response.status_code == 201
    result = client.get(f"/api/v1/documents/{response.json()['id']}/fact-suggestions")
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "no_extracted_text"


def test_import_refuses_bad_date_range(client: TestClient, profile: dict) -> None:
    document = _upload(client, PDF_STYLE_CV)
    item = {"category": "education", "subject": "X", "value_text": "X", "valid_from": "2022-01-01", "valid_until": "2020-01-01"}
    response = client.post("/api/v1/profile/facts/import", json={"document_id": document["id"], "items": [item]})
    assert response.status_code == 422
