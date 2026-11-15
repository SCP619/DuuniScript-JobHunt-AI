from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

FACTS = "/api/v1/profile/facts"


def test_facts_require_profile(client: TestClient) -> None:
    response = client.post(FACTS, json={"category": "skill", "subject": "Python", "value_text": "Python"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "profile_not_found"


def test_new_fact_is_unverified(fact: dict) -> None:
    assert fact["verification_status"] == "unverified"
    assert fact["verified_at"] is None
    assert fact["evidence_count"] == 0


def test_cannot_create_fact_as_verified(client: TestClient, profile: dict) -> None:
    response = client.post(
        FACTS,
        json={"category": "skill", "subject": "Python", "value_text": "Python", "verification_status": "verified"},
    )
    assert response.status_code == 422


def test_invalid_category_and_date_range(client: TestClient, profile: dict) -> None:
    assert client.post(FACTS, json={"category": "superpower", "subject": "x", "value_text": "x"}).status_code == 422
    response = client.post(
        FACTS,
        json={
            "category": "work_experience",
            "subject": "Example Oy",
            "value_text": "Developer",
            "valid_from": "2023-01-01",
            "valid_until": "2022-01-01",
        },
    )
    assert response.status_code == 422
    error = response.json()["error"]
    # Same stable code as editing, so the UI can show it on the date fields.
    assert error["code"] == "invalid_date_range"
    assert error["details"]["fields"][0]["loc"] == ["body", "valid_until"]


def test_verify_sets_verified_at(client: TestClient, fact: dict) -> None:
    response = client.patch(f"{FACTS}/{fact['id']}", json={"verification_status": "verified"})
    assert response.status_code == 200
    body = response.json()
    assert body["verification_status"] == "verified"
    assert body["verified_at"] is not None


def test_editing_verified_fact_resets_verification(client: TestClient, fact: dict) -> None:
    client.patch(f"{FACTS}/{fact['id']}", json={"verification_status": "verified"})
    body = client.patch(f"{FACTS}/{fact['id']}", json={"value_text": "MSc (corrected, synthetic)"}).json()
    assert body["verification_status"] == "unverified"
    assert body["verified_at"] is None


def test_edit_and_reverify_in_one_request(client: TestClient, fact: dict) -> None:
    client.patch(f"{FACTS}/{fact['id']}", json={"verification_status": "verified"})
    body = client.patch(
        f"{FACTS}/{fact['id']}", json={"value_text": "MSc (edited)", "verification_status": "verified"}
    ).json()
    assert body["verification_status"] == "verified"
    assert body["value_text"] == "MSc (edited)"


def test_noop_edit_keeps_verification(client: TestClient, fact: dict) -> None:
    client.patch(f"{FACTS}/{fact['id']}", json={"verification_status": "verified"})
    body = client.patch(f"{FACTS}/{fact['id']}", json={"value_text": fact["value_text"]}).json()
    assert body["verification_status"] == "verified"


def test_reject_and_expire(client: TestClient, fact: dict) -> None:
    client.patch(f"{FACTS}/{fact['id']}", json={"verification_status": "verified"})
    expired = client.patch(f"{FACTS}/{fact['id']}", json={"verification_status": "expired"}).json()
    assert expired["verification_status"] == "expired"
    assert expired["verified_at"] is not None  # keeps when it was last verified
    rejected = client.patch(f"{FACTS}/{fact['id']}", json={"verification_status": "rejected"}).json()
    assert rejected["verification_status"] == "rejected"
    assert rejected["verified_at"] is None


def test_patch_date_range_checked_against_stored_values(client: TestClient, fact: dict) -> None:
    response = client.patch(f"{FACTS}/{fact['id']}", json={"valid_from": "2030-01-01"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_date_range"


def test_patch_null_required_field_rejected(client: TestClient, fact: dict) -> None:
    assert client.patch(f"{FACTS}/{fact['id']}", json={"subject": None}).status_code == 422


def test_list_filter_and_paginate(client: TestClient, fact: dict) -> None:
    for i in range(3):
        client.post(FACTS, json={"category": "skill", "subject": f"Skill {i}", "value_text": f"Synthetic {i}"})
    client.patch(f"{FACTS}/{fact['id']}", json={"verification_status": "verified"})

    all_facts = client.get(FACTS).json()
    assert all_facts["total"] == 4

    skills = client.get(FACTS, params={"category": "skill", "limit": 2}).json()
    assert skills["total"] == 3
    assert len(skills["items"]) == 2
    page2 = client.get(FACTS, params={"category": "skill", "limit": 2, "offset": 2}).json()
    assert len(page2["items"]) == 1

    verified = client.get(FACTS, params={"verification_status": "verified"}).json()
    assert [f["id"] for f in verified["items"]] == [fact["id"]]

    assert client.get(FACTS, params={"limit": 0}).status_code == 422
    assert client.get(FACTS, params={"limit": 1000}).status_code == 422


def test_get_unknown_and_malformed_fact_ids(client: TestClient, profile: dict) -> None:
    missing = client.get(f"{FACTS}/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "fact_not_found"
    assert client.get(f"{FACTS}/not-a-uuid").status_code == 422


def test_delete_fact(client: TestClient, fact: dict) -> None:
    assert client.delete(f"{FACTS}/{fact['id']}").status_code == 204
    assert client.get(f"{FACTS}/{fact['id']}").status_code == 404


def test_evidence_does_not_verify_fact(client: TestClient, fact: dict) -> None:
    response = client.post(
        f"{FACTS}/{fact['id']}/evidence",
        json={"source_type": "url", "source_reference": "https://example.com/diploma", "excerpt": "Synthetic"},
    )
    assert response.status_code == 201
    evidence = response.json()
    assert evidence["verification_status"] == "unverified"

    updated = client.get(f"{FACTS}/{fact['id']}").json()
    assert updated["verification_status"] == "unverified"
    assert updated["evidence_count"] == 1

    listed = client.get(f"{FACTS}/{fact['id']}/evidence").json()
    assert [e["id"] for e in listed] == [evidence["id"]]


def test_evidence_validation(client: TestClient, fact: dict) -> None:
    url = f"{FACTS}/{fact['id']}/evidence"
    bad_url = client.post(url, json={"source_type": "url", "source_reference": "javascript:alert(1)"})
    assert bad_url.status_code == 422
    assert bad_url.json()["error"]["details"]["fields"][0]["loc"] == ["body", "source_reference"]
    no_doc = client.post(url, json={"source_type": "document"})
    assert no_doc.status_code == 422
    assert no_doc.json()["error"]["code"] == "validation_error"
    assert no_doc.json()["error"]["details"]["fields"][0]["loc"] == ["body", "document_id"]
    assert client.get(url).json() == []
    assert client.post(url, json={"source_type": "telepathy"}).status_code == 422
    assert client.post(url, json={"source_type": "user_input", "excerpt": "x" * 2001}).status_code == 422


def test_fact_deletion_removes_evidence(client: TestClient, fact: dict) -> None:
    client.post(f"{FACTS}/{fact['id']}/evidence", json={"source_type": "user_input"})
    client.delete(f"{FACTS}/{fact['id']}")
    assert client.get(f"{FACTS}/{fact['id']}/evidence").status_code == 404
