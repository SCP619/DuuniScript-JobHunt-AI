"""Private data directory resolution.

Private data never lives inside the repository. The default location is
``%LOCALAPPDATA%\\DuuniScript`` on Windows, overridable with ``APP_DATA_DIR``.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "DuuniScript"

# Folder layout from DBD section 2.
DATA_SUBDIRS: tuple[str, ...] = (
    "database",
    "documents/originals",
    "documents/extracted",
    "documents/generated",
    "applications/drafts",
    "applications/submitted",
    "source_snapshots",
    "vector_store",
    "logs",
    "backups",
)


def default_data_dir() -> Path:
    """Return the platform default private data directory."""
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / APP_DIR_NAME
    # Non-Windows fallback (development portability only).
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / APP_DIR_NAME


def ensure_data_dirs(root: Path) -> None:
    """Create the private data directory tree if missing."""
    root.mkdir(parents=True, exist_ok=True)
    for sub in DATA_SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)


def is_inside(child: Path, parent: Path) -> bool:
    """True if ``child`` resolves to a location inside ``parent``."""
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True
