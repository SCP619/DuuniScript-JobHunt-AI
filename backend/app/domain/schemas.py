"""Pydantic request/response schemas for the public API contract."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.persistence.models import (
    ApplicationOutcome,
    ApplicationStatus,
    Availability,
    NotificationKind,
    DocumentCategory,
    DraftKind,
    DraftSource,
    DraftStatus,
    EmploymentType,
    EvidenceSourceType,
    ExtractionStatus,
    FactCategory,
    JobStatus,
    ListingStatus,
    SourceAccessType,
    SubmissionMethod,
    VerificationStatus,
    WorkMode,
)

T = TypeVar("T")

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


# ---------- Health ----------


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: Literal["ok", "unavailable"]


# ---------- Profile ----------


class ProfileUpsert(StrictModel):
    display_name: ShortText
    email: EmailStr | None = None
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=50, pattern=r"^[0-9+()\-\s]*$")] | None = None
    location: ShortText | None = None
    professional_summary: Annotated[str, StringConstraints(strip_whitespace=True, max_length=5_000)] | None = None


class ProfileRead(ReadModel):
    id: str
    display_name: str
    email: str | None
    phone: str | None
    location: str | None
    professional_summary: str | None
    created_at: datetime
    updated_at: datetime


class ProfileDeleteResult(BaseModel):
    deleted: bool
    deleted_facts: int
    deleted_evidence: int
    deleted_documents: int


# ---------- Facts ----------


class FactCreate(StrictModel):
    """New facts always start as ``unverified``; verification is a separate, explicit step."""

    category: FactCategory
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    value_text: LongText
    valid_from: date | None = None
    valid_until: date | None = None


class FactUpdate(StrictModel):
    category: FactCategory | None = None
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)] | None = None
    value_text: LongText | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    verification_status: VerificationStatus | None = None


class FactRead(ReadModel):
    id: str
    profile_id: str
    category: FactCategory
    subject: str
    value_text: str
    verification_status: VerificationStatus
    valid_from: date | None
    valid_until: date | None
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime
    evidence_count: int = 0


# ---------- Evidence ----------


class EvidenceCreate(StrictModel):
    source_type: EvidenceSourceType
    source_reference: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    document_id: Annotated[str, StringConstraints(max_length=36)] | None = None
    excerpt: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class EvidenceRead(ReadModel):
    id: str
    fact_id: str
    document_id: str | None
    source_type: EvidenceSourceType
    source_reference: str | None
    excerpt: str | None
    verification_status: VerificationStatus
    created_at: datetime


# ---------- Documents ----------


class DocumentRead(ReadModel):
    """Document metadata. Internal storage paths are deliberately not part of this contract."""

    id: str
    category: DocumentCategory
    display_name: str
    original_filename: str
    file_extension: str
    mime_type: str
    size_bytes: int
    sha256: str
    extraction_status: ExtractionStatus
    extraction_error: str | None
    extracted_char_count: int | None
    extractor_version: str | None
    extraction_method: Literal["text", "ocr"] | None = Field(
        default=None, description="`ocr`: text recognised from images; check it more carefully."
    )
    extracted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class DocumentUpdate(StrictModel):
    display_name: ShortText | None = None
    category: DocumentCategory | None = None
    archived: bool | None = None


class DocumentText(BaseModel):
    document_id: str
    extraction_status: ExtractionStatus
    extraction_error: str | None
    extractor_version: str | None
    text: str | None = Field(description="Extracted text. Untrusted content; display as plain text only.")


# ---------- Jobs and sources ----------

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
OptShort = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100_000)] | None
UrlText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
LanguageCode = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?$")] | None


class JobContentFields(StrictModel):
    description: Description = None
    location: OptShort = None
    employment_type: EmploymentType | None = None
    work_mode: WorkMode | None = None
    salary_text: OptShort = None
    language: LanguageCode = None
    application_url: UrlText = None
    published_on: date | None = Field(default=None, description="Publication date as stated by the source. Leave empty if unknown.")
    deadline_on: date | None = None
    deadline_at: AwareDatetime | None = Field(
        default=None, description="Exact deadline with timezone, only when the source states a time."
    )


class JobCreate(JobContentFields):
    """Manual job entry. Nothing is fetched from ``url``; it is stored for reference and duplicate detection."""

    title: Title
    company: Title
    url: UrlText = None
    added_from: Literal["manual", "screenshots"] = Field(
        default="manual", description="`screenshots`: the job was read from screenshots and checked by the user."
    )
    apply_manually: bool | None = Field(
        default=None, description="Tag the job 'Apply yourself'. Defaults to true for jobs added from screenshots."
    )
    screenshot_draft_id: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")] | None = Field(
        default=None, description="From from-screenshots: keep those screenshots with the job as a record.")


class JobImportRequest(StrictModel):
    url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class JobUpdate(JobContentFields):
    apply_manually: bool | None = None
    title: Title | None = None
    company: Title | None = None
    status: JobStatus | None = None
    hidden: bool | None = None
    user_notes: Annotated[str, StringConstraints(max_length=20_000)] | None = None
    possible_duplicate_of: None = Field(
        default=None, description="Send null to confirm this job is not a duplicate (clears the flag)."
    )


class JobMergeRequest(StrictModel):
    into_job_id: Annotated[str, StringConstraints(min_length=36, max_length=36, pattern=r"^[0-9a-fA-F-]{36}$")] = Field(
        description="The job to keep. The merged job's listings, missing details and notes move to it."
    )


class JobListingRead(BaseModel):
    source_key: str
    source_name: str
    source_url: str | None
    external_id: str | None
    source_published_on: date | None
    first_seen_at: datetime
    last_seen_at: datetime
    listing_status: ListingStatus
    captured_at: datetime | None
    parser_version: str | None


class JobSummary(ReadModel):
    id: str
    title: str
    company: str
    location: str | None
    employment_type: EmploymentType | None
    work_mode: WorkMode | None
    language: str | None = Field(
        description="Posting language as stated by the page or clearly detected from its text (e.g. en, fi). Null if not known."
    )
    available_from_finland: Availability = Field(
        description=(
            "Can someone living in Finland do this job? `yes`: located in Finland, or a remote job "
            "open to Finland (worldwide, Europe/EU/EMEA, Nordics, or a time zone including Finland). "
            "`no`: located elsewhere, or remote only for other countries. `unknown`: not stated clearly."
        )
    )
    published_on: date | None = Field(description="Null means the source did not state it.")
    deadline_on: date | None
    first_seen_at: datetime
    status: JobStatus
    hidden: bool
    canonical_url: str | None
    sources: list[str] = Field(default_factory=list, description="Source keys this job was seen on.")
    possible_duplicate_of: str | None = Field(
        default=None,
        description=(
            "ID of a job already in the list that this one looks like (same company and title, but "
            "date, location or description differ). The user decides: merge, or clear the flag."
        ),
    )
    match_score: int | None = Field(
        default=None,
        description="0-100: how well the job fits your verified facts. Null until some facts are verified.",
    )
    match_has_blockers: bool = Field(
        default=False, description="Something likely rules the job out (see GET /api/v1/jobs/{id}/match)."
    )
    apply_manually: bool = Field(
        default=False, description="Tag 'Apply yourself': the user applies on the site themselves."
    )
    archived: bool = Field(default=False, description="Archived automatically as old and untouched.")


class JobRead(JobSummary):
    description: str | None = Field(description="Untrusted text from the job posting. Display as plain text only.")
    salary_text: str | None
    application_url: str | None
    deadline_at: datetime | None
    last_seen_at: datetime
    user_notes: str | None
    created_at: datetime
    updated_at: datetime
    listings: list[JobListingRead] = Field(default_factory=list)


class SourceRead(ReadModel):
    id: str
    key: str
    name: str
    domain: str | None
    access_type: SourceAccessType
    access_method: str
    terms_url: str | None
    policy_notes: str | None
    enabled: bool
    last_success_at: datetime | None
    last_error_at: datetime | None
    last_error: str | None


# ---------- Errors (documented for OpenAPI) ----------


class ErrorDetail(BaseModel):
    code: str = Field(examples=["profile_not_found"])
    message: str
    details: dict = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ---------- Job alert emails ----------


class AlertSyncResult(BaseModel):
    emails_checked: int = Field(0, description="Emails looked at in this run.")
    emails_already_read: int = 0
    emails_not_alerts: int = Field(0, description="From senders that are not supported job sites.")
    emails_unverified: int = Field(0, description="Claimed to be from a job site but failed the sender check.")
    emails_without_jobs: int = 0
    jobs_found: int = 0
    jobs_created: int = 0
    jobs_merged: int = Field(0, description="Matched a job already in the list and added to it.")
    jobs_already_known: int = 0
    possible_duplicates: int = Field(0, description="New jobs flagged as looking like one already in the list.")
    unreadable_cards: int = Field(0, description="Job cards without a readable title or company.")


class AlertSiteRead(BaseModel):
    key: str
    name: str
    format_verified: bool = Field(description="True when this site's alert format was checked against real emails.")
    emails_read: int
    last_email_at: datetime | None


class JobAlertStatus(BaseModel):
    configured: bool = Field(description="A mailbox address is set and its password is saved on this computer.")
    mailbox: str | None
    folder: str
    sync_interval_minutes: int = Field(description="0 means automatic checks are off.")
    last_sync_at: datetime | None
    last_error_at: datetime | None
    last_error: str | None
    emails_read: int
    jobs_created: int
    jobs_merged: int
    sites: list[AlertSiteRead]


# ---------- Job feeds ----------


class FeedSyncResult(BaseModel):
    key: str
    name: str
    jobs_found: int = Field(0, description="Jobs in the feed this time.")
    jobs_created: int = 0
    jobs_merged: int = Field(0, description="Matched a job already in the list and added to it.")
    jobs_already_known: int = 0
    possible_duplicates: int = Field(0, description="New jobs flagged as looking like one already in the list.")
    skipped_not_available: int = Field(0, description="Remote jobs limited to other countries; not added.")
    skipped_keywords: int = Field(0, description="Jobs without any of the FEED_KEYWORDS words; not added.")
    error: str | None = Field(default=None, description="Readable reason when this feed could not be read.")


class FeedRead(BaseModel):
    key: str
    name: str
    domain: str
    enabled: bool
    access_method: str
    terms_url: str
    attribution: str = Field(description="Show this near the feed's jobs: the site is credited as the source.")
    min_interval_hours: float = Field(description="The site asks not to be read more often than this.")
    last_success_at: datetime | None
    last_error_at: datetime | None
    last_error: str | None
    next_allowed_at: datetime | None = Field(description="Null: can be checked now.")
    jobs: int = Field(description="Jobs in the list that were seen on this feed.")


class FeedsStatus(BaseModel):
    check_interval_minutes: int = Field(description="How often due feeds are checked automatically; 0 = off.")
    skip_unavailable: bool = Field(description="Remote jobs limited to other countries are not added.")
    keywords: list[str] = Field(description="When not empty, only feed jobs mentioning one of these are added.")
    feeds: list[FeedRead]


class SourceUpdate(StrictModel):
    enabled: bool


# ---------- Fact suggestions from documents ----------


class FactSuggestion(BaseModel):
    category: FactCategory
    subject: str
    value_text: str
    valid_from: date | None
    valid_until: date | None
    excerpt: str = Field(description="The CV text the suggestion was read from. Untrusted; display as plain text.")
    already_in_profile: bool = Field(description="A fact with the same category, subject and text already exists.")


class FactSuggestionList(BaseModel):
    document_id: str
    parser_version: str
    items: list[FactSuggestion]


class FactImportItem(FactCreate):
    excerpt: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class FactImportRequest(StrictModel):
    document_id: Annotated[str, StringConstraints(min_length=36, max_length=36, pattern=r"^[0-9a-fA-F-]{36}$")]
    items: Annotated[list[FactImportItem], Field(min_length=1, max_length=200)]


class FactImportResult(BaseModel):
    created: int
    skipped_existing: int = Field(description="Items identical to a fact already in the profile; not added again.")
    facts: list[FactRead]


class FactVerifyRequest(StrictModel):
    fact_ids: Annotated[
        list[Annotated[str, StringConstraints(min_length=36, max_length=36, pattern=r"^[0-9a-fA-F-]{36}$")]],
        Field(min_length=1, max_length=200),
    ]


class FactVerifyResult(BaseModel):
    verified: int
    facts: list[FactRead]


# ---------- Applications ----------

TemplateKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Id36 = Annotated[str, StringConstraints(min_length=36, max_length=36, pattern=r"^[0-9a-fA-F-]{36}$")]


class TemplateRead(BaseModel):
    key: str
    kind: DraftKind
    name: str
    description: str


class ApplicationCreate(StrictModel):
    job_id: Id36
    cv_source: DraftSource = Field(
        default=DraftSource.GENERATED,
        description="`generated`: build a CV from verified facts with `cv_template`. `uploaded`: send one of your uploaded documents unchanged.",
    )
    cv_template: TemplateKey | None = Field(
        default=None, description="Empty: the CV profile's template, else UTU Rekry (Finnish version for postings in Finnish).")
    cv_profile_id: Id36 | None = Field(default=None, description="CV profile to use; empty with auto_profile picks the best one.")
    auto_profile: bool = True
    cv_document_id: Id36 | None = Field(default=None, description="Required when `cv_source` is `uploaded`.")
    include_cover_letter: bool = True
    letter_template: TemplateKey | None = Field(
        default=None, description="Empty: UTU Rekry, in Finnish when the posting is in Finnish.")


class ApplicationUpdate(StrictModel):
    include_cover_letter: bool | None = None
    notes: Annotated[str, StringConstraints(max_length=20_000)] | None = None


class DraftIssue(BaseModel):
    severity: Literal["error", "warning", "info"] = Field(
        description="`error` blocks approval; `warning` must be acknowledged when approving; `info` is advice."
    )
    code: str
    message: str
    excerpt: str | None = None


class DraftRead(BaseModel):
    id: str
    kind: DraftKind
    version: int
    source: DraftSource
    template: str | None
    document_id: str | None = Field(description="The uploaded document sent unchanged (when `source` is `uploaded`).")
    document_name: str | None = None
    content: str | None = Field(
        description="Markdown of a generated draft (supports #, ##, ###, *dates*, - bullets). Private; plain text only."
    )
    evidence_fact_ids: list[str] = Field(description="Verified facts the generated text was built from.")
    status: DraftStatus
    content_sha256: str
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    issues: list[DraftIssue] = Field(default_factory=list)


class DraftUpdate(StrictModel):
    """Edit the current version, or switch between a generated and an uploaded CV.

    Editing an approved version creates a new draft version; approved versions never change.
    """

    source: DraftSource = DraftSource.GENERATED
    content: Annotated[str, StringConstraints(max_length=100_000)] | None = None
    document_id: Id36 | None = None


class DraftRegenerate(StrictModel):
    template: TemplateKey | None = Field(default=None, description="Template key; keeps the current one when empty.")


class DraftApprove(StrictModel):
    acknowledge_warnings: bool = Field(
        default=False, description="Must be true when the draft has warnings (claims no verified fact supports)."
    )


class JobBrief(BaseModel):
    id: str
    title: str
    company: str
    location: str | None
    deadline_on: date | None
    status: JobStatus


class ApplicationSummary(BaseModel):
    id: str
    job: JobBrief
    status: ApplicationStatus
    include_cover_letter: bool
    submission_method: SubmissionMethod | None
    ready_at: datetime | None
    submitted_at: datetime | None
    withdrawn_at: datetime | None
    outcome: ApplicationOutcome | None = Field(default=None, description="What happened after sending (user-recorded).")
    cv_profile_id: str | None = Field(default=None, description="CV profile used for this application's CV.")
    outcome_on: date | None = None
    created_at: datetime
    updated_at: datetime


class OutcomeUpdate(StrictModel):
    outcome: ApplicationOutcome | None = Field(description="Null clears it.")
    outcome_on: date | None = Field(default=None, description="When it happened; defaults to today.")


class ApplicationRead(ApplicationSummary):
    destination: str | None = Field(
        description="Where to apply: the posting's application link, else the posting itself. Open it in the browser; DuuniScript never submits."
    )
    contact_emails: list[str] = Field(
        description="Email addresses written in the posting itself (never guessed). Empty if none."
    )
    package_hash: str | None = Field(description="Set when status is `ready`: SHA-256 of the approved documents.")
    confirmation_reference: str | None
    notes: str | None
    cv: DraftRead | None
    cover_letter: DraftRead | None


class PackageFile(BaseModel):
    kind: DraftKind
    version: int
    filename: str
    sha256: str


class PackageRead(BaseModel):
    application_id: str
    ready: bool
    package_hash: str | None
    employer: str
    role: str
    destination: str | None
    contact_emails: list[str]
    files: list[PackageFile]
    cover_letter_text: str | None = Field(description="Approved cover letter as plain text, to paste into a form.")


class SubmissionRecord(StrictModel):
    """The user's own confirmation that they sent the application. DuuniScript never submits by itself."""

    confirm: Literal[True]
    package_hash: Annotated[str, StringConstraints(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")] = Field(
        description="The `package_hash` the user reviewed; a changed package is refused."
    )
    method: SubmissionMethod
    destination: UrlText = None
    confirmation_reference: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None


class ApplicationEventRead(ReadModel):
    id: str
    event_type: str
    package_hash: str | None
    details: dict | None
    occurred_at: datetime


# ---------- Job match ----------


class MatchBlocker(BaseModel):
    code: Literal["not_open_to_finland", "deadline_passed", "language_required"]
    message: str


class MatchParts(BaseModel):
    skills: int = Field(0, description="Out of 60.")
    role: int = Field(0, description="Out of 25.")
    wording: int = Field(0, description="Out of 15.")
    feedback: int = Field(0, description="-10 to +10 from your decisions on similar jobs (from 3 decisions on).")
    semantic: int | None = Field(None, description="0-20: closeness in meaning to your verified facts (local embeddings).")
    learned: int = Field(0, description="-10 to +10 from the reward model trained on your decisions (from 6 decisions on).")


class JobMatchRead(BaseModel):
    job_id: str
    score: int | None = Field(description="0-100; null until some facts are verified.")
    scoring_version: str
    reasons: list[str] = Field(description="Readable reasons, most important first.")
    matched_skills: list[str]
    missing_terms: list[str] = Field(description="Technical terms the posting names that no verified fact covers.")
    blockers: list[MatchBlocker]
    parts: MatchParts
    computed_at: datetime


# ---------- Dashboard and backups ----------


class DashboardCounts(BaseModel):
    jobs: int = Field(description="Jobs in the list (not hidden).")
    jobs_new_this_week: int
    jobs_saved: int
    jobs_good_match: int = Field(description="Open jobs scoring 60 or more without blockers.")
    applications_drafting: int
    applications_ready: int = Field(description="Approved, waiting for you to send.")
    applications_sent: int
    interviews: int = 0
    offers: int = Field(0, description="Offers received (including accepted).")


class DashboardJob(BaseModel):
    id: str
    title: str
    company: str
    location: str | None
    deadline_on: date | None
    status: JobStatus
    match_score: int | None


class DashboardStatus(BaseModel):
    last_source_check_at: datetime | None = Field(description="Last successful feed or mailbox check.")
    sources_turned_off: list[str]
    sources_failing: list[str] = Field(description="Feeds or the mailbox whose last check failed.")
    last_backup_at: datetime | None
    automatic_backups: bool


class DashboardSummary(BaseModel):
    counts: DashboardCounts
    deadlines_soon: list[DashboardJob] = Field(description="Open jobs whose deadline is within 7 days, soonest first.")
    best_matches: list[DashboardJob] = Field(description="Top 5 open jobs by match score, without blockers.")
    status: DashboardStatus


class BackupRead(BaseModel):
    name: str
    size_bytes: int
    created_at: datetime


class BackupsStatus(BaseModel):
    interval_hours: int = Field(description="Automatic backup every N hours while the app runs; 0 = off.")
    keep: int = Field(description="Newest backups kept; older ones are removed.")
    backups: list[BackupRead]


# ---------- Notifications ----------


class NotificationRead(ReadModel):
    id: str
    kind: NotificationKind
    entity_type: Literal["job", "application"]
    entity_id: str
    title: str = Field(description="Names the job or employer; plain text.")
    message: str
    link: str = Field(description="App route to open, e.g. /jobs/{id}.")
    created_at: datetime
    read_at: datetime | None
    dismissed_at: datetime | None


class NotificationList(BaseModel):
    unread: int
    items: list[NotificationRead]


# ---------- Sign-in ----------


class AuthStatus(BaseModel):
    password_set: bool = Field(description="False: DuuniScript is open (no sign-in yet); offer to create a passphrase.")
    signed_in: bool


class PasswordSet(StrictModel):
    password: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class PasswordChange(StrictModel):
    current_password: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    new_password: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class AuthToken(BaseModel):
    token: str = Field(description="Send as `Authorization: Bearer <token>` on every API request. Keep it in memory or sessionStorage.")
    expires_at: datetime


# ---------- Connected accounts ----------


class ProviderStatus(BaseModel):
    configured: bool = Field(description="The app credentials for this provider are set up on this computer.")
    connected: bool
    account: str | None = Field(description="The mailbox address that is connected.")
    connected_at: datetime | None
    last_sync_at: datetime | None
    last_error: str | None


class DeviceSignInRead(BaseModel):
    status: Literal["idle", "waiting", "connected", "failed"]
    user_code: str | None = Field(description="Type this code at verification_uri.")
    verification_uri: str | None
    expires_at: datetime | None
    message: str | None


class IntegrationsStatus(BaseModel):
    google: ProviderStatus
    microsoft: ProviderStatus
    microsoft_sign_in: DeviceSignInRead


class ConnectUrl(BaseModel):
    url: str = Field(description="Open in a new browser tab; the user signs in on Google's page.")


class GmailDraftResult(BaseModel):
    draft_id: str
    open_url: str


class EmailSend(StrictModel):
    """The user's explicit approval to send this application email from their Gmail."""

    confirm: Literal[True]
    package_hash: Annotated[str, StringConstraints(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]
    to: EmailStr


# ---------- Optional local AI ----------


class AiStatus(BaseModel):
    enabled: bool = Field(description="OLLAMA_MODEL is set.")
    model: str | None
    reachable: bool = Field(description="Ollama runs on this computer and has the model.")
    message: str | None
    embedding_model: str | None = Field(default=None, description="Model used for RAG search (OLLAMA_EMBED_MODEL).")
    embeddings_reachable: bool = False
    facts_indexed: int = Field(0, description="Verified facts in the search index.")
    jobs_indexed: int = 0


class AiIndexResult(BaseModel):
    available: bool
    facts: int = Field(description="Facts (re)indexed now.")
    jobs: int = Field(description="Jobs (re)indexed now.")


class PolishResult(BaseModel):
    suggestion: str = Field(description="Reworded draft (Markdown). Not saved; plain text only.")
    issues: list[DraftIssue] = Field(description="Claim check of the suggestion, like for any edit.")


# ---------- Jobs from screenshots ----------


class ScreenshotDraftRead(BaseModel):
    fields: dict = Field(description="Values for the Add job form (JobCreate keys). Not saved: the user checks and saves.")
    text: str = Field(description="All text read from the screenshots. Untrusted; plain text only.")
    method: Literal["ai", "text_only"] = Field(description="`ai`: fields filled by the local model; `text_only`: OCR text only.")
    warnings: list[str] = Field(description="Values to check, e.g. not found word for word in the screenshots.")
    images: int
    screenshot_draft_id: str | None = Field(default=None, description="Send back when saving to keep the screenshots.")


class PastedPosting(StrictModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100_000)]


# ---------- Form answers, CV profiles, statistics, attachments ----------


class FormAnswerRead(BaseModel):
    key: str
    question: str
    answer: str = Field(description="Ready to copy; empty when needs_input.")
    source: Literal["facts", "profile", "saved", "job", "none"]
    needs_input: bool
    hint: str | None
    fact_ids: list[str]


class SavedAnswerWrite(StrictModel):
    answer: Annotated[str, StringConstraints(max_length=5000)] | None = Field(description="Empty or null deletes it.")


class CvProfileWrite(StrictModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    focus: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)] = Field(
        description="Comma-separated focus words, e.g. 'SQL, Power BI, analytics'.")
    summary: Annotated[str, StringConstraints(strip_whitespace=True, max_length=3000)] | None = Field(
        default=None, description="Your own profile text for this CV version (replaces the summary).")
    cv_template: TemplateKey | None = None


