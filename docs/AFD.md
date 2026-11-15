# DuuniScript — Application Functional Design (AFD)

**Version:** 1.0  
**Status:** Development baseline

## 1. Purpose

This document defines how users interact with DuuniScript and how its functional modules work together.

The frontend owns presentation. Backend services expose stable API contracts and do not own visual design decisions.

## 2. Application navigation

1. Dashboard
2. Jobs
3. Applications
4. Pending approvals
5. Profile
6. Documents
7. Integrations
8. Sources and scanning
9. Settings

## 3. Dashboard

Show total jobs discovered, new jobs, high-match jobs, drafts, pending approvals, submitted applications, interviews and outcomes.

The recent jobs table should include company, title, location, publication date, first-seen date, deadline, source, match score and status. Default sort is newest discovered first.

Show recent scans, new and updated jobs, drafts, approvals, submissions and integration errors. Link activity to its record.

## 4. Jobs

Support search and filters for company, location, source, publication date, deadline, match score, employment type, work mode, status and saved/hidden state.

Job detail includes employer, title, description, responsibilities, requirements, location, employment type, salary if published, dates, source URL, last checked time, match score and explanation.

Actions: save, hide, mark irrelevant, change status, generate draft, open original posting, inspect duplicate sources and add notes.

Suggested states: `new`, `reviewed`, `saved`, `not_relevant`, `drafting`, `applied`, `closed`, `expired`. Application status and source availability are separate.

## 5. Profile and evidence

Profile sections: personal/contact details, summary, education, work experience, skills, projects, certifications, languages, publications, references, preferences and writing style.

Each extracted fact must show its value, source, verification status, creation date, last verification date and optional confidence. Statuses: `unverified`, `verified`, `rejected`, `expired`.

Only verified facts support generated claims by default. Show incomplete profile sections honestly.

## 6. Documents

Categories include CV, cover letter, certificate, transcript, portfolio, publication, reference and other.

Support upload, preview, text extraction, fact review, verification, rename, categorize, archive, download and version history. Never modify original uploads.

For each generated version record version, date, related job/application, approval state, evidence used, format and content hash. Submitted versions are immutable.

## 7. Matching

Match factors include required/preferred skills, experience, education, language, location, employment type, seniority, eligibility requirements supplied by the user and preferences.

Show score, strong matches, partial matches, missing requirements, blockers and explanation. A score is not a probability of interview or offer.

User feedback may adjust ranking, but must not silently alter verified profile facts.

## 8. Application builder

On request, load the job, verified profile facts and approved style samples; extract requirements; create an application plan; generate drafts; validate claims; and create a pending review record.

Draft types: tailored CV, cover letter, motivation statement, form answers, recruiter email and supplementary documents.

Every personal claim must map to verified evidence or explicit user confirmation. Flag unsupported claims rather than inventing details.

Detect required documents. If one is missing, request it. Never fabricate certificates, transcripts or references.

## 9. Pending approvals

Show employer/job, deadline, destination, drafts, attachments, warnings, unresolved fields and submission method.

Allow editing, regeneration, approval, rejection and saving for later. Document approval and final submission approval are distinct.

Before submission, show destination, recipient, exact documents, form answers and external data to be transmitted. Require explicit confirmation.

## 10. Submission and history

Submission methods: manual, assisted browser form filling, or official supported API.

States: `draft`, `validation_required`, `pending_review`, `approved`, `ready_to_submit`, `submitting`, `submitted`, `submission_failed`, `unknown`, `withdrawn`.

If a network/browser failure occurs after possible acceptance, mark outcome `unknown`; do not retry automatically.

Record job, destination, method, approval, timestamp, confirmation evidence, document versions and submitted field values where appropriate.

History must show the exact submitted package. Historical content can guide style but cannot prove personal facts.

## 11. Recruiter email

Draft only when the address is explicitly published for recruitment or supplied and verified by the user. Show recipient, subject, body and attachments. Validate claims. Require approval before sending. Avoid unsolicited bulk email.

## 12. Integrations

Show service, connection state, permissions, last sync, errors and disconnect action.

Gmail sending and reading are separate permissions; request minimum scopes. LinkedIn access must use supported mechanisms or user-provided data. GitHub/portfolio data requires explicit user selection and verification. Do not assume access to university systems.

## 13. Sources and scanning

Show source, access type, enabled state, last/next scan, last error and jobs found. Allow run, pause, resume, scan-log viewing and source opening.

Record retrieved, new, updated, duplicate, rejected and failed counts.

## 14. Notifications and settings

In-app notifications: new high-match job, approaching deadline, missing document, pending approval, failed scan, expired integration and application outcome.

Settings include location, languages, employment type, role preferences, excluded employers, scan interval, AI provider/model, data directory, backup, integrations and privacy controls.

## 15. Error states and accessibility

Every page handles loading, empty, recoverable error, permission error, unsupported source, stale data, invalid data, offline model and external-service failure.

Use keyboard-accessible controls, labels, accessible dialogs, visible focus, responsive layouts and status text not based on color alone.

## 16. Acceptance tests

1. Create profile.
2. Import CV.
3. Extract facts as unverified.
4. Verify selected facts.
5. Import a job.
6. Parse and normalize it.
7. Calculate explainable match.
8. Generate draft.
9. Flag unsupported claims.
10. Correct and approve documents.
11. Review package.
12. Confirm submission or manual completion.
13. Record application.
14. Inspect exact historical package.

## 17. Ownership

The frontend (`frontend/`) owns pages, components, navigation, visual styling, tables, forms and responsive behavior.

The backend (`backend/`) owns API contracts, validation, persistence, business rules, integrations, background processing and tests.

Business rules live only in the backend; the frontend shows what the API returns.
