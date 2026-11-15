# DuuniScript — Database Design Document (DBD)

**Version:** 1.0  
**Database:** SQLite initially  
**ORM:** SQLAlchemy  
**Migrations:** Alembic  
**Storage:** Relational metadata plus private filesystem; optional local vector index

## 1. Objectives

Store profile facts and evidence, normalized jobs and provenance, source scans, match results, document versions, application packages, approvals, external actions and audit records.

## 2. Storage boundaries

SQLite stores structured metadata and relationships. The filesystem stores originals, extracted text, generated documents, submitted packages, permitted source snapshots and backups. A vector index is derived data and must be rebuildable.

Default data directory: `%LOCALAPPDATA%\\DuuniScript`, overridable with `APP_DATA_DIR`.

Suggested folders: `database`, `documents/originals`, `documents/extracted`, `documents/generated`, `applications/drafts`, `applications/submitted`, `source_snapshots`, `vector_store`, `logs`, `backups`.

## 3. Core entities

`user_profile`, `profile_fact`, `profile_evidence`, `education`, `work_experience`, `skill`, `project`, `language_skill`, `certification`, `reference_contact`, `document`, `document_version`, `writing_sample`, `job_source`, `source_scan`, `job`, `job_source_listing`, `job_snapshot`, `job_requirement`, `job_match`, `job_feedback`, `application`, `application_document`, `application_answer`, `application_approval`, `submission_event`, `integration`, `audit_event`, `notification`.

## 4. Conventions

Use UUID string primary keys, UTC ISO 8601 timestamps, ISO dates, controlled state values, foreign keys and indexes. JSON is for source-specific/flexible metadata, not core relationships. Enable SQLite foreign keys on every connection. Archive or soft-delete important records.

## 5. Profile tables

### `user_profile`
`id`, `display_name`, protected `email`, protected optional `phone`, user-provided `location`, approved `professional_summary`, `created_at`, `updated_at`.

### `profile_fact`
`id`, `profile_id`, `category`, `subject`, `value_text`, `verification_status`, optional `valid_from`, `valid_until`, `verified_at`, `created_at`, `updated_at`.

Statuses: `unverified`, `verified`, `rejected`, `expired`.

### `profile_evidence`
`id`, `fact_id`, nullable `document_id`, `source_type`, `source_reference`, minimal `excerpt`, `verification_status`, `created_at`.

A fact may have multiple evidence records.

### Other profile records
- `education`: institution, degree, field, dates, description, status, evidence reference.
- `work_experience`: employer, title, location, dates, current flag, description, achievements, verification.
- `skill`: name, category, proficiency, years of experience, verification and evidence.
- `project`: name, description, role, technologies, URL, dates, verification and evidence.
- `language_skill`: language, proficiency scheme/level, certificate and verification.
- `certification`: name, issuer, issue/expiry dates, credential URL, document and verification.
- `reference_contact`: name, relationship, organization, contact details, permission status and notes. Treat as highly sensitive; never contact without approval.

## 6. Document records

### `document`
`id`, `profile_id`, category, original filename, private relative storage path, MIME type, SHA-256, extraction status, creation and archive timestamps.

### `document_version`
`id`, `document_id`, version number, storage path, content hash, format, optional job/application references, approval status, evidence manifest and creation timestamp.

Approved/submitted versions are immutable.

### `writing_sample`
`id`, `profile_id`, `document_id`, sample type, language, approved-for-style flag, notes and creation timestamp. Samples guide style, not factual claims.

## 7. Job-source records

### `job_source`
`id`, name, domain, source type, access method, terms URL, policy notes, rate-limit metadata, enabled flag, last success/error and timestamps.

### `source_scan`
`id`, `source_id`, start/end, status, retrieved/new/updated/duplicate/rejected/error counts, error summary and adapter version.

### `job`
`id`, canonical URL, company, optional logo URL, title, normalized description, location, employment type, work mode, optional salary range/currency, publication date, deadline, first/last seen, status, content hash and timestamps.

Unknown dates must remain unknown; never infer publication time from retrieval time.

### `job_source_listing`
Links canonical jobs to source listings: job/source IDs, external ID, source URL, source dates, first/last seen, listing status and raw reference. Use uniqueness on `(source_id, external_id)` where an external ID exists.

### `job_snapshot`
`id`, job/source-listing references, capture time, content hash, snapshot path and change summary.

### `job_requirement`
`id`, job ID, requirement type, description, mandatory flag, normalized skill, confidence and source excerpt.

## 8. Matching records

`job_match`: job/profile, score, scoring version, matched/missing requirements, blockers, explanation and timestamp.

`job_feedback`: job/profile, feedback, notes and timestamp. Feedback never changes verified facts.

## 9. Application records

### `application`
`id`, job/profile IDs, status, submission method, destination URL, created/approved/submitted timestamps, outcome and notes.

### `application_document`
Application ID, immutable document version ID, role, required flag, approved/submitted flags and submitted hash.

### `application_answer`
Application ID, field key, question, answer, evidence manifest, approval status and submitted flag.

### `application_approval`
Application ID, approval type, actor, decision, timestamp, package hash and notes. Distinguish document approval from final submission approval.

### `submission_event`
Application ID, event type, time, destination, method, result, confirmation reference, package hash and redacted details. Never record uncertain submission as success.

## 10. Integration, audit and notification

`integration`: provider, status, scopes, connection/sync/error timestamps and protected credential reference. Never store plaintext tokens in ordinary metadata.

`audit_event`: actor, action, entity type/ID, timestamp, result and redacted details. Audit fact verification, approvals, submissions, email sends, integration changes and data exports/deletions.

`notification`: type, title, message, entity reference, creation/read/dismissal timestamps. Avoid sensitive details in notification text.

## 11. Indexes and deduplication

Index job publication/first-seen/deadline/company/title/status, source, application status/submission date, scan time, fact category/verification, document hash and audit entity/time.

Deduplicate in stages: exact canonical URL, source external ID, normalized company/title/location, description/requirements similarity, then human review. Similar titles alone are insufficient. Preserve all source listings after merging.

## 12. Lifecycle and migrations

Archive jobs/documents where appropriate. Keep submitted application records immutable. Define deletion and backup retention. Profile deletion requires explicit confirmation and explanation of dependent records.

Use Alembic from the first schema version. Test migrations against a copy, back up before destructive changes and never make undocumented manual schema changes.

## 13. Backups and security

Back up the database, private documents, generated packages, metadata and hashes. Keep backups outside Git. Do not share a live SQLite database between computers.

Bind API to loopback by default. Validate paths and uploads, enable foreign keys, parameterize SQL, redact logs, protect credentials and keep embeddings local.

## 14. Initial implementation

Start with profile, fact/evidence, document/version, source/scan, job/source listing, match, application, application document, approval, submission event and audit tables. Add other tables as features are implemented.
