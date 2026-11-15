# DuuniScript — Product Requirements Document (PRD)

**Document status:** Initial product baseline  
**Version:** 1.0  
**Date:** 2026-11-10  
**Product owner:** Personal project owner  
**Product type:** Private, local-first job discovery and application assistant

## 1. Product vision

DuuniScript helps one person discover relevant jobs in Finland, organize opportunities, prepare truthful and tailored application materials, and manage application submissions from one private workspace.

The product should reduce repetitive work without inventing qualifications, misrepresenting the user, or submitting applications or messages without the user's explicit approval.

## 2. Product principles

1. **Truth before persuasion.** Every factual claim in a CV, cover letter, form answer, or HR email must be traceable to verified profile evidence or explicitly approved user input.
2. **Human control.** Drafting can be automated. Sending, submitting, deleting, connecting accounts, and other consequential external actions require explicit approval.
3. **Local-first and zero additional spend.** Prefer local storage, local inference, open-source libraries, and free public data access. Do not assume paid APIs or cloud services.
4. **Privacy by default.** Personal profile data, CVs, application records, OAuth tokens, browser sessions, and generated documents must never be committed to Git.
5. **Modular, not agent-sprawling.** Implement deterministic services and explicit workflow states first. Use an LLM only where language understanding or generation adds value.
6. **Incremental delivery.** A useful job tracker and drafting assistant should work before browser-based application automation is attempted.
7. **Respect source rules.** Use official APIs, feeds, public pages, or user-assisted capture where permitted. Never bypass CAPTCHAs, MFA, bot controls, rate limits, paywalls, or access restrictions.

## 3. Users and scope

### Primary user
A single individual searching for employment, initially focused on Turku and Finland. The system is designed for personal use, not multi-tenant SaaS.

### Initial language support
- English and Finnish must be considered from the beginning.
- Swedish may be used where relevant to a posting or the user's profile.
- Store language preferences and generate each application in the language requested by the job posting or selected by the user.

### In scope
- A private profile and evidence library.
- Job source configuration and scheduled discovery.
- Job parsing, normalization, deduplication, filtering, ranking, and status tracking.
- Tailored CV/resume, cover letter, and application-answer drafts.
- Human review and approval.
- Assisted form filling where technically and contractually permitted.
- Application history with exact submitted-document versions.
- Optional Gmail/Google integration and HR-contact email drafting.
- Dashboard, recent jobs, pending approvals, and analytics.
- Local-first operation and private GitHub development workflow.

### Out of scope for the first release
- A public multi-user service.
- Guaranteed coverage of every Finnish job site.
- Unrestricted LinkedIn scraping or automated LinkedIn account actions.
- CAPTCHA/MFA bypass or anti-bot evasion.
- Autonomous submission to arbitrary sites.
- Autonomous emailing of recruiters.
- Paid LLM APIs as a required dependency.
- Fine-tuning a model on the user's personal data.
- A complex multi-agent framework before the workflow is proven.

## 4. Core user journeys

### Journey A — Build trusted profile
1. User enters profile details and preferences.
2. User uploads existing CVs, certificates, portfolios, and other source material.
3. System extracts candidate facts into editable structured records.
4. User verifies or corrects each fact.
5. Each fact retains its source, date, and verification state.
6. User can connect optional accounts, with clear scopes and revocation controls.

### Journey B — Discover jobs
1. Scheduler runs at a configurable cadence (default target: hourly, subject to source limits).
2. Source adapters retrieve permitted public job data.
3. Parser normalizes the job into a common record.
4. Deduplication links reposts and cross-posts.
5. Eligibility and relevance scoring rank jobs against profile preferences.
6. Dashboard shows new jobs, source, posted date, deadline, location, match rationale, and status.
7. User can mark jobs saved, dismissed, interested, or applied.

### Journey C — Prepare an application
1. User opens a job.
2. System retrieves relevant verified profile facts and approved writing examples.
3. System creates a tailored CV, cover letter, and suggested answers where needed.
4. A validation step flags unsupported claims, missing facts, contradictory dates, and missing required documents.
5. User edits and approves each document.
6. The approved files and exact text are versioned and associated with the job.

