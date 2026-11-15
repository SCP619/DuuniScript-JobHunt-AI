from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.persistence.models import AuditEvent
from tests.conftest import SYNTHETIC_PROFILE


def test_get_profile_when_missing(client: TestClient) -> None:
    response = client.get("/api/v1/profile")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "profile_not_found"


def test_create_then_get(client: TestClient, profile: dict) -> None:
    assert profile["display_name"] == SYNTHETIC_PROFILE["display_name"]
    assert profile["created_at"].endswith(("Z", "+00:00"))
    got = client.get("/api/v1/profile").json()
    assert got["id"] == profile["id"]


def test_update_keeps_single_profile(client: TestClient, profile: dict) -> None:
    response = client.put("/api/v1/profile", json={**SYNTHETIC_PROFILE, "location": "Helsinki"})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == profile["id"]
    assert body["location"] == "Helsinki"


def test_profile_validation(client: TestClient) -> None:
    bad_email = client.put("/api/v1/profile", json={**SYNTHETIC_PROFILE, "email": "not-an-email"})
    assert bad_email.status_code == 422
    assert bad_email.json()["error"]["code"] == "validation_error"
    # Submitted values must not be echoed back in errors.
    assert "not-an-email" not in bad_email.text

    unknown_field = client.put("/api/v1/profile", json={**SYNTHETIC_PROFILE, "is_admin": True})
    assert unknown_field.status_code == 422

    blank_name = client.put("/api/v1/profile", json={**SYNTHETIC_PROFILE, "display_name": "   "})
    assert blank_name.status_code == 422


def test_delete_requires_confirmation(client: TestClient, fact: dict) -> None:
    response = client.delete("/api/v1/profile")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "confirmation_required"
    assert error["details"] == {"facts": 1, "evidence": 0, "documents": 0}
    assert client.get("/api/v1/profile").status_code == 200


def test_delete_with_confirmation_cascades(client: TestClient, fact: dict) -> None:
    client.post(f"/api/v1/profile/facts/{fact['id']}/evidence", json={"source_type": "user_input"})
    response = client.delete("/api/v1/profile", params={"confirm": "true"})
    assert response.status_code == 200
    assert response.json() == {
        "deleted": True,
        "deleted_facts": 1,
        "deleted_evidence": 1,
        "deleted_documents": 0,
    }
    assert client.get("/api/v1/profile").status_code == 404


def test_audit_records_do_not_contain_personal_values(client: TestClient, profile: dict) -> None:
    client.put("/api/v1/profile", json={**SYNTHETIC_PROFILE, "location": "Helsinki"})
    with client.app.state.session_factory() as session:
        events = session.scalars(select(AuditEvent).order_by(AuditEvent.occurred_at)).all()
    assert [e.action for e in events] == ["profile.created", "profile.updated"]
    assert events[1].details == {"fields": ["location"]}
    dumped = repr([(e.details, e.entity_id) for e in events])
    for value in SYNTHETIC_PROFILE.values():
        assert value not in dumped
    assert "Helsinki" not in dumped
