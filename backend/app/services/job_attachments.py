"""Screenshots kept with a job as a record of the posting (private files under APP_DATA_DIR)."""

from __future__ import annotations

import hashlib
import shutil
import time
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found
from app.persistence.models import JobAttachment
from app.services.storage import FileStore, make_read_only, make_writable

PENDING = "job_screenshots/pending"
PENDING_HOURS = 24


def _ext(data: bytes) -> tuple[str, str]:
    return (".png", "image/png") if data.startswith(b"\x89PNG") else (".jpg", "image/jpeg")


def keep_pending(store: FileStore, files: list[tuple[str, bytes]]) -> str:
    draft_id = uuid.uuid4().hex
    folder = store.resolve(f"{PENDING}/{draft_id}")
    folder.mkdir(parents=True, exist_ok=True)
    for i, (_, data) in enumerate(files):
        ext, _ = _ext(data)
        (folder / f"{i:02d}{ext}").write_bytes(data)
    return draft_id


def attach_pending(session: Session, store: FileStore, draft_id: str, job_id: str) -> int:
    folder = store.resolve(f"{PENDING}/{draft_id}")
    if not folder.is_dir():
        return 0  # expired or already used: the job is still saved
    target = store.resolve(f"job_screenshots/{job_id}")
    target.mkdir(parents=True, exist_ok=True)
    count = 0
    for i, path in enumerate(sorted(folder.iterdir())):
        data = path.read_bytes()
        ext, media = _ext(data)
        dest = target / f"{i:02d}{ext}"
        dest.write_bytes(data)
        make_read_only(dest)
        session.add(JobAttachment(job_id=job_id, position=i, storage_path=f"job_screenshots/{job_id}/{dest.name}",
                                  media_type=media, sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data)))
        count += 1
    shutil.rmtree(folder, ignore_errors=True)
    session.commit()
    return count


def list_for(session: Session, job_id: str) -> list[JobAttachment]:
    return list(session.scalars(select(JobAttachment).where(JobAttachment.job_id == job_id).order_by(JobAttachment.position)))


def read(session: Session, store: FileStore, job_id: str, attachment_id: str) -> tuple[bytes, str]:
    item = session.get(JobAttachment, attachment_id)
    if item is None or item.job_id != job_id:
        raise not_found("attachment")
    path = store.resolve(item.storage_path)
    if not path.is_file():
        raise AppError(404, "attachment_missing", "The screenshot file is missing.")
    return path.read_bytes(), item.media_type


def clean_pending(store: FileStore) -> int:
    root = store.resolve(PENDING)
    if not root.is_dir():
        return 0
    removed = 0
    for folder in root.iterdir():
        if folder.is_dir() and time.time() - folder.stat().st_mtime > PENDING_HOURS * 3600:
            shutil.rmtree(folder, ignore_errors=True)
            removed += 1
    return removed


def delete_for_job(store: FileStore, job_id: str) -> None:
    folder = store.resolve(f"job_screenshots/{job_id}")
    if folder.is_dir():
        for path in folder.iterdir():
            make_writable(path)
        shutil.rmtree(folder, ignore_errors=True)


__all__ = ["keep_pending", "attach_pending", "list_for", "read", "clean_pending", "delete_for_job", "Path"]
