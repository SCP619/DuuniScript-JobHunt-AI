"""SQLAlchemy ORM models (DBD sections 4-5 and 10).

Conventions: UUID string primary keys, UTC timestamps, controlled state values,
foreign keys enforced on every SQLite connection.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from enum import StrEnum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    MetaData,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator[datetime]):
    """Stores naive UTC in SQLite and always returns timezone-aware UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):  # noqa: ANN001
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetimes are not allowed; use UTC-aware datetimes.")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):  # noqa: ANN001
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"


class FactCategory(StrEnum):
    CONTACT = "contact"
    SUMMARY = "summary"
    EDUCATION = "education"
    WORK_EXPERIENCE = "work_experience"
    SKILL = "skill"
    PROJECT = "project"
    CERTIFICATION = "certification"
    LANGUAGE = "language"
    PUBLICATION = "publication"
    REFERENCE = "reference"
    ACHIEVEMENT = "achievement"
    PREFERENCE = "preference"
    OTHER = "other"


class EvidenceSourceType(StrEnum):
    DOCUMENT = "document"
    USER_INPUT = "user_input"
    URL = "url"
    INTEGRATION = "integration"


class DocumentCategory(StrEnum):
    CV = "cv"
    COVER_LETTER = "cover_letter"
    CERTIFICATE = "certificate"
    TRANSCRIPT = "transcript"
    PORTFOLIO = "portfolio"
    PUBLICATION = "publication"
    REFERENCE = "reference"
    OTHER = "other"


class ExtractionStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    NO_TEXT = "no_text"
    FAILED = "failed"


class JobStatus(StrEnum):
    """User workflow state of a job (AFD 4). Independent of source availability."""

    NEW = "new"
    REVIEWED = "reviewed"
    SAVED = "saved"
    NOT_RELEVANT = "not_relevant"
    DRAFTING = "drafting"
    APPLIED = "applied"
    CLOSED = "closed"
    EXPIRED = "expired"


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"
    VOLUNTEER = "volunteer"
    PER_DIEM = "per_diem"
    OTHER = "other"


class WorkMode(StrEnum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"


class Availability(StrEnum):
    """Can the job be done by someone living in Finland? (services/eligibility.py)"""

    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class SourceAccessType(StrEnum):
    """Access classification from BSD 3."""

    OFFICIAL_API = "official_api"
    OFFICIAL_FEED = "official_feed"
    PUBLIC_STRUCTURED_DATA = "public_structured_data"
    PUBLIC_PAGE_UNCERTAIN = "public_page_uncertain"
    SUPPORTED_AUTHENTICATED = "supported_authenticated"
    USER_PROVIDED = "user_provided"
    RESTRICTED = "restricted"


class AlertEmailResult(StrEnum):
    PARSED = "parsed"
    NO_JOBS = "no_jobs"
    UNKNOWN_SENDER = "unknown_sender"
    UNVERIFIED_SENDER = "unverified_sender"
    TOO_LARGE = "too_large"


class ListingStatus(StrEnum):
    ACTIVE = "active"
    REMOVED = "removed"
    UNKNOWN = "unknown"


def _values(enum: type[StrEnum]) -> str:
    return ", ".join(f"'{m.value}'" for m in enum)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: UTCDateTime}


class UserProfile(Base):
    __tablename__ = "user_profile"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    display_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(200))
    professional_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    facts: Mapped[list[ProfileFact]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", passive_deletes=True
    )
    documents: Mapped[list[Document]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", passive_deletes=True
    )


