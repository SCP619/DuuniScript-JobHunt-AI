"""Backups of the private data (PRD: recoverability; DBD 13).

A backup is one zip in ``APP_DATA_DIR\\backups``: a consistent copy of the SQLite database (made
with SQLite's online backup API, so it is safe while the app runs), the original documents,
their extracted text and the job source snapshots, plus ``manifest.json`` with a SHA-256 for
every file. Backups stay on this computer, outside the repository, and contain personal data:
copy them only to places you trust (e.g. an encrypted drive).

Restoring is deliberately not an API call: stop the app and run ``scripts\\restore_backup.py``.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import __version__
from app.core.config import Settings
from app.core.errors import AppError, not_found

BACKUP_DIR = "backups"
INCLUDED_DIRS = ("documents/originals", "documents/extracted", "source_snapshots", "job_screenshots")
NAME = re.compile(r"^DuuniScript-backup-\d{8}-\d{6}(?:-\d+)?\.zip$")
_LOCK = threading.Lock()


@dataclass(frozen=True)
class BackupInfo:
    name: str
    size_bytes: int
    created_at: datetime


def _dir(settings: Settings) -> Path:
    path = settings.app_data_dir / BACKUP_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _info(path: Path) -> BackupInfo:
    stat = path.stat()
    return BackupInfo(path.name, stat.st_size, datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc))


def list_backups(settings: Settings) -> list[BackupInfo]:
    items = [_info(p) for p in _dir(settings).iterdir() if p.is_file() and NAME.match(p.name)]
    return sorted(items, key=lambda b: (b.created_at, b.name), reverse=True)


def create(settings: Settings, reason: str = "manual") -> BackupInfo:
    if not _LOCK.acquire(blocking=False):
        raise AppError(409, "backup_in_progress", "A backup is already being made.")
    try:
        folder = _dir(settings)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        target = folder / f"DuuniScript-backup-{stamp}.zip"
        n = 1
        while target.exists():
            n += 1
            target = folder / f"DuuniScript-backup-{stamp}-{n}.zip"
        part = target.with_suffix(".zip.part")
        files: dict[str, str] = {}
        with tempfile.TemporaryDirectory(dir=folder, prefix=".backup-") as tmp:
            db_copy = Path(tmp) / "duuniscript.sqlite3"
            source = sqlite3.connect(settings.database_path)
            try:
                dest = sqlite3.connect(db_copy)
                try:
                    source.backup(dest)
                finally:
                    dest.close()
            finally:
                source.close()
            try:
                with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.write(db_copy, "database/duuniscript.sqlite3")
                    files["database/duuniscript.sqlite3"] = _sha256(db_copy)
                    for sub in INCLUDED_DIRS:
                        base = settings.app_data_dir / sub
                        if not base.is_dir():
                            continue
                        for path in sorted(base.rglob("*")):
                            if path.is_file() and not path.name.endswith(".part"):
                                name = path.relative_to(settings.app_data_dir).as_posix()
                                archive.write(path, name)
                                files[name] = _sha256(path)
                    manifest = {
                        "app_version": __version__,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "reason": reason,
                        "files": files,
                    }
                    archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
                part.replace(target)
            except BaseException:
                part.unlink(missing_ok=True)
                raise
        prune(settings)
        return _info(target)
    finally:
        _LOCK.release()


def prune(settings: Settings) -> int:
    """Keep the newest ``backup_keep`` backups."""
    removed = 0
    for old in list_backups(settings)[settings.backup_keep:]:
        (_dir(settings) / old.name).unlink(missing_ok=True)
        removed += 1
    return removed


def path_of(settings: Settings, name: str) -> Path:
    if not NAME.match(name):
        raise not_found("backup")
    path = _dir(settings) / name
    if not path.is_file():
        raise not_found("backup")
    return path


def delete(settings: Settings, name: str) -> None:
    path_of(settings, name).unlink()


def due(settings: Settings) -> bool:
    if not settings.backup_interval_hours:
        return False
    newest = next(iter(list_backups(settings)), None)
    return newest is None or datetime.now(timezone.utc) - newest.created_at >= timedelta(hours=settings.backup_interval_hours)


def verify(path: Path) -> list[str]:
    """Names of files whose checksum does not match the manifest (empty list = intact)."""
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        bad = []
        for name, digest in manifest["files"].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                bad.append(name)
        return bad
