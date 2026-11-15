"""Test fixtures. All data is synthetic; every test gets its own temporary APP_DATA_DIR."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.fake_web import FakeWeb


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # No background feed checks in tests (they are triggered explicitly).
    return Settings(
        app_data_dir=tmp_path / "DuuniScriptTest", feed_sync_interval_minutes=0, backup_interval_hours=0,
        mail_sync_interval_minutes=0, rag_index_interval_minutes=0, housekeeping_interval_minutes=0,
        desktop_notifications=False, _env_file=None
    )


@pytest.fixture
def fake_web() -> FakeWeb:
    return FakeWeb()


@pytest.fixture
def client(settings: Settings, fake_web: FakeWeb) -> Iterator[TestClient]:
    app = create_app(settings)
    # Tests never reach the real internet.
    app.state.fetcher = fake_web.fetcher()
    app.state.feed_fetcher = fake_web.fetcher()
    # Connected accounts: tokens in memory, never the real Credential Manager or network.
    from app.adapters.oauth_mail import MemoryTokenStore
    from app.services.integration_service import Integrations

    app.state.integrations = Integrations(settings, tokens=MemoryTokenStore())
    with TestClient(app) as test_client:
        yield test_client


SYNTHETIC_PROFILE = {
    "display_name": "Testi Käyttäjä",
    "email": "testi.kayttaja@example.com",
    "phone": "+358 40 000 0000",
    "location": "Turku",
    "professional_summary": "Synthetic profile used only for automated tests.",
}


@pytest.fixture
def profile(client: TestClient) -> dict:
    response = client.put("/api/v1/profile", json=SYNTHETIC_PROFILE)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def fact(client: TestClient, profile: dict) -> dict:
    response = client.post(
        "/api/v1/profile/facts",
        json={
            "category": "education",
            "subject": "Example University",
            "value_text": "MSc in Example Studies (synthetic)",
            "valid_from": "2020-09-01",
            "valid_until": "2022-06-30",
        },
    )
    assert response.status_code == 201
    return response.json()
