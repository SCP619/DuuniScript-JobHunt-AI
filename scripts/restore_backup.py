"""Restore a DuuniScript backup into a data folder.

Stop DuuniScript first. Usage (PowerShell, repository root):

    .venv\\Scripts\\python.exe scripts\\restore_backup.py <backup.zip> [--target <folder>] [--replace]

- Without ``--target`` the backup is restored into the normal data folder (``APP_DATA_DIR`` or
  ``%LOCALAPPDATA%\\DuuniScript``).
- The target must be empty or missing, unless ``--replace`` is given. With ``--replace`` the
  current database and documents are first moved aside to ``<target>\\replaced-<time>`` (nothing
  is deleted).
- Every file is checked against the backup's manifest before anything is written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

RESTORED = ("database", "documents/originals", "documents/extracted", "source_snapshots", "job_screenshots")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("backup", type=Path)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    if args.target is None:
        from app.core.config import get_settings

        target = get_settings().app_data_dir
    else:
        target = args.target
    target = target.resolve()

    with zipfile.ZipFile(args.backup) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        for name, digest in manifest["files"].items():
            parts = PurePosixPath(name).parts
            if name.startswith("/") or ".." in parts or not any(name.startswith(d + "/") for d in RESTORED):
                print(f"Refused: unexpected path in backup: {name}")
                return 1
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                print(f"Refused: {name} does not match the manifest; the backup is damaged.")
                return 1

        existing = [target / d for d in RESTORED if (target / d).exists() and any((target / d).iterdir())]
        if existing and not args.replace:
            print(f"{target} already has data. Use --replace to move it aside first, or choose an empty --target.")
            return 1
        if existing:
            aside = target / f"replaced-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            for path in existing:
                destination = aside / path.relative_to(target)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(destination))
            print(f"Moved the current data to {aside}")

        for name in manifest["files"]:
            out = target / Path(*PurePosixPath(name).parts)
            out.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as src, out.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    print(f"Restored {len(manifest['files'])} files from {args.backup.name} into {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
