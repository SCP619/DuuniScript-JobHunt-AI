"""Job match scores from verified facts. Synthetic data only."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.persistence.models import Job
from app.services import drafting, match_service

FACTS = [
    {"category": "skill", "subject": "Analysis SQL", "value_text": "Analysis SQL"},
    {"category": "skill", "subject": "Python", "value_text": "Python"},
    {"category": "skill", "subject": "Excel", "value_text": "Excel"},
    {"category": "work_experience", "subject": "Data Analyst · Example Oy", "value_text": "Built reports with Power BI."},
    {"category": "language", "subject": "English", "value_text": "English (C1)"},
    {"category": "language", "subject": "Finnish", "value_text": "Finnish (beginner)"},
]


def _views() -> list[drafting.FactView]:
    return [drafting.FactView(str(i), f["category"], f["subject"], f["value_text"]) for i, f in enumerate(FACTS)]


def _job(**values) -> Job:  # noqa: ANN003
    base = {"title": "Data Analyst", "company": "Example", "description": "", "available_from_finland": "yes"}
    return Job(**{**base, **values})


TODAY = date(2026, 11, 11)


def test_skills_role_and_reasons() -> None:
    job = _job(description="We need SQL, Python, Power BI and Docker skills.")
    score, details = match_service.score_job(job, _views(), TODAY)
    assert details["matched_skills"] == ["SQL", "Python", "Power BI"]  # label prefix and work text count
    assert details["missing_terms"] == ["Docker"]
    assert details["parts"]["skills"] == 45 and details["parts"]["role"] == 25
    assert score >= 70
    assert details["reasons"][0] == "Matches 3 of 4 skills the posting names: SQL, Python, Power BI."
    assert details["blockers"] == []


def test_unrelated_job_scores_low() -> None:
    job = _job(title="Registered Nurse", description="Patient care in a hospital ward. Kubernetes is not needed.")
    score, details = match_service.score_job(job, _views(), TODAY)
    assert score < 20
    assert details["missing_terms"] == ["Kubernetes"]


def test_blockers_cap_the_score() -> None:
    job = _job(description="SQL and Python. Fluent Finnish is required.", deadline_on=date(2026, 11, 1),
               available_from_finland="no")
    score, details = match_service.score_job(job, _views(), TODAY)
    assert {b["code"] for b in details["blockers"]} == {"not_open_to_finland", "deadline_passed", "language_required"}
    assert score <= match_service.BLOCKER_CAP


def test_language_as_advantage_is_not_a_blocker() -> None:
    assert match_service.language_requirements("Finnish language skills are an advantage.") == []
    assert match_service.language_requirements("Edellytämme sujuvaa suomen kielen taitoa.") == ["Finnish"]
    assert match_service.language_requirements("Swedish is a plus") == []
    fluent = [*_views(), drafting.FactView("x", "language", "Swedish", "Swedish (native)")]
    _, details = match_service.score_job(_job(description="Fluent Swedish required."), fluent, TODAY)
    assert details["blockers"] == []


def test_no_verified_facts_gives_no_score() -> None:
    assert match_service.score_job(_job(), [], TODAY)[0] is None


# ---------- API ----------


def test_list_sort_filter_and_explain(client: TestClient, profile: dict) -> None:
    good = client.post("/api/v1/jobs", json={"title": "Data Analyst", "company": "A Oy",
                                              "description": "SQL, Python and Excel daily."}).json()
    weak = client.post("/api/v1/jobs", json={"title": "Chef", "company": "B Oy", "description": "Cooking."}).json()
    listed = client.get("/api/v1/jobs").json()["items"]
    assert {j["match_score"] for j in listed} == {None}  # nothing verified yet

    ids = [client.post("/api/v1/profile/facts", json=f).json()["id"] for f in FACTS]
    client.post("/api/v1/profile/facts", json={"category": "skill", "subject": "Cooking", "value_text": "Cooking"})  # unverified
    client.post("/api/v1/profile/facts/verify", json={"fact_ids": ids})

    by_match = client.get("/api/v1/jobs", params={"sort": "match"}).json()["items"]
    assert [j["id"] for j in by_match] == [good["id"], weak["id"]]
    assert by_match[0]["match_score"] > by_match[1]["match_score"]
    assert [j["id"] for j in client.get("/api/v1/jobs", params={"min_match": 50}).json()["items"]] == [good["id"]]

    detail = client.get(f"/api/v1/jobs/{good['id']}").json()
    assert detail["match_score"] == by_match[0]["match_score"]
    explained = client.get(f"/api/v1/jobs/{good['id']}/match").json()
    assert explained["matched_skills"] == ["SQL", "Python", "Excel"]
    assert explained["scoring_version"] == "match-3"
    assert explained["reasons"][0].startswith("Matches 3 of 3 skills")
    assert client.get(f"/api/v1/jobs/{weak['id']}/match").json()["matched_skills"] == []  # unverified Cooking ignored

    # Editing a fact (back to unverified) or the job recomputes the score.
    client.patch(f"/api/v1/jobs/{good['id']}", json={"description": "Docker and Kubernetes."})
    assert client.get(f"/api/v1/jobs/{good['id']}/match").json()["missing_terms"] == ["Docker", "Kubernetes"]
    client.patch(f"/api/v1/jobs/{good['id']}", json={"location": "New York, USA"})
    blockers = client.get(f"/api/v1/jobs/{good['id']}/match").json()["blockers"]
    assert [b["code"] for b in blockers] == ["not_open_to_finland"]
    assert client.get(f"/api/v1/jobs/{good['id']}").json()["match_has_blockers"] is True


def test_match_for_unknown_job(client: TestClient, profile: dict) -> None:
    assert client.get("/api/v1/jobs/00000000-0000-4000-8000-999999999999/match").status_code == 404


def test_concurrent_refresh_does_not_insert_twice(client: TestClient, profile: dict) -> None:
    """Page load sends several requests at once; each recomputes stale scores."""
    from concurrent.futures import ThreadPoolExecutor

    for i in range(30):
        client.post("/api/v1/jobs", json={"title": f"Data Analyst {i}", "company": f"Firm {i}", "description": "SQL"})
    fact = client.post("/api/v1/profile/facts", json={"category": "skill", "subject": "SQL", "value_text": "SQL"}).json()
    client.post("/api/v1/profile/facts/verify", json={"fact_ids": [fact["id"]]})
    with ThreadPoolExecutor(max_workers=6) as pool:
        statuses = list(pool.map(lambda path: client.get(path).status_code,
                                 ["/api/v1/dashboard", "/api/v1/jobs", "/api/v1/jobs?sort=match"] * 4))
    assert set(statuses) == {200}


def test_feedback_from_decisions() -> None:
    feedback = match_service.Feedback([
        ("a", "not_relevant", "Restaurant Chef"), ("b", "not_relevant", "Sous Chef"),
        ("c", "saved", "Data Analyst"), ("d", "applied", "Business Analyst"),
    ])
    chef = _job(title="Head Chef", description="Cooking.")
    analyst = _job(title="Junior Analyst", description="SQL and Python.")
    _, down = match_service.score_job(chef, _views(), TODAY, feedback)
    _, up = match_service.score_job(analyst, _views(), TODAY, feedback)
    assert down["parts"]["feedback"] < 0 and "marked not relevant (chef)" in down["reasons"][-1]
    assert up["parts"]["feedback"] > 0 and "saved or applied to (analyst)" in up["reasons"][-1]
    # Fewer than three decisions: no effect. A job's own decision does not count for itself.
    few = match_service.Feedback([("a", "not_relevant", "Chef")])
    assert match_service.score_job(chef, _views(), TODAY, few)[1]["parts"]["feedback"] == 0
    own = _job(title="Sous Chef")
    own.id = "b"
    solo = match_service.Feedback([("b", "not_relevant", "Sous Chef"), ("c", "saved", "Data Analyst"), ("d", "saved", "Analyst")])
    assert match_service.score_job(own, _views(), TODAY, solo)[1]["parts"]["feedback"] == 0


def test_decisions_rescore_through_api(client: TestClient, profile: dict) -> None:
    ids = [client.post("/api/v1/profile/facts", json=f).json()["id"] for f in FACTS]
    client.post("/api/v1/profile/facts/verify", json={"fact_ids": ids})
    jobs = [client.post("/api/v1/jobs", json={"title": t, "company": f"C{i} Oy"}).json() for i, t in
            enumerate(["Line Chef", "Pastry Chef", "Sushi Chef", "Grill Chef"])]
    before = client.get(f"/api/v1/jobs/{jobs[3]['id']}").json()["match_score"]
    for job in jobs[:3]:
        client.patch(f"/api/v1/jobs/{job['id']}", json={"status": "not_relevant"})
    after = client.get(f"/api/v1/jobs/{jobs[3]['id']}/match").json()
    assert after["parts"]["feedback"] < 0 and after["score"] <= before
