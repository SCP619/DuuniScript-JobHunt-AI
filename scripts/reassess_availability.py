"""Re-read "Can I work from Finland?" for jobs still marked unknown, after the location rules improved.

Only jobs whose value is ``unknown`` are changed (to ``yes`` or ``no`` when their stated location
now says so); jobs already ``yes`` or ``no`` are left alone. Match scores update by themselves.

Usage (PowerShell, repository root):  .venv\\Scripts\\python.exe scripts\\reassess_availability.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.persistence.db import make_session_factory, prepare_database  # noqa: E402
from app.persistence.models import Job  # noqa: E402
from app.services import audit, eligibility  # noqa: E402


def reassess(session, dry_run: bool = False) -> Counter:  # noqa: ANN001
    changes: Counter = Counter()
    for job in session.scalars(select(Job).where(Job.available_from_finland == eligibility.UNKNOWN)):
        value = eligibility.assess(job.location)
        if value != eligibility.UNKNOWN:
            changes[value] += 1
            if not dry_run:
                job.available_from_finland = value
    if not dry_run and changes:
        audit.record(session, "jobs.availability_reassessed", "job", None, dict(changes), actor="system")
        session.commit()
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    engine = prepare_database(settings)
    with make_session_factory(engine)() as session:
        changes = reassess(session, args.dry_run)
    engine.dispose()
    verb = "Would change" if args.dry_run else "Changed"
    print(f"{verb}: {changes.get('yes', 0)} to 'yes', {changes.get('no', 0)} to 'no'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
