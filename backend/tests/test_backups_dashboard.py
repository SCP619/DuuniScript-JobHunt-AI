"""Backups, restore script and the dashboard summary. Synthetic data only."""

from __future__ import annotations

import io
import sqlite3
import subprocess
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.services import backup_service
from tests.files import make_pdf

ROOT = Path(__file__).resolve().parents[2]


def _with_document(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/documents", files={"file": ("cv.pdf", io.BytesIO(make_pdf()), "application/pdf")}, data={"category": "cv"}
    )
    assert response.status_code == 201
    return response.json()


def test_backup_create_list_download_delete(client: TestClient, profile: dict, settings: Settings) -> None:
    _with_document(client)
    assert client.get("/api/v1/backups").json() == {"interval_hours": 0, "keep": 10, "backups": []}
    made = client.post("/api/v1/backups")
    assert made.status_code == 201
    name = made.json()["name"]
    assert backup_service.NAME.match(name)
    listed = client.get("/api/v1/backups").json()["backups"]
    assert [b["name"] for b in listed] == [name]

    download = client.get(f"/api/v1/backups/{name}")
    assert download.status_code == 200 and download.headers["x-content-type-options"] == "nosniff"
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        names = set(archive.namelist())
        assert "database/duuniscript.sqlite3" in names and "manifest.json" in names
        assert any(n.startswith("documents/originals/") for n in names)
        assert any(n.startswith("documents/extracted/") for n in names)
    assert backup_service.verify(settings.app_data_dir / "backups" / name) == []

    assert client.delete(f"/api/v1/backups/{name}").json()["error"]["code"] == "confirmation_required"
    assert client.delete(f"/api/v1/backups/{name}?confirm=true").status_code == 204
    assert client.get(f"/api/v1/backups/{name}").status_code == 404
    assert client.get("/api/v1/backups/..%5Cdatabase%5Cx.zip").status_code in (404, 422)


def test_prune_keeps_newest(client: TestClient, profile: dict, settings: Settings) -> None:
    small = settings.model_copy(update={"backup_keep": 2})
    for _ in range(3):
        backup_service.create(small)
    assert len(backup_service.list_backups(small)) == 2


def test_due_logic(settings: Settings) -> None:
    assert backup_service.due(settings) is False  # automatic backups off in tests
    on = settings.model_copy(update={"backup_interval_hours": 24})
    assert backup_service.due(on) is True  # no backup yet


def test_restore_script_round_trip(client: TestClient, profile: dict, settings: Settings, tmp_path: Path) -> None:
    document = _with_document(client)
    info = backup_service.create(settings)
    backup = settings.app_data_dir / "backups" / info.name
    target = tmp_path / "restored"
    script = [sys.executable, str(ROOT / "scripts" / "restore_backup.py"), str(backup), "--target", str(target)]
    first = subprocess.run(script, capture_output=True, text=True, check=False)
    assert first.returncode == 0, first.stdout + first.stderr
    db = sqlite3.connect(target / "database" / "duuniscript.sqlite3")
    try:
        assert db.execute("select display_name from user_profile").fetchone()[0] == profile["display_name"]
        assert db.execute("select count(*) from document where id = ?", (document["id"],)).fetchone()[0] == 1
    finally:
        db.close()  # "with" does not close a sqlite3 connection; Windows keeps the file locked
    # A second restore into the same folder is refused without --replace, then moves data aside.
    assert subprocess.run(script, capture_output=True, text=True, check=False).returncode == 1
    replaced = subprocess.run([*script, "--replace"], capture_output=True, text=True, check=False)
    assert replaced.returncode == 0, replaced.stdout
    assert any(p.name.startswith("replaced-") for p in target.iterdir())


def test_restore_refuses_damaged_or_unsafe_backup(tmp_path: Path) -> None:
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr("../evil.txt", "x")
        archive.writestr("manifest.json", '{"files": {"../evil.txt": "00"}}')
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "restore_backup.py"), str(bad), "--target", str(tmp_path / "t")],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1 and "unexpected path" in result.stdout
    assert not (tmp_path / "evil.txt").exists()


def test_dashboard(client: TestClient, profile: dict) -> None:
    soon = (date.today() + timedelta(days=3)).isoformat()
    later = (date.today() + timedelta(days=30)).isoformat()
    a = client.post("/api/v1/jobs", json={"title": "Data Analyst", "company": "A Oy", "deadline_on": soon,
                                           "description": "SQL and Python"}).json()
    client.post("/api/v1/jobs", json={"title": "Chef", "company": "B Oy", "deadline_on": later})
    hidden = client.post("/api/v1/jobs", json={"title": "Hidden", "company": "C Oy", "deadline_on": soon}).json()
    client.patch(f"/api/v1/jobs/{hidden['id']}", json={"hidden": True})
    client.patch(f"/api/v1/jobs/{a['id']}", json={"status": "saved"})
    ids = [client.post("/api/v1/profile/facts", json={"category": "skill", "subject": s, "value_text": s}).json()["id"]
           for s in ("SQL", "Python")]
    client.post("/api/v1/profile/facts/verify", json={"fact_ids": ids})

    body = client.get("/api/v1/dashboard").json()
    assert body["counts"]["jobs"] == 2 and body["counts"]["jobs_new_this_week"] == 2
    assert body["counts"]["jobs_saved"] == 1
    assert body["counts"]["applications_drafting"] == 0
    assert [j["id"] for j in body["deadlines_soon"]] == [a["id"]]
    assert body["best_matches"][0]["id"] == a["id"] and body["best_matches"][0]["match_score"] > 0
    assert body["status"]["automatic_backups"] is False and body["status"]["last_backup_at"] is None
    assert "Remotive" not in body["status"]["sources_failing"]