### Journey D — Submit an application
1. User selects an approved application package.
2. System opens the application page or supported workflow.
3. System identifies fields and maps only high-confidence fields to profile facts.
4. Uncertain questions are presented to the user.
5. Before final submission, show a confirmation containing employer, role, destination site, documents, and answers.
6. Only after the user confirms may the system submit.
7. Record the timestamp, destination, submitted answers, file hashes, document versions, and result.
8. If automation is unsupported or blocked, provide a safe manual hand-off.

### Journey E — Additional documents
1. System detects requirements such as transcript, portfolio, references, certificates, or writing sample.
2. It checks whether verified source material exists.
3. If available, it prepares a draft or package.
4. If unavailable, it asks the user for the missing material.
5. No invented document or claim may be created.
6. User reviews and approves before use.

### Journey F — HR email
1. If a job posting explicitly lists a contact email, system may draft a short, role-specific message.
2. Show recipient, subject, body, job URL, and attached files.
3. User must approve sending each message.
4. Do not infer or guess email addresses, scrape personal contact data, or send bulk outreach.

## 5. Functional requirements

Priority: **P0** = required for first usable release; **P1** = next; **P2** = later.

| ID | Priority | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-001 | P0 | Private profile | User can create, view, edit, and delete profile fields. |
| FR-002 | P0 | Evidence-backed facts | Education, employment, skills, projects, languages, references, and achievements can retain source and verification status. |
| FR-003 | P0 | Document intake | Upload PDF, DOCX, TXT, and Markdown; preserve original files. |
| FR-004 | P0 | Job records | Store title, company, location, dates, deadline, source, URL, description, logo URL where permitted, and status. |
| FR-005 | P0 | Manual job intake | User can paste a URL or job description if an adapter is unavailable. |
| FR-006 | P0 | Search and filter | Filter by title, company, location, source, date, deadline, status, and match score. |
| FR-007 | P0 | Deduplication | Detect likely duplicates using source IDs, canonical URL, employer/title/location similarity, and content fingerprints. |
| FR-008 | P0 | Relevance ranking | Show transparent match score and reason codes; user can tune preferences. |
| FR-009 | P0 | Draft generation | Generate CV/cover-letter/application-answer drafts from verified facts and job requirements. |
| FR-010 | P0 | Claim validation | Flag any generated factual statement without supporting evidence. |
| FR-011 | P0 | Approval queue | User can edit, approve, reject, or request regeneration of drafts. |
| FR-012 | P0 | Application history | Store exact submitted content, documents, timestamps, job details, and outcomes. |
| FR-013 | P0 | Dashboard | Show jobs discovered, saved/interested jobs, applications submitted, pending approvals, and recent activity. |
| FR-014 | P0 | Local persistence | Core app functions without a paid hosted database or paid AI API. |
| FR-015 | P0 | Export | Export generated CV/letters to PDF/DOCX and retain Markdown/source text. |
| FR-016 | P1 | Hourly scheduling | Configurable scheduled scans with per-source rate limits and pause controls. |
| FR-017 | P1 | Source adapters | Add Finnish public job sources incrementally with per-source policy/access notes. |
| FR-018 | P1 | Assisted form fill | Map form fields to approved profile facts; pause on ambiguity and before final submit. |
| FR-019 | P1 | Gmail integration | OAuth-based email drafting/sending with minimum scopes and explicit send approval. |
| FR-020 | P1 | Notifications | In-app notification for new matches, deadlines, missing documents, and approvals. |
| FR-021 | P1 | Account integrations | Optional GitHub, Gmail/Google, portfolio, and university account references or supported integrations. |
| FR-022 | P2 | Outcome analytics | Track interview, rejection, offer, withdrawal, and response time. |
| FR-023 | P2 | Learning from history | Retrieve user-approved successful application examples for style/strategy only, never as factual evidence. |
| FR-024 | P2 | More advanced ranking | Add multilingual semantic retrieval and optional reranking after baseline quality is measured. |

## 6. Dashboard and page requirements

