from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import REPO_ROOT, Settings
from app.core.paths import DATA_SUBDIRS, default_data_dir


def test_default_data_dir_uses_localappdata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert default_data_dir() == tmp_path / "DuuniScript"


def test_app_data_dir_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "custom"))
    assert Settings(_env_file=None).app_data_dir == tmp_path / "custom"


def test_data_dir_inside_repo_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(app_data_dir=REPO_ROOT / "data", _env_file=None)


def test_defaults_bind_loopback() -> None:
    settings = Settings(_env_file=None)
    assert settings.api_host == "127.0.0.1"
    assert settings.is_loopback


def test_cors_origins_from_comma_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, http://127.0.0.1:3000")
    assert Settings(_env_file=None).cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]


def test_startup_creates_private_dirs_and_database(client: TestClient, settings: Settings) -> None:
    for sub in DATA_SUBDIRS:
        assert (settings.app_data_dir / sub).is_dir()
    assert settings.database_path.is_file()


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["version"]


def test_health_does_not_leak_paths(client: TestClient, settings: Settings) -> None:
    text = client.get("/health").text
    assert str(settings.app_data_dir) not in text
    assert "sqlite" not in text.lower()


def test_unknown_route_uses_error_format(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_oversized_body_rejected(client: TestClient, settings: Settings) -> None:
    payload = {"display_name": "x" * 10, "professional_summary": "y" * (settings.max_request_bytes + 10)}
    response = client.put("/api/v1/profile", json=payload)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"


def test_cors_allows_local_frontend_only(client: TestClient) -> None:
    ok = client.options(
        "/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options(
        "/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in bad.headers