class CvProfileRead(ReadModel):
    id: str
    name: str
    focus: str
    summary: str | None
    cv_template: str | None
    created_at: datetime
    updated_at: datetime


class AiFitResult(BaseModel):
    suggestion: str = Field(description="The cover letter with AI-written fit paragraphs. Not saved.")
    issues: list[DraftIssue]
    fact_ids: list[str] = Field(description="Verified facts given to the model.")


class SourceStats(BaseModel):
    key: str
    sent: int
    responses: int
    interviews: int
    offers: int
    response_rate: float | None


class OutcomeStats(BaseModel):
    sent: int
    responses: int = Field(description="Applications with any recorded outcome other than no_response.")
    interviews: int
    offers: int
    response_rate: float | None
    interview_rate: float | None
    median_days_to_reply: float | None
    by_source: list[SourceStats]
    by_role: list[SourceStats] = Field(description="Grouped by the main word of the job title (e.g. analyst).")
    sent_per_week: list[dict] = Field(description="[{week: 'YYYY-Www', sent: n}] for the last 12 weeks.")


class HousekeepingResult(BaseModel):
    expired: int = Field(description="Open jobs whose deadline passed, marked expired.")
    archived: int = Field(description="Old jobs never acted on, archived.")
    merged: int = Field(0, description="Reposts (same company, title and place) merged into one job.")


class JobAttachmentRead(ReadModel):
    id: str
    position: int
    media_type: str
    sha256: str
    size_bytes: int
    created_at: datetime
