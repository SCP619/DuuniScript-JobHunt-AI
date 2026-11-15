# DuuniScript — Background & Source Strategy Document (BSD)

**Version:** 1.0  
**Initial region:** Turku and Finland  
**Principle:** Source access must be permitted, traceable, reliable and replaceable.

## 1. Purpose

Define background services, job-source strategy, retrieval policy, scheduling and external-data boundaries. A broad source list is a research target, not a promise that every site permits automated retrieval.

## 2. Source categories

Evaluate Finnish public job boards and services such as Työmarkkinatori, Jobly, Duunitori, Kuntarekry, Valtiolle.fi, Work in Finland, Academic Positions and EURAXESS.

Also evaluate University of Turku, Åbo Akademi, Turku UAS, other Finnish universities, research institutes, employer career pages and relevant professional networks.

LinkedIn and other login-based platforms require particular care. Prefer supported access or user-provided exports/data. Manual URL import and user-provided job content must remain available.

## 3. Access classification

Each source must be classified as:
- Official API.
- Official feed.
- Public structured data with permitted retrieval.
- Public page with uncertain policy.
- Supported authenticated access.
- User-provided data.
- Restricted/prohibited.

Do not assume a public page permits scraping. Personal use does not automatically override website terms.

## 4. Source evaluation checklist

Record official API/feed, permitted access method, authentication, rate limits, terms URL, data storage restrictions, copyright/retention, logo rules, attribution, available fields, deletion behavior, date reliability and review date.

Do not activate a source until its access method and policy notes are documented.

## 5. Candidate priorities

First evaluate official public employment sources, university/research career pages and employer pages with documented feeds or permitted access.

Then evaluate broader job boards.

Treat LinkedIn and uncertain authenticated platforms as manual-only unless an expressly supported mechanism is confirmed.

## 6. Background services

### Scheduler
Start scheduled scans, honor source-specific intervals, prevent overlap, record status, retry transient errors with bounds, permit manual scans and isolate failing sources.

### Retrieval
Fetch permitted content, handle timeouts, respect rate limits, preserve provenance and avoid redundant downloads.

### Parsing
Extract structured fields, normalize dates/locations, identify language, requirements and application method, and preserve uncertainty.

### Deduplication
Find duplicates while preserving all source references. Do not merge uncertain matches without review.

### Matching
Compare requirements with verified profile facts and preferences. Store explainable, versioned scores.

### Notifications
Create local alerts for new relevant jobs, deadlines, approvals and failures without duplicate notifications.

### Document/application services
Extract evidence, generate versioned drafts, validate claims, enforce approval states and record outcomes.

## 7. Hourly scan target

Pipeline:
1. Check source schedule.
2. Create scan record.
3. Retrieve permitted data.
4. Parse and validate.
5. Normalize.
6. Deduplicate.
7. Persist jobs and source references.
8. Recalculate matches.
9. Create notifications.
10. Store scan metrics.

Hourly is a target, not a universal interval. Source policies and rate limits take priority. Use timeouts, bounded retries, backoff, jitter, conditional requests where supported and one active scan per source.

## 8. Dates and freshness

Keep separate `published_at`, `source_updated_at`, `first_seen_at`, `last_seen_at` and snapshot capture time. If publication date is absent, store unknown. Never substitute first-seen time for publication date.

## 9. Parsing and provenance

Extract employer, title, location, work mode, employment type, description, responsibilities, required/preferred skills, education/language/experience requirements, salary, publication date, deadline, application URL, recruitment contact and required documents.

For each extracted field retain source excerpt/reference, confidence where useful and parser version. Unknown is better than guessed.

## 10. Logos and assets

Use only permitted source-provided assets, user-supplied images or official assets whose use is permitted. Store provenance and attribution notes. A missing logo must not prevent a listing from being displayed.

## 11. Adapter design

Each source adapter handles retrieval, parsing, validation, normalization and health reporting. It must not generate applications, send email, change the profile or submit applications.

Keep adapters isolated from core business logic.

## 12. Prompt injection and untrusted content

Job descriptions, employer pages, email and attachments are untrusted data. Never execute or follow instructions embedded in them. They cannot override system instructions, trigger tools, access secrets, send messages or disclose profile data.

Use structured extraction, schema validation and separation between external text and verified profile evidence.

## 13. Submission strategy

Level 1: manual submission with checklist and approved documents.

Level 2: assisted form filling that stops for user review and confirmation.

Level 3: official supported API, if available.

Stop at CAPTCHA, MFA, access restrictions, unexpected form changes or ambiguous submission results. Do not bypass technical controls or retry uncertain submissions automatically.

## 14. Recruiter email

Use only recruitment addresses explicitly published or supplied and verified by the user. Draft accurate messages and require approval before sending. Avoid bulk outreach.

## 15. Integration roadmap

Initial: local profile/documents, manual job URL import, a few evaluated public sources and local inference.

Intermediate: additional permitted sources, approved Gmail sending, local notifications and selected assisted browser workflows.

Later: additional official integrations and more advanced monitoring.

## 16. Laptop-only and optional second machine

The laptop can host frontend, backend, SQLite, private files, scheduler and local inference. The desktop is optional, not required.

If desktop inference is added later, use a trusted private network, authentication and firewall restrictions; do not expose public ports. Do not share a live SQLite database between machines.

## 17. Operational monitoring

Record last/next scan, duration, retrieved/new/updated/duplicate/rejected counts, parsing failures, network errors, access denials and policy disablements. Pause repeatedly failing sources and notify the user.

## 18. Compliance and completion

Respect source terms, privacy obligations, copyright and retention limits. Do not circumvent CAPTCHA, MFA, rate limits or access controls.

A source is ready only when its access method is documented, adapter fixture tests pass, source provenance is preserved, failures are isolated, dates remain accurate and manual import remains available.