class Document(Base):
    """An uploaded source document. The original file is never modified (AFD 6, DBD 6)."""

    __tablename__ = "document"
    __table_args__ = (
        CheckConstraint(f"category IN ({_values(DocumentCategory)})", name="category"),
        CheckConstraint(f"extraction_status IN ({_values(ExtractionStatus)})", name="extraction_status"),
        UniqueConstraint("profile_id", "sha256", name="uq_document_profile_sha256"),
        Index("ix_document_category_archived", "category", "archived_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    profile_id: Mapped[str] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(30))
    display_name: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    # Relative to APP_DATA_DIR. Internal only; never returned by the API.
    storage_path: Mapped[str] = mapped_column(String(500))
    file_extension: Mapped[str] = mapped_column(String(10))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column()
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    extraction_status: Mapped[str] = mapped_column(String(20), default=ExtractionStatus.PENDING.value)
    extraction_error: Mapped[str | None] = mapped_column(String(50))
    extracted_text_path: Mapped[str | None] = mapped_column(String(500))
    extracted_char_count: Mapped[int | None] = mapped_column()
    extractor_version: Mapped[str | None] = mapped_column(String(20))
    # "text": read from the file itself; "ocr": recognised from images (check it more carefully).
    extraction_method: Mapped[str | None] = mapped_column(String(10))
    extracted_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    archived_at: Mapped[datetime | None] = mapped_column()

    profile: Mapped[UserProfile] = relationship(back_populates="documents")


class ProfileFact(Base):
    __tablename__ = "profile_fact"
    __table_args__ = (
        CheckConstraint(f"verification_status IN ({_values(VerificationStatus)})", name="verification_status"),
        CheckConstraint(f"category IN ({_values(FactCategory)})", name="category"),
        CheckConstraint(
            "valid_from IS NULL OR valid_until IS NULL OR valid_from <= valid_until", name="valid_range"
        ),
        Index("ix_profile_fact_category_status", "category", "verification_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    profile_id: Mapped[str] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(40))
    subject: Mapped[str] = mapped_column(String(300))
    value_text: Mapped[str] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(20), default=VerificationStatus.UNVERIFIED.value)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    verified_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    profile: Mapped[UserProfile] = relationship(back_populates="facts")
    evidence: Mapped[list[ProfileEvidence]] = relationship(
        back_populates="fact", cascade="all, delete-orphan", passive_deletes=True
    )


class ProfileEvidence(Base):
    __tablename__ = "profile_evidence"
    __table_args__ = (
        CheckConstraint(f"verification_status IN ({_values(VerificationStatus)})", name="verification_status"),
        CheckConstraint(f"source_type IN ({_values(EvidenceSourceType)})", name="source_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    fact_id: Mapped[str] = mapped_column(ForeignKey("profile_fact.id", ondelete="CASCADE"), index=True)
    # RESTRICT: a document that backs evidence cannot be deleted out from under it.
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("document.id", ondelete="RESTRICT"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(30))
    source_reference: Mapped[str | None] = mapped_column(String(2000))
    excerpt: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(20), default=VerificationStatus.UNVERIFIED.value)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    fact: Mapped[ProfileFact] = relationship(back_populates="evidence")


class AuditEvent(Base):
    """Append-only audit log. Details must be redacted (no personal values)."""

    __tablename__ = "audit_event"
    __table_args__ = (Index("ix_audit_event_entity_time", "entity_type", "entity_id", "occurred_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    result: Mapped[str] = mapped_column(String(20), default="success")
    details: Mapped[dict | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow)


# ---------- Jobs and sources (DBD 7) ----------


class JobSource(Base):
    """A place jobs come from. Built-in sources are seeded by migration and identified by ``key``."""

    __tablename__ = "job_source"
    __table_args__ = (
        CheckConstraint(f"access_type IN ({_values(SourceAccessType)})", name="access_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    domain: Mapped[str | None] = mapped_column(String(253))
    access_type: Mapped[str] = mapped_column(String(40))
    access_method: Mapped[str] = mapped_column(String(200))
    terms_url: Mapped[str | None] = mapped_column(String(2000))
    policy_notes: Mapped[str | None] = mapped_column(Text)
    rate_limit: Mapped[dict | None] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(default=True)
    last_success_at: Mapped[datetime | None] = mapped_column()
    last_error_at: Mapped[datetime | None] = mapped_column()
    last_error: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Job(Base):
    """A canonical job. Dates are never inferred: unknown stays NULL (BSD 8)."""

    __tablename__ = "job"
    __table_args__ = (
        CheckConstraint(f"status IN ({_values(JobStatus)})", name="status"),
        CheckConstraint(f"employment_type IS NULL OR employment_type IN ({_values(EmploymentType)})",
                        name="employment_type"),
        CheckConstraint(f"work_mode IS NULL OR work_mode IN ({_values(WorkMode)})", name="work_mode"),
        CheckConstraint(f"available_from_finland IN ({_values(Availability)})", name="available_from_finland"),
        Index("ix_job_status_hidden", "status", "hidden"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    canonical_url: Mapped[str | None] = mapped_column(String(2000), unique=True)
    company: Mapped[str] = mapped_column(String(300), index=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(300))
    employment_type: Mapped[str | None] = mapped_column(String(20))
    work_mode: Mapped[str | None] = mapped_column(String(10))
    salary_text: Mapped[str | None] = mapped_column(String(300))
    language: Mapped[str | None] = mapped_column(String(10))
    application_url: Mapped[str | None] = mapped_column(String(2000))
    # yes / no / unknown, from the stated location or the remote job's stated restrictions.
    available_from_finland: Mapped[str] = mapped_column(
        String(10), default=Availability.UNKNOWN.value, server_default=Availability.UNKNOWN.value, index=True
    )
    published_on: Mapped[date | None] = mapped_column(Date, index=True)
    deadline_on: Mapped[date | None] = mapped_column(Date, index=True)
    deadline_at: Mapped[datetime | None] = mapped_column()
    first_seen_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(default=utcnow)
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.NEW.value)
    hidden: Mapped[bool] = mapped_column(default=False)
    user_notes: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    # "Apply yourself": the user applies on the site themselves (e.g. jobs added from screenshots
    # of pages behind a login). Shown as a tag; DuuniScript still prepares the documents.
    apply_manually: Mapped[bool] = mapped_column(default=False, server_default="0")
    # Set when an old job was archived automatically (hidden from lists, kept for history).
    archived_at: Mapped[datetime | None] = mapped_column(index=True)
    # Set when this job looks like one already in the list but is not clearly the same posting.
    possible_duplicate_of_id: Mapped[str | None] = mapped_column(
        ForeignKey("job.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    listings: Mapped[list[JobSourceListing]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )


class JobSourceListing(Base):
    """Where a canonical job was seen. All listings are kept, even after merging duplicates."""

    __tablename__ = "job_source_listing"
    __table_args__ = (
        CheckConstraint(f"listing_status IN ({_values(ListingStatus)})", name="listing_status"),
        UniqueConstraint("source_id", "external_id", name="uq_job_source_listing_source_external"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("job.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("job_source.id", ondelete="RESTRICT"), index=True)
    external_id: Mapped[str | None] = mapped_column(String(300))
    source_url: Mapped[str | None] = mapped_column(String(2000))
    source_published_on: Mapped[date | None] = mapped_column(Date)
    source_updated_at: Mapped[datetime | None] = mapped_column()
    first_seen_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(default=utcnow)
    listing_status: Mapped[str] = mapped_column(String(20), default=ListingStatus.ACTIVE.value)
    # Relative to APP_DATA_DIR; internal only. Holds the structured data captured at import.
    snapshot_path: Mapped[str | None] = mapped_column(String(500))
    snapshot_hash: Mapped[str | None] = mapped_column(String(64))
    captured_at: Mapped[datetime | None] = mapped_column()
    parser_version: Mapped[str | None] = mapped_column(String(20))

    job: Mapped[Job] = relationship(back_populates="listings")
    source: Mapped[JobSource] = relationship()


class AlertEmail(Base):
    """A job alert email that has been read, so it is never processed twice.

    Holds counts and the sending site only; the email itself stays in the mailbox.
    """

    __tablename__ = "alert_email"
    __table_args__ = (
        CheckConstraint(f"result IN ({_values(AlertEmailResult)})", name="result"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    message_key: Mapped[str] = mapped_column(String(300), unique=True)
    source_key: Mapped[str | None] = mapped_column(String(50))
    result: Mapped[str] = mapped_column(String(20))
    received_at: Mapped[datetime | None] = mapped_column()
    processed_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    jobs_found: Mapped[int] = mapped_column(default=0)
    jobs_created: Mapped[int] = mapped_column(default=0)
    jobs_merged: Mapped[int] = mapped_column(default=0)
    jobs_known: Mapped[int] = mapped_column(default=0)
    unreadable_cards: Mapped[int] = mapped_column(default=0)


# ---------- Applications (DBD 9) ----------


class ApplicationStatus(StrEnum):
    DRAFT = "draft"  # documents being prepared
    READY = "ready"  # every included document approved; package can be sent by the user
    SUBMITTED = "submitted"  # the user confirmed they sent it; record is now read-only
    WITHDRAWN = "withdrawn"


class DraftKind(StrEnum):
    CV = "cv"
    COVER_LETTER = "cover_letter"


class DraftSource(StrEnum):
    GENERATED = "generated"  # built from verified facts with a template, editable
    UPLOADED = "uploaded"  # one of the user's uploaded documents, sent unchanged


class DraftStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"


class SubmissionMethod(StrEnum):
    WEB_FORM = "web_form"
    EMAIL = "email"
    OTHER = "other"


class ApplicationOutcome(StrEnum):
    """What happened after the user sent the application (FR-022)."""

    NO_RESPONSE = "no_response"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    OFFER = "offer"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class Application(Base):
    """One application to one job. Nothing is ever sent by DuuniScript itself (AFD, PRD Journey D)."""

    __tablename__ = "application"
    __table_args__ = (
        CheckConstraint(f"status IN ({_values(ApplicationStatus)})", name="status"),
        CheckConstraint(
            f"submission_method IS NULL OR submission_method IN ({_values(SubmissionMethod)})",
            name="submission_method",
        ),
        CheckConstraint(f"outcome IS NULL OR outcome IN ({_values(ApplicationOutcome)})", name="outcome"),
        Index("ix_application_status_submitted", "status", "submitted_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    profile_id: Mapped[str] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"), index=True)
    # RESTRICT: merging jobs moves applications first; a job with an application is never lost.
    job_id: Mapped[str] = mapped_column(ForeignKey("job.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(20), default=ApplicationStatus.DRAFT.value)
    include_cover_letter: Mapped[bool] = mapped_column(default=True)
    cv_profile_id: Mapped[str | None] = mapped_column(ForeignKey("cv_profile.id", ondelete="SET NULL"))
    submission_method: Mapped[str | None] = mapped_column(String(20))
    destination: Mapped[str | None] = mapped_column(String(2000))
    package_hash: Mapped[str | None] = mapped_column(String(64))
    confirmation_reference: Mapped[str | None] = mapped_column(String(300))
    outcome: Mapped[str | None] = mapped_column(String(20))
    outcome_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    ready_at: Mapped[datetime | None] = mapped_column()
    submitted_at: Mapped[datetime | None] = mapped_column()
    withdrawn_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    drafts: Mapped[list[ApplicationDraft]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ApplicationDraft.version",
    )


class ApplicationDraft(Base):
    """A CV or cover letter version for an application. Approved versions are never changed."""

    __tablename__ = "application_document"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_values(DraftKind)})", name="kind"),
        CheckConstraint(f"source IN ({_values(DraftSource)})", name="source"),
        CheckConstraint(f"status IN ({_values(DraftStatus)})", name="status"),
        CheckConstraint(
            "(source = 'uploaded' AND document_id IS NOT NULL) OR (source = 'generated' AND content IS NOT NULL)",
            name="content_present",
        ),
        UniqueConstraint("application_id", "kind", "version", name="uq_application_document_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(ForeignKey("application.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column()
    source: Mapped[str] = mapped_column(String(20))
    template: Mapped[str | None] = mapped_column(String(40))
    # RESTRICT: an uploaded CV used in an application cannot be deleted from under it.
    document_id: Mapped[str | None] = mapped_column(ForeignKey("document.id", ondelete="RESTRICT"), index=True)
    # Markdown text of a generated draft. Private: never logged or audited.
    content: Mapped[str | None] = mapped_column(Text)
    # IDs of the verified facts the generated text was built from (evidence manifest).
    evidence: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default=DraftStatus.DRAFT.value)
    content_sha256: Mapped[str] = mapped_column(String(64))
    approved_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    application: Mapped[Application] = relationship(back_populates="drafts")


class ApplicationEvent(Base):
    """Approvals and submission records. Details hold state values only, no personal content."""

    __tablename__ = "application_event"
    __table_args__ = (Index("ix_application_event_app_time", "application_id", "occurred_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(ForeignKey("application.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(40))
    package_hash: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow)


class JobMatch(Base):
    """How well a job fits the verified profile (FR-008). Recomputed when facts or the job change."""

    __tablename__ = "job_match"
    __table_args__ = (
        CheckConstraint("score IS NULL OR (score >= 0 AND score <= 100)", name="score_range"),
        Index("ix_job_match_score", "score"),
    )

    job_id: Mapped[str] = mapped_column(ForeignKey("job.id", ondelete="CASCADE"), primary_key=True)
    # NULL: not enough verified facts to judge.
    score: Mapped[int | None] = mapped_column()
    has_blockers: Mapped[bool] = mapped_column(default=False)
    scoring_version: Mapped[str] = mapped_column(String(20))
    profile_fingerprint: Mapped[str] = mapped_column(String(64))
    job_hash: Mapped[str] = mapped_column(String(80))
    # Readable explanation: matched skills, missing terms, blockers and reasons (no personal values).
    details: Mapped[dict] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(default=utcnow)


class NotificationKind(StrEnum):
    GOOD_MATCH = "good_match"
    DEADLINE_SOON = "deadline_soon"
    READY_NOT_SENT = "ready_not_sent"
    FOLLOW_UP = "follow_up"


class Notification(Base):
    """In-app notice (FR-020). One per kind and subject; text names the job, never personal data."""

    __tablename__ = "notification"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_values(NotificationKind)})", name="kind"),
        UniqueConstraint("kind", "entity_id", name="uq_notification_kind_entity"),
        Index("ix_notification_state", "dismissed_at", "read_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(30))
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[str] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(300))
    message: Mapped[str] = mapped_column(String(600))
    link: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column()
    dismissed_at: Mapped[datetime | None] = mapped_column()
    # When a Windows notification was shown for it (shown once).
    toasted_at: Mapped[datetime | None] = mapped_column()


# ---------- Sign-in to DuuniScript itself ----------


class AppCredential(Base):
    """The one sign-in passphrase for this DuuniScript, as a salted scrypt hash (never the text)."""

    __tablename__ = "app_credential"

    id: Mapped[int] = mapped_column(primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class AppSession(Base):
    """A signed-in browser. Only the SHA-256 of the session token is stored."""

    __tablename__ = "app_session"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_used_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(index=True)


class Integration(Base):
    """A connected account (Gmail, Microsoft/UTU mailbox). Tokens live in Windows Credential
    Manager, never here: this row holds only the provider, the account address and states."""

    __tablename__ = "integration"
    __table_args__ = (UniqueConstraint("provider", name="uq_integration_provider"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(30))  # "google" or "microsoft"
    account: Mapped[str | None] = mapped_column(String(320))
    scopes: Mapped[str] = mapped_column(String(1000))
    connected_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_sync_at: Mapped[datetime | None] = mapped_column()
    last_error_at: Mapped[datetime | None] = mapped_column()
    last_error: Mapped[str | None] = mapped_column(String(300))


class Embedding(Base):
    """A local embedding vector (RAG) for one verified fact or one job. float32, little-endian."""

    __tablename__ = "embedding"
    __table_args__ = (
        CheckConstraint("kind IN ('fact', 'job')", name="kind"),
        UniqueConstraint("kind", "ref_id", name="uq_embedding_kind_ref"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(10))
    ref_id: Mapped[str] = mapped_column(String(36), index=True)
    model: Mapped[str] = mapped_column(String(100))
    text_hash: Mapped[str] = mapped_column(String(64))
    dim: Mapped[int] = mapped_column()
    vector: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


# ---------- Form answers, CV profiles, job attachments ----------


class SavedAnswer(Base):
    """The user's own answer to a common application-form question (salary, availability…).

    Written by the user, so it counts as user-confirmed; reused for every application."""

    __tablename__ = "saved_answer"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    answer: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class CvProfile(Base):
    """A CV emphasis, e.g. "Data Analyst" or "AI/ML": focus words reorder verified facts; an
    optional profile text (written by the user) replaces the summary. Never adds claims."""

    __tablename__ = "cv_profile"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    focus: Mapped[str] = mapped_column(Text)  # comma-separated words and skills
    summary: Mapped[str | None] = mapped_column(Text)
    cv_template: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class JobAttachment(Base):
    """A screenshot kept with a job as a record of the posting (private, read-only)."""

    __tablename__ = "job_attachment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("job.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column()
    storage_path: Mapped[str] = mapped_column(String(500))
    media_type: Mapped[str] = mapped_column(String(50))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