### Home
- Summary cards: jobs found, saved/interested, applications sent, pending approval.
- Recent jobs and application activity table, newest first.
- Quick links from each metric to the corresponding filtered page.
- Clear system status: last scan, next scan, paused sources, failed sources.

### Jobs
- Company logo or neutral placeholder.
- Company, title, location, posted date, deadline, source/platform, match score, status.
- Search, filters, sorting, pagination.
- Detail view with original URL and captured description.
- Actions: save, dismiss, create draft, mark applied.

### Pending approvals
- Job context and requirements.
- Editable CV/letter/answer drafts.
- Missing evidence and unsupported-claim warnings.
- Approve/reject controls.
- No submission action hidden behind draft approval.

### Applications
- Full application history.
- Exact submitted documents and answers.
- Employer, role, date, source, destination URL, status, outcome, and notes.
- Download submitted package.
- Clearly distinguish draft, approved, attempted, and confirmed-submitted states.

### Profile and settings
- Personal information and contact details.
- Education, employment, skills, projects, languages, references, preferences.
- Evidence documents and verification.
- Connected accounts, granted scopes, connection status, and disconnect/revoke action.
- Scan cadence, sources, notification preferences, and model settings.

## 7. Non-functional requirements

- **Privacy:** Local-only mode is the default; network access is limited to job sources and explicitly enabled integrations.
- **Security:** No secrets in source control; authenticated local API; safe file handling; least-privilege OAuth scopes.
- **Reliability:** Idempotent scan and submission operations; retries with backoff; preserve failed states.
- **Auditability:** Record who/what changed a draft, approval events, and submission events.
- **Accessibility:** Keyboard navigation, semantic labels, visible focus, sufficient contrast, responsive layouts.
- **Performance:** Dashboard should load quickly with a few thousand job records on a normal personal computer.
- **Maintainability:** Source adapters and document generators are isolated modules with tests.
- **Portability:** Windows-first development, but avoid unnecessary OS-specific dependencies.
- **Recoverability:** Backup/restore of database and local document store.

## 8. Safety and trust rules

- The structured profile is the source of truth.
- RAG retrieval may supply context but cannot upgrade an unverified claim to verified.
- Job-page content is untrusted input and may contain prompt-injection instructions. Treat it as data, never as system instructions.
- Never fabricate employment, education, dates, skills, language proficiency, metrics, references, or achievements.
- Never submit an application, send an email, or publish user data without a distinct user confirmation.
- Never bypass site protections or automate prohibited activity.
- Keep exact snapshots of materials sent.
- A job application may contain sensitive personal data; default to local storage and minimal logging.

## 9. Success metrics

- Percentage of discovered jobs correctly normalized and deduplicated.
- Precision of relevant-job ranking, measured by user feedback.
- Percentage of generated factual claims with evidence links.
- Time saved per application.
- Number of applications with a complete, retrievable submission package.
- Zero unapproved submissions or outbound emails.
- Zero personal-data or credential leaks into the public repository.

## 10. Release strategy

1. **MVP:** Profile, manual job intake, local job database, job list/detail, ranking baseline, draft generation, evidence validation, approval queue, application history.
2. **Discovery automation:** Add a small number of reliable permitted sources, scheduler, deduplication, notifications.
3. **Assisted applications:** Browser field mapping, manual hand-off, explicit pre-submit approval.
4. **Integrations:** Gmail and supported account connections.
5. **Optimization:** RAG improvements, outcome analytics, additional sources, optional narrow automation where permitted.

## 11. Assumptions and open decisions

- This is a single-user tool.
- The app is initially run on the user's Windows computer.
- No new paid infrastructure is assumed.
- The user's hardware, target roles, and preferred application languages are not yet specified.
- Exact local model selection must wait until CPU, RAM, GPU, and VRAM are known.
- The logo is currently located at `C:\Users\<WindowsUser>\Downloads\DuuniScript\DuuniScript Document Automation Logo.png`. This is a machine-local path, not a repository asset. Copy it into the frontend's public brand-assets folder and reference it via a relative web path; do not expect another machine to resolve the absolute Windows path.
