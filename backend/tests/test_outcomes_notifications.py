"""Application outcomes and in-app notifications. Synthetic data only."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import update

from app.persistence.models import Application
from tests.test_applications import FACTS, JOB, _approve_all, _start  # noqa: F401 - fixtures below


def _verified(client: TestClient) -> None:
    ids = [client.post("/api/v1/profile/facts", json=f).json()["id"] for f in FACTS]
    client.post("/api/v1/profile/facts/verify", json={"fact_ids": ids})


def _sent(client: TestClient) -> dict:
    job = client.post("/api/v1/jobs", json=JOB).json()
    app = _approve_all(client, _start(client, job))
    sent = client.post(f"/api/v1/applications/{app['id']}/submission",
                       json={"confirm": True, "package_hash": app["package_hash"], "method": "email"})
    assert sent.status_code == 200
    return sent.json()


def test_outcome_flow(client: TestClient, profile: dict) -> None:
    _verified(client)
    job = client.post("/api/v1/jobs", json={**JOB, "title": "Other role"}).json()
    draft = _start(client, job)
    early = client.put(f"/api/v1/applications/{draft['id']}/outcome", json={"outcome": "interview"})
    assert early.status_code == 409 and early.json()["error"]["code"] == "application_not_sent"

    app = _sent(client)
    rec = client.put(f"/api/v1/applications/{app['id']}/outcome", json={"outcome": "interview", "outcome_on": "2026-11-20"})
    assert rec.status_code == 200
    assert rec.json()["outcome"] == "interview" and rec.json()["outcome_on"] == "2026-11-20"
    assert client.get("/api/v1/dashboard").json()["counts"]["interviews"] == 1
    client.put(f"/api/v1/applications/{app['id']}/outcome", json={"outcome": "offer"})
    counts = client.get("/api/v1/dashboard").json()["counts"]
    assert counts["interviews"] == 0 and counts["offers"] == 1
    cleared = client.put(f"/api/v1/applications/{app['id']}/outcome", json={"outcome": None}).json()
    assert cleared["outcome"] is None and cleared["outcome_on"] is None
    events = [e["event_type"] for e in client.get(f"/api/v1/applications/{app['id']}/events").json()]
    assert events.count("outcome_recorded") == 3
    assert client.put(f"/api/v1/applications/{app['id']}/outcome", json={"outcome": "hired"}).status_code == 422


def test_notifications(client: TestClient, profile: dict) -> None:
    _verified(client)
    soon = (date.today() + timedelta(days=2)).isoformat()
    good = client.post("/api/v1/jobs", json={**JOB, "title": "Data Analyst", "company": "Good Oy",
                                              "description": "Data analyst work with SQL, Python and Excel reporting."}).json()
    saved = client.post("/api/v1/jobs", json={"title": "Chef", "company": "Kitchen Oy", "deadline_on": soon}).json()
    client.patch(f"/api/v1/jobs/{saved['id']}", json={"status": "saved"})

    body = client.get("/api/v1/notifications").json()
    kinds = {(n["kind"], n["entity_id"]) for n in body["items"]}
    assert ("good_match", good["id"]) in kinds
    assert ("deadline_soon", saved["id"]) in kinds
    assert body["unread"] == len(body["items"])
    deadline = next(n for n in body["items"] if n["kind"] == "deadline_soon")
    assert deadline["title"] == "Deadline in 2 days: Chef" and deadline["link"] == f"/jobs/{saved['id']}"

    # Read, dismiss: a dismissed notice never comes back.
    assert client.post(f"/api/v1/notifications/{deadline['id']}/read").json()["read_at"]
    client.post(f"/api/v1/notifications/{deadline['id']}/dismiss")
    again = client.get("/api/v1/notifications").json()
    assert deadline["id"] not in {n["id"] for n in again["items"]}
    assert ("deadline_soon", saved["id"]) not in {(n["kind"], n["entity_id"]) for n in again["items"]}
    assert client.post("/api/v1/notifications/read-all").json()["marked"] >= 1
    assert client.get("/api/v1/notifications").json()["unread"] == 0
    assert client.post("/api/v1/notifications/00000000-0000-4000-8000-999999999999/read").status_code == 404


def test_ready_and_follow_up_notifications(client: TestClient, profile: dict) -> None:
    _verified(client)
    app = _sent(client)
    old = datetime.now(timezone.utc) - timedelta(days=15)
    factory = client.app.state.session_factory
    with factory() as session:
        session.execute(update(Application).where(Application.id == app["id"]).values(submitted_at=old))
        session.commit()
    job2 = client.post("/api/v1/jobs", json={**JOB, "company": "Second Oy"}).json()
    ready = _approve_all(client, _start(client, job2))
    with factory() as session:
        session.execute(update(Application).where(Application.id == ready["id"]).values(ready_at=old))
        session.commit()
    kinds = {(n["kind"], n["entity_id"]) for n in client.get("/api/v1/notifications").json()["items"]}
    assert ("follow_up", app["id"]) in kinds and ("ready_not_sent", ready["id"]) in kinds
