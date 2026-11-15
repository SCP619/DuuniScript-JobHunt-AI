"""Private file storage under APP_DATA_DIR.

- Files get internal names (``<uuid><ext>``); user filenames never become paths.
- Writes go to a temporary file first and are moved into place atomically.
- Originals are made read-only after writing and are never modified.
- Every path is resolved and checked to stay inside the data directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from app.core.errors import AppError
from app.core.paths import is_inside

CHUNK = 1024 * 1024
ORIGINALS = "documents/originals"
EXTRACTED = "documents/extracted"
SNAPSHOTS = "source_snapshots"


@dataclass(frozen=True)
class StoredFile:
    relative_path: str
    sha256: str
    size_bytes: int


class FileStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def resolve(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if not is_inside(path, self.root):
            raise AppError(500, "storage_error", "Stored file reference is invalid.")
        return path

    def save_original(self, file_id: str, extension: str, source: BinaryIO, max_bytes: int) -> StoredFile:
        relative = f"{ORIGINALS}/{file_id}{extension}"
        target = self.resolve(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=".upload-", suffix=".part")
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as out:
                while chunk := source.read(CHUNK):
                    size += len(chunk)
                    if size > max_bytes:
                        raise AppError(413, "file_too_large", "The file is larger than the upload limit.",
                                       {"max_bytes": max_bytes})
                    digest.update(chunk)
                    out.write(chunk)
            if size == 0:
                raise AppError(422, "empty_file", "The file is empty.")
            os.replace(tmp, target)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        make_read_only(target)
        return StoredFile(relative, digest.hexdigest(), size)

    def write_extracted_text(self, file_id: str, text: str) -> str:
        relative = f"{EXTRACTED}/{file_id}.txt"
        target = self.resolve(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            make_writable(target)
        fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=".extract-", suffix=".part")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
                out.write(text)
            os.replace(tmp_name, target)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
        return relative

    def write_snapshot(self, snapshot_id: str, payload: dict) -> StoredFile:
        """Write an immutable JSON snapshot of captured source data."""
        relative = f"{SNAPSHOTS}/{snapshot_id}.json"
        target = self.resolve(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str).encode("utf-8")
        fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=".snapshot-", suffix=".part")
        try:
            with os.fdopen(fd, "wb") as out:
                out.write(data)
            os.replace(tmp_name, target)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
        make_read_only(target)
        return StoredFile(relative, hashlib.sha256(data).hexdigest(), len(data))

    def read_text(self, relative_path: str) -> str:
        return self.resolve(relative_path).read_text(encoding="utf-8")

    def delete(self, relative_path: str | None) -> None:
        if not relative_path:
            return
        path = self.resolve(relative_path)
        if path.exists():
            make_writable(path)
            path.unlink()


def make_read_only(path: Path) -> None:
    path.chmod(stat.S_IREAD)


def make_writable(path: Path) -> None:
    path.chmod(stat.S_IREAD | stat.S_IWRITE)
