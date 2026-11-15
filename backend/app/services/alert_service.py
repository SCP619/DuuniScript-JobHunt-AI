"""Job alert emails -> jobs (AFD 4: email-based job alerts).

Each email is read once (``alert_email`` remembers its Message-ID). For every job card:

1. the same site posting seen before -> only "last seen" is updated;
2. the same posting address as a job in the list -> added to that job as another listing;
3. the same company and title, nothing contradicting it (job_matching) -> added likewise;
4. otherwise a new job, flagged ``possible_duplicate_of`` when it resembles one in the list.

So one posting seen on LinkedIn, Glassdoor and by URL import is one job with three listings,
and it can only be applied to once. The mailbox is only ever read; nothing is sent.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.job_sources.email_alerts import (
    PARSER_VERSION,
    SITES,
    AlertJob,
    AlertSite,
    message_key,
    parse_alert_email,
)
from app.adapters.mailbox import AlertMailbox, ImapMailbox, MailboxError, get_password
from app.core.config import Settings
from app.core.errors import AppError
from app.domain import schemas
from app.persistence.models import AlertEmail, JobSource, utcnow
from app.services import audit
from app.services.job_service import get_source
from app.services.listing_intake import add_posting
from app.services.storage import FileStore

logger = logging.getLogger("duuniscript.alerts")

MAILBOX_SOURCE = "email_alerts"
SYSTEM_ACTOR = "system"
MAILBOX_FAILURE_MESSAGES = {
    "consent_required": (
        "Your organisation requires an administrator to approve DuuniScript before it can read this "
        "mailbox. Ask its IT service, or download the alert emails as .eml files and upload them."
    ),
    "not_configured": "Job alert emails are not set up yet. Add the mailbox address and save its app password.",
    "auth_failed": (
        "The mailbox refused the sign-in. For Gmail connected in Settings: disconnect and connect it again. "
        "For IMAP: check the address and save a new app password."
    ),
    "rate_limited": "The mailbox asked DuuniScript to slow down. The rest is read at the next check.",
    "folder_missing": "The mailbox label for job alerts was not found. Check the label name in settings.",
    "connection_failed": "The mailbox could not be reached. Check your internet connection.",
    "timeout": "The mailbox took too long to respond.",
    "search_failed": "The mailbox could not list the job alert emails.",
}
# One sync at a time, whether started by the user or by the timer.
SYNC_LOCK = threading.Lock()


def make_mailbox(settings: Settings) -> AlertMailbox | None:
    if not settings.mail_imap_user:
        return None
    password = get_password(settings.mail_imap_user)
    if not password:
        return None
    return ImapMailbox(
        host=settings.mail_imap_host,
        port=settings.mail_imap_port,
        user=settings.mail_imap_user,
        password=password,
        folder=settings.mail_folder,
        timeout=settings.mail_timeout_seconds,
    )


# ---------- One email ----------


def ingest_email(
    session: Session, store: FileStore, raw: bytes, report: schemas.AlertSyncResult, actor: str = "user"
) -> None:
    report.emails_checked += 1
    key = message_key(raw)
    if session.scalar(select(AlertEmail.id).where(AlertEmail.message_key == key)):
        report.emails_already_read += 1
        return
    parsed = parse_alert_email(raw)
    record = AlertEmail(
        message_key=key,
        source_key=parsed.site.key if parsed.site else None,
        result=parsed.result,
        received_at=parsed.received_at,
        jobs_found=len(parsed.jobs),
        jobs_created=0,
        jobs_merged=0,
        jobs_known=0,
        unreadable_cards=parsed.unreadable_cards,
    )
    report.unreadable_cards += parsed.unreadable_cards
    if parsed.result == "unknown_sender":
        report.emails_not_alerts += 1
    elif parsed.result == "unverified_sender":
        report.emails_unverified += 1
    elif not parsed.jobs:
        report.emails_without_jobs += 1

    snapshots: list[str] = []
    try:
        if parsed.jobs and parsed.site is not None:
            source = get_source(session, parsed.site.key)
            received = parsed.received_at or datetime.now(timezone.utc)
            for card in parsed.jobs:
                outcome = _add_card(session, store, source, parsed.site, card, received, snapshots)
                column = {"created": "jobs_created", "possible": "jobs_created", "merged": "jobs_merged"}.get(
                    outcome, "jobs_known"
                )
                setattr(record, column, getattr(record, column) + 1)
                report.jobs_found += 1
                if outcome in ("created", "possible"):
                    report.jobs_created += 1
                    report.possible_duplicates += outcome == "possible"
                elif outcome == "merged":
                    report.jobs_merged += 1
                else:
                    report.jobs_already_known += 1
            source.last_success_at = utcnow()
        session.add(record)
        audit.record(
            session,
            "alert_email.processed",
            "alert_email",
            record.id,
            {
                "site": record.source_key,
                "result": record.result,
                "jobs_found": record.jobs_found,
                "jobs_created": record.jobs_created,
                "jobs_merged": record.jobs_merged,
            },
            actor=actor,
        )
        session.commit()
    except BaseException:
        session.rollback()
        for path in snapshots:
            store.delete(path)
        raise


def _add_card(
    session: Session,
    store: FileStore,
    source: JobSource,
    site: AlertSite,
    card: AlertJob,
    received: datetime,
    snapshots: list[str],
) -> str:
    """Returns known, merged, created or possible (created and flagged)."""
    outcome, _ = add_posting(
        session,
        store,
        source,
        external_id=card.external_id,
        link=card.link,
        canonical_url=card.canonical_url,
        values={
            "title": card.title,
            "company": card.company,
            "location": card.location,
            "published_on": card.posted_on,
        },
        seen_on=received.date(),
        snapshot={
            "source": site.key,
            "parser_version": PARSER_VERSION,
            "email_received_at": received.isoformat(),
            "card": {
                "title": card.title,
                "company": card.company,
                "location": card.location,
                "link": card.link,
                "stated_age": card.age_text,
            },
        },
        parser_version=PARSER_VERSION,
        snapshots=snapshots,
    )
    return outcome


# ---------- Mailbox ----------


def sync_mailbox(
    session: Session, store: FileStore, mailbox: AlertMailbox | None, settings: Settings, actor: str = "user",
    source_key: str = MAILBOX_SOURCE,
) -> schemas.AlertSyncResult:
    source = get_source(session, source_key)
    if mailbox is None:
        _record_mailbox_failure(session, source, "not_configured", actor)
        raise AppError(409, "mailbox_not_configured", MAILBOX_FAILURE_MESSAGES["not_configured"])
    if not SYNC_LOCK.acquire(blocking=False):
        raise AppError(409, "sync_in_progress", "Job alert emails are already being checked.")
    try:
        today = datetime.now(timezone.utc).date()
        if source.last_success_at:
            since = source.last_success_at.date() - timedelta(days=2)
        else:
            since = today - timedelta(days=settings.mail_backfill_days)
        report = schemas.AlertSyncResult()

        def already_read(message_id: str) -> bool:
            return session.scalar(select(AlertEmail.id).where(AlertEmail.message_key == message_id)) is not None

        try:
            for raw in mailbox.fetch_since(since, already_read):
                ingest_email(session, store, raw, report, actor)
        except MailboxError as exc:
            _record_mailbox_failure(session, source, exc.reason, actor)
            message = MAILBOX_FAILURE_MESSAGES.get(exc.reason, "The mailbox check failed.")
            raise AppError(502, "mailbox_error", message, {"reason": exc.reason}) from exc
        source.last_success_at = utcnow()
        source.last_error = None
        source.last_error_at = None
        audit.record(session, "alert_mailbox.synced", "job_source", source.id, report.model_dump(), actor=actor)
        session.commit()
        return report
    finally:
        SYNC_LOCK.release()


def _record_mailbox_failure(session: Session, source: JobSource, reason: str, actor: str) -> None:
    source.last_error_at = utcnow()
    source.last_error = MAILBOX_FAILURE_MESSAGES.get(reason, "The mailbox check failed.")
    audit.record(
        session, "alert_mailbox.sync_failed", "job_source", source.id, {"reason": reason}, actor=actor,
        result="failure",
    )
    session.commit()


def status(session: Session, settings: Settings, configured: bool) -> schemas.JobAlertStatus:
    source = get_source(session, MAILBOX_SOURCE)
    rows = session.execute(
        select(
            AlertEmail.source_key,
            func.count(AlertEmail.id),
            func.max(AlertEmail.received_at),
            func.sum(AlertEmail.jobs_created),
            func.sum(AlertEmail.jobs_merged),
        ).group_by(AlertEmail.source_key)
    ).all()
    by_site = {row[0]: row for row in rows}
    return schemas.JobAlertStatus(
        configured=configured,
        mailbox=settings.mail_imap_user,
        folder=settings.mail_folder,
        sync_interval_minutes=settings.mail_sync_interval_minutes,
        last_sync_at=source.last_success_at,
        last_error_at=source.last_error_at,
        last_error=source.last_error,
        emails_read=sum(row[1] for row in rows),
        jobs_created=sum(row[3] or 0 for row in rows),
        jobs_merged=sum(row[4] or 0 for row in rows),
        sites=[
            schemas.AlertSiteRead(
                key=site.key,
                name=site.name,
                format_verified=site.verified,
                emails_read=by_site[site.key][1] if site.key in by_site else 0,
                last_email_at=by_site[site.key][2] if site.key in by_site else None,
            )
            for site in SITES
        ],
    )


# ---------- Timer ----------


class AlertSyncTimer:
    """Runs a check every ``interval`` minutes while the app runs (mailbox, job feeds)."""

    def __init__(
        self,
        run_once: Callable[[], None],
        interval_minutes: int,
        first_delay_seconds: float = 60,
        name: str = "alert-sync",
    ) -> None:
        self._run_once = run_once
        self._interval = interval_minutes * 60
        self._first_delay = first_delay_seconds
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name=name, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def _loop(self) -> None:
        delay = self._first_delay
        while not self._stop.wait(delay):
            try:
                self._run_once()
            except AppError as exc:
                logger.info("Job alert check skipped: %s", exc.code)
            except Exception:  # noqa: BLE001 - the timer must keep running
                logger.exception("Job alert check failed")
            delay = self._interval
