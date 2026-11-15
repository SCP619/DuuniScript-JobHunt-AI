# DuuniScript — Backend Setup (Windows 11)

Status: implemented so far are the health check, profile CRUD, profile facts, fact evidence,
document upload and text extraction, jobs (manual entry and URL import), and the audit log.
Nothing else is implemented yet.

## 1. Prerequisites

- Python 3.11 or newer.
- [uv](https://docs.astral.sh/uv/) (recommended) or the standard `venv` + `pip`.
- Git for Windows.

## 2. Install

From the repository root in PowerShell:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
```

Without uv:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

You do not need to activate the virtual environment; call `.venv\Scripts\python.exe` directly.
That avoids changing the PowerShell execution policy.

## 3. Configure (optional)

Copy `.env.example` to `.env` only if you need to change a default. `.env` is ignored by Git.

| Variable | Default | Notes |
|---|---|---|
| `APP_DATA_DIR` | `%LOCALAPPDATA%\DuuniScript` | Must be outside the repository; startup refuses a path inside it. |
| `API_HOST` | `127.0.0.1` | Keep loopback. The API has no authentication yet. |
| `API_PORT` | `8000` | |
| `CORS_ORIGINS` | `localhost`/`127.0.0.1` on ports 5173 and 8080 | Comma-separated. Add your frontend dev server origin if it differs. |
| `MAX_REQUEST_BYTES` | `1048576` | JSON body limit. |
| `MAX_UPLOAD_BYTES` | `20971520` | Document upload limit (20 MB). |
| `URL_IMPORT_ENABLED` | `true` | Set `false` to stop all job URL fetching. |
| `URL_IMPORT_TIMEOUT_SECONDS` | `15` | Per-request timeout for URL import (max 60). |

## 4. Run

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m app.main
```

On startup the app creates the private data folders and applies database migrations
automatically. Then open:

- Health: <http://127.0.0.1:8000/health>
- Interactive API docs: <http://127.0.0.1:8000/docs>

### Start and stop with one click

`scripts\start_duuniscript.ps1` starts the API (port 8000) and the frontend (port 8080, real
backend, no sample data) in two minimised windows and opens the app in the browser; things that
are already running are reused. `scripts\stop_duuniscript.ps1` stops only DuuniScript's own
processes on those ports. For double-clicking, put next to the repository and the `frontend`
folder a `Start DuuniScript.cmd` containing:

```bat
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0duuniscript\scripts\start_duuniscript.ps1"
if errorlevel 1 pause
```

## 5. Test

From the repository root:

```powershell
.venv\Scripts\python.exe -m pytest
```

Tests use a temporary data directory and synthetic data only. They never touch
`%LOCALAPPDATA%\DuuniScript`.

## 6. Database migrations

Migrations live in `backend/migrations`. They run automatically on startup. To create a new
migration after changing `backend/app/persistence/models.py`:

```powershell
Set-Location backend
$env:APP_DATA_DIR = "$env:TEMP\duuni_autogen"   # throwaway database, not your real one
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe change"
Remove-Item Env:APP_DATA_DIR
```

Review every generated migration by hand. `test_models_match_migrations` fails if models and
migrations drift apart. Back up the real database before applying a destructive migration.

## 7. API contract

The OpenAPI contract for the frontend is committed at `contracts/openapi.json`. Regenerate it after
any API change:

```powershell
.venv\Scripts\python.exe scripts\export_openapi.py
```

`test_committed_openapi_contract_is_current` fails if it is out of date.

Error responses always look like:

```json
{"error": {"code": "fact_not_found", "message": "Fact not found.", "details": {}}}
```

## 8. Implemented endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | Status, version, database check. |
| GET | `/api/v1/profile` | 404 `profile_not_found` before creation. |
| PUT | `/api/v1/profile` | Creates (201) or replaces (200) the single local profile. |
| DELETE | `/api/v1/profile?confirm=true` | Without `confirm=true`: 409 `confirmation_required` with dependent counts. |
| GET | `/api/v1/profile/facts` | Filters `category`, `verification_status`; `limit` 1-200, `offset`. |
| POST | `/api/v1/profile/facts` | Always created `unverified`. |
| GET/PATCH/DELETE | `/api/v1/profile/facts/{id}` | Editing a verified fact resets it to `unverified` unless the same request re-verifies it. |
| GET/POST | `/api/v1/profile/facts/{id}/evidence` | Adding evidence never verifies a fact. Document evidence must reference an existing, non-archived document. |
| POST | `/api/v1/profile/facts/import` | Saves chosen fact suggestions as `unverified` facts with the document as evidence; identical facts are skipped. |
| POST | `/api/v1/profile/facts/verify` | Verifies a list of facts (the user confirmed each). Unknown IDs: 404, nothing changes. |
| POST | `/api/v1/documents` | Multipart upload: `file`, `category`, optional `display_name`. PDF, DOCX, TXT, Markdown, HTML. |
| GET | `/api/v1/documents` | Filters `category`, `include_archived`; `limit`, `offset`. Newest first. |
| GET/PATCH | `/api/v1/documents/{id}` | PATCH: `display_name`, `category`, `archived`. |
| GET | `/api/v1/documents/{id}/content` | Downloads the unchanged original as an attachment. |
| GET | `/api/v1/documents/{id}/text` | Extracted text. Untrusted; display as plain text only. |
| POST | `/api/v1/documents/{id}/extract` | Re-runs extraction. The original is never changed. |
| GET | `/api/v1/dashboard` | Home summary: counts, deadlines within 7 days, top 5 matches, source and backup status. |
| GET | `/api/v1/jobs/{id}/match` | Match score explained (section 13). The job list has `sort=match` and `min_match`. |
| GET | `/api/v1/documents/{id}/fact-suggestions` | Profile facts read from the text by rules (section 12). Nothing is saved. 409 `no_extracted_text`. |
| DELETE | `/api/v1/documents/{id}?confirm=true` | Removes the record and files. Refused (409 `document_in_use`) while evidence or an application references it. |

### Document handling rules

- Accepted: PDF, DOCX, TXT, Markdown and HTML (`.html`/`.htm`, e.g. a saved web CV page).
  File type is checked by content, not by the browser's MIME type: PDFs must start with `%PDF-`,
  DOCX must be a valid Word archive within zip-bomb limits, text must be UTF-8 (or UTF-16
  with a byte-order mark), and HTML must start like a web page. HTML is only reduced to text
  (scripts and styles dropped) and never rendered; downloads are attachments with `nosniff`.
  PNG and JPEG images (e.g. a photographed certificate) are accepted and read with **OCR**
  (below); images are opened under a 60-million-pixel limit.
- **OCR** uses the text recognition built into Windows (`Windows.Media.Ocr`, through the `winrt`
  packages): local, free, no model download. It also reads scanned PDFs that have no text layer
  (the page images inside the PDF). `extraction_method` is `ocr` for such text: check it more
  carefully. It recognises the languages installed in Windows (Settings > Time & language >
  Language); add Finnish there for Finnish documents. Without the OCR engine, images get
  `failed` / `ocr_unavailable` and scanned PDFs stay `no_text`. Extractor version 3.
  Checked 2026-11-11: a synthetic certificate image was read exactly; the user's only image in
  the CV folder is a photo of a person, which correctly gives `no_text`.
- Originals are stored as `documents/originals/<id><ext>` under `APP_DATA_DIR`, marked
  read-only, and never modified. The user's filename is kept only as metadata.
- The same file (same SHA-256) cannot be uploaded twice; the 409 response names the existing
  document.
- Extraction is local (`pypdf`, `python-docx`). `extraction_status` is `succeeded`, `no_text`
  (for example a scanned PDF; OCR is not implemented), or `failed` with an `extraction_error`
  code (`encrypted`, `too_many_pages`, `parse_error`, `unsupported_encoding`).
- PDF text clean-up (extractor version 2): ligatures (ﬁ, ﬂ, ﬃ) become plain letters; icon-font
  glyphs (Font Awesome etc.) are removed; digits, brackets and dashes that the Inter font draws
  as alternates (private-use code points) are restored when an Inter font is in the PDF; any
  other unreadable character becomes "�" so a missing digit is visible rather than silently
  dropped. Checked on 2026-11-10 against 20 real CV PDFs: all extracted, 2 characters left
  unreadable in total. `POST /api/v1/documents/{id}/extract` re-runs extraction on older uploads.
- Extracted text never creates or verifies profile facts on its own.
- Upload limit: `MAX_UPLOAD_BYTES` (default 20 MB).

### Jobs and sources

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/jobs` | Manual entry. `title` and `company` required. `url` is stored, never fetched. |
| POST | `/api/v1/jobs/import` | `{"url": ...}`. One fetch you trigger yourself; reads schema.org `JobPosting` JSON-LD only. |
| GET | `/api/v1/jobs` | `q`, `company`, `location`, `source`, `status` (repeatable), `employment_type`, `work_mode`, `language`, `available_from_finland` (repeatable: `yes`, `no`, `unknown`), `published_from/to`, `deadline_from/to`, `hidden`, `include_hidden`, `sort` (`newest`, `published`, `deadline`, `company`, `title`), `limit`, `offset`. |
| GET/PATCH | `/api/v1/jobs/{id}` | PATCH: `status`, `hidden`, `user_notes`, and corrections to job details. |
| POST | `/api/v1/jobs/{id}/merge` | `{"into_job_id": ...}`. The user confirmed two jobs are the same posting. |
| GET | `/api/v1/sources` | Built-in sources (`manual`, `url_import`, `email_alerts`, one `alert_*` per alert sender and one `feed_*` per job feed), with access policy and last error. |
| PATCH | `/api/v1/sources/{key}` | `{"enabled": false}` turns a source off (a turned-off feed is not read). |
| GET | `/api/v1/feeds` | Job feeds: interval, last result, readable last error, when the next check is allowed, jobs per feed, attribution text. |
| POST | `/api/v1/feeds/sync` | Check every feed that is due now; one result per feed read (with `error` if it failed). |
| POST | `/api/v1/feeds/{key}/sync` | Check one feed. 429 `too_soon` (with `details.next_allowed_at`) if it was read too recently; 502 with `details.reason` if it could not be read. |
| GET | `/api/v1/job-alerts` | Alert mailbox status: set up or not, last check, readable last error, counts per site. |
| POST | `/api/v1/job-alerts/sync` | Check the alert mailbox now. 409 if not set up or already running; 502 with `details.reason` if the mailbox fails. |
| POST | `/api/v1/job-alerts/emails` | Upload saved alert emails (`files`, `.eml`, up to 50, 5 MB each). Works without mailbox access. |

Job rules:

- **Dates are never guessed.** `published_on` and `deadline_on` are exactly what the source (or
  you) states, otherwise `null`. `first_seen_at` is when DuuniScript first saw the job and is never
  used as a publication date. `deadline_at` is set only when the source gives a time *and* a
  timezone.
- **Duplicates, stage 1:** same normalised URL (tracking parameters, fragments and trailing slash
  ignored) or the same job ID from the same site. A duplicate returns 409 `duplicate_job` with the
  existing `job_id`; for URL import this is checked before anything is fetched.
- **Duplicates, stage 2** (`services/job_matching.py`), so one posting seen on several sites is one
  job and is never applied to twice. Company and job title must match after normalisation (case,
  punctuation, legal forms such as Oy/Ltd/GmbH, country tags such as "(FI)", gender markers such
  as "(m/f/d)"). Then:
  - nothing contradicts it → **same**: URL imports and alert emails are added to the existing job
    as another listing and fill in details it lacks (never overwriting). URL import returns
    **200** instead of 201 in that case;
  - listing dates more than 45 days apart, locations with no word in common, or descriptions that
    differ (both at least 200 characters, under 60 % word-sequence overlap), or a title that is
    only close → **possible**: a new job is created with `possible_duplicate_of` set to the
    existing job's ID, and the user decides (merge, or `PATCH` `possible_duplicate_of: null`);
  - descriptions are compared only when both jobs have one. Alert emails carry none, and the same
    job can be advertised in Finnish on one site and in English on another, so different text
    alone never proves two jobs are different.
  Manual entries are never merged automatically, only flagged.
- **Separate postings on one site** (e.g. the same title for several cities or regions) are
  different jobs and are not flagged, unless you have already applied to (or are drafting for)
  the other one: then the new one is flagged, which catches a repost.
- **Available from Finland** (`available_from_finland`, `services/eligibility.py`): `yes` when the
  stated location is in Finland, or a remote job is open to Finland (worldwide, anywhere,
  Europe/EU/EMEA, Nordics, Finland, or a time zone including UTC+2); `no` when the location or
  the remote restriction is elsewhere ("USA", "LATAM, Canada", "London, UK", a title such as
  "(U.S. Based)"); otherwise `unknown`. Recomputed when the location is edited. Migration `0006`
  marks existing jobs with a Finnish location as `yes`.
- **Merging** (`POST /api/v1/jobs/{id}/merge`): listings move to the kept job, missing details are
  copied, notes are joined, and the further application status (`new` → `applied`) is kept.
  The later deadline wins, and an expired or archived job that is listed again opens again.
- **Reposts** (the same site lists the same job again under a new posting ID): with the same
  company, title and place they are merged on import, and housekeeping
  (`job_service.merge_reposts`, every 6 hours or `POST /api/v1/jobs/housekeeping`) merges older
  ones. The same title in another city stays a separate job. Unclear cases (listed more than 45
  days apart, or clearly different text) are only flagged "Possible duplicate" for you to merge.
- **URL import safety:** http/https on ports 80/443 only, no credentials in URLs, at most 5
  redirects, each checked; private, loopback and link-local addresses are refused; 15-second
  timeout; 3 MB limit; HTML only; no cookies or login. Turn it off with `URL_IMPORT_ENABLED=false`.
- **robots.txt is respected** (RFC 9309) on every hop. A refused page returns 422 with
  `details.reason = "robots_disallowed"`; add that job manually. A missing `robots.txt` (4xx)
  means no restrictions; a server error or unreachable `robots.txt` means don't fetch.
- Which sites work today: see `docs/SOURCE_EVALUATION.md`.
- **English first.** Imports send `Accept-Language: en, fi;q=0.5, sv;q=0.3`. If the posting is not
  in English and the page declares an English version of itself (`<link rel="alternate"
  hreflang="en">`) on the same site, that version is fetched once (same safety and robots rules)
  and used only if its advertisement text really is English and it is not a different job ID.
  Otherwise the original is kept; a failed English fetch is not an import failure. The snapshot
  records the other-language address.
- **Posting language** (`language`) is what the posting states (`inLanguage`), otherwise English,
  Finnish or Swedish detected from the advertisement text when it is clear, otherwise `null`.
  Nothing is translated. Filter with `GET /api/v1/jobs?language=en` (also matches `en-GB`) or
  `language=unknown`.
- **Source errors** (`GET /api/v1/sources`, `last_error`) are short English sentences, not codes.
  Migration `0004` converts codes stored by earlier versions.
- **No guessing from page text.** If a page has no `JobPosting` structured data, the result is 422
  `no_structured_job_data`; add the job manually instead.
- **Provenance:** each import stores a read-only JSON snapshot of the structured data (not the
  whole page) in `source_snapshots/`, with capture time and parser version.
- **Untrusted content:** job text is stored and returned as plain text and never acted on.
- `status` values: `new`, `reviewed`, `saved`, `not_relevant`, `drafting`, `applied`, `closed`,
  `expired`. `hidden` is separate from `status`.

### Third-party libraries added in this milestone

| Library | License | Use |
|---|---|---|
| pypdf | BSD-3-Clause | PDF text extraction |
| python-docx | MIT | DOCX text extraction |
| python-multipart | Apache-2.0 | Multipart upload parsing |
| httpx | BSD-3-Clause | Fetching a page for URL import |
| keyring | MIT | Mailbox password in Windows Credential Manager |
| tzdata | Apache-2.0 | Time zone data on Windows (Finnish deadlines in feeds) |
| fpdf2 | LGPL-3.0 (used unmodified as a library) | PDF export of CVs and cover letters |
| Pillow | MIT-CMU (HPND) | Opening and checking images for OCR |
| winrt-* (pywinrt) | MIT | Access to the Windows OCR engine (Windows only) |

`pymupdf` was deliberately not used because it is AGPL-licensed.

## 9. Backups and restore

While the API runs it makes a backup every `BACKUP_INTERVAL_HOURS` (default 24; `0` = off) and
keeps the newest `BACKUP_KEEP` (default 10). "Back up now": `POST /api/v1/backups`.

A backup is one zip in `%LOCALAPPDATA%\DuuniScript\backups`: a consistent copy of the database
(SQLite online backup, safe while the app runs), original documents, extracted text and job
source snapshots, plus `manifest.json` with a SHA-256 of every file. Backups contain personal
data: keep them on this computer or an encrypted drive, never in the repository or a public
cloud folder.

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/backups` | Interval, number kept, and the backups (newest first). |
| POST | `/api/v1/backups` | Makes one now (201). 409 `backup_in_progress`. |
| GET | `/api/v1/backups/{name}` | Download (attachment). |
| DELETE | `/api/v1/backups/{name}?confirm=true` | Without `confirm=true`: 409. |

**Restore** (stop DuuniScript first):

```powershell
.venv\Scripts\python.exe scripts\restore_backup.py "$env:LOCALAPPDATA\DuuniScript\backups\DuuniScript-backup-20261111-120000.zip"
```

Every file is checked against the manifest before anything is written. Into a folder that
already has data it refuses unless `--replace` is given; then the current database and documents
are moved to `replaced-<time>` first (nothing is deleted). `--target <folder>` restores
somewhere else, e.g. to inspect a backup.

## 10. Job alert emails

Job sites email alerts to you; DuuniScript reads those emails and never visits the sites. This
works for sites that refuse automated access (for example Duunitori), and new jobs keep arriving
while you are away. You browse and search them in DuuniScript whenever you like.

**Supported senders:** LinkedIn and Glassdoor (format checked against real alert emails on
2026-11-10); Duunitori, Jobly, Indeed, Oikotie, Monster, Kuntarekry, Job Market Finland, Europe Remotely and ZipRecruiter
(Työmarkkinatori) by their posting address patterns, not yet checked against a real alert. `GET
/api/v1/job-alerts` shows `format_verified` per site. If a site's emails produce no jobs, the
count `emails_without_jobs` / `unreadable_cards` says so; send one such email (saved as `.eml`) to
have its format added.

**Set up (Gmail):**

1. In Gmail, create a label, for example `DuuniScript`, and a filter that applies it to alert
   emails, e.g. `from:(jobalerts-noreply@linkedin.com OR noreply@glassdoor.com OR duunitori.fi)`.
2. Turn on 2-Step Verification, then create an **app password** (Google Account → Security →
   App passwords). Don't use your normal password. You can revoke an app password at any time.
3. In `.env`: `MAIL_IMAP_USER=you@gmail.com` (and `MAIL_FOLDER` if the label is not `DuuniScript`).
4. Save the password (input is hidden, stored only in Windows Credential Manager):

   ```powershell
   .venv\Scripts\python.exe scripts\set_mail_password.py
   ```

5. Start the API. It checks the label a minute after start and then every
   `MAIL_SYNC_INTERVAL_MINUTES` (default 60; 0 = only when you press "Check now"). The first check
   reads the last `MAIL_BACKFILL_DAYS` (default 30).

Without mailbox access, save alert emails as `.eml` (Gmail: ⋮ → Download message) and upload them
to `POST /api/v1/job-alerts/emails`.

**Rules:**

- Read-only: the label is opened read-only and fetched with `BODY.PEEK`, so emails stay unread,
  unmoved and undeleted. TLS with certificate checks. Only the one label is opened.
- Each email is processed once (its Message-ID is remembered in `alert_email`, with counts only;
  the email itself stays in the mailbox). Emails already processed are skipped before download.
- Only emails from a supported site **with a passing DKIM signature for that site's domain** (as
  recorded by Gmail in `Authentication-Results`) are read; look-alike senders are ignored. Only
  links on the site's own domain become jobs.
- Stored link: the clean posting address where it is known (LinkedIn `/jobs/view/<id>/`; sign-in
  and tracking tokens are dropped), otherwise the link as sent.
- Alert jobs have title, company, location and the link; no description. `published_on` is set
  only when the card states an age ("3d" in an email of 10 Nov → 7 Nov; "30d+" → unknown).
  Open the original posting, or import its URL, to add the full advertisement: it is matched to
  the alert job and fills in the description.
- Each job card is stored as a read-only snapshot in `source_snapshots/` (card fields and link).
- Readable errors in `last_error` (e.g. "The mailbox refused the sign-in. Check the address and
  save a new app password.").

## 11. Job feeds (official feeds and public job APIs)

DuuniScript reads these sites' own published feeds or APIs. Each site's terms and robots.txt
were checked on 2026-11-10 (`docs/SOURCE_EVALUATION.md`).

| Feed key | Site | What is read | At most every |
|---|---|---|---|
| `feed_remotive` | Remotive | Public remote jobs API | 6 h (site asks for max. 4 reads a day) |
| `feed_jobspresso` | Jobspresso | Job RSS feed (newest 10) | 2 h |
| `feed_weworkremotely` | We Work Remotely | Job RSS feed (newest 100) | 2 h |
| `feed_himalayas` | Himalayas | Jobs API search, jobs open to Finland (first page, 20) | 6 h |
| `feed_jobicy` | Jobicy | Jobs API, Finland and Europe (100 each) | 6 h (site: max. once an hour) |
| `feed_arbeitnow` | Arbeitnow | Job board API, remote jobs only | 6 h |
| `feed_abo_akademi` | Åbo Akademi | Official vacancies RSS feed (Turku) | 2 h |

**How it runs:** while the API runs, it looks every `FEED_SYNC_INTERVAL_MINUTES` (default 60,
first look 90 s after start) for feeds that are due and reads them. "Check now" (`POST
/api/v1/feeds/sync` or `/api/v1/feeds/{key}/sync`) obeys the same minimum interval. A failed
read is recorded as a sentence in `last_error` and also waits for the interval: no immediate
retries. Turn a feed off with `PATCH /api/v1/sources/{key}`.

**Rules:**

- Only the published feed or API address is read. robots.txt is honoured for every feed except
  Remotive, whose robots.txt lists `/api/*` for crawlers while its API documentation invites
  programs to use that address (with a link back and at most 4 reads a day), which is what we do.
- Each job keeps its link to the original posting, and the site is shown as the source
  (`attribution` in `GET /api/v1/feeds`). Jobs are only shown to you, never passed on.
- Feed content is untrusted: HTML is reduced to plain text, XML with a document type declaration
  is refused, sizes are limited (10 MB per response), and only links on the site's own domain
  are kept.
- Every job goes through the same duplicate rules as alert emails and URL import, so a job seen
  on several feeds, an alert email and an import is one job.
- Remote jobs limited to other countries are skipped (`FEED_SKIP_UNAVAILABLE=true`, default);
  `FEED_KEYWORDS` can limit feeds to jobs mentioning given words.
- Each job's feed item (fields only) is stored as a snapshot in `source_snapshots/`.
- Live check on 2026-11-10 (one read each): 192 jobs added from 319 found; 137 remote jobs for
  other countries skipped; 180 of the added jobs `yes`, 12 `unknown`.

## 12. Profile facts from CVs, CV and cover letter drafts, and applying

### Facts from your CVs

`GET /api/v1/documents/{id}/fact-suggestions` reads an uploaded CV's extracted text with simple
local rules (no AI): contact details from the top of the CV, the profile summary, jobs and
education with their dates, projects, publications, certificates, skills and spoken languages.
Recognised headings include Profile/Summary, (Work) Experience, Education (and Training),
Projects, Skills, Languages, Certifications/Certificates, Publications, plus a few Finnish ones.
Dates such as "Oct 2024 – Jun 2025", "2019 – 2022", "October 2024 to June 2025", "Sep 2022 –
Present" are read; an *expected* end ("exp. 2027") is left empty, because it is not a fact yet.
References and recommendations are never suggested (they are other people's data).

The user picks suggestions and saves them with `POST /api/v1/profile/facts/import`. They are
saved **unverified**, each with the CV as document evidence and the excerpt it came from. The
user then verifies them (one by one, or `POST /api/v1/profile/facts/verify` for a list).
Checked on 2026-11-10 against the user's real CVs in a private test folder: 21 of 22 readable
CVs gave suggestions (the 22nd is a study transcript); the newest CV gave 43 suggestions.

### Drafts (`/api/v1/applications`)

`POST /api/v1/applications` with a `job_id` starts an application:

- **CV**: built from **verified facts only**, with a template (`GET /api/v1/applications/templates`):
  `utu_rekry` (default; the University of Turku career services guide: profile, education, work
  experience, positions of trust, language levels, IT skills, references, at most two pages),
  `classic`, `compact` (one page: matching skills first, three most relevant roles) or
  `projects_first`. Or `cv_source: "uploaded"` with `cv_document_id` to send one of your uploaded
  CVs unchanged.
- **Cover letter** (optional): `utu_rekry` (default; "Job application" and date, the position
  as a heading, why this job, how you meet the requirements, an invitation to interview,
  "Yours sincerely" and "Appendices: CV"; one page; the CV's profile is not repeated), `standard`
  or `short`. The letter uses the same font as the CV, as the UTU guide asks. Built from verified facts: your most
  relevant role, the skills the posting names that you have, a relevant project and the languages
  the posting mentions. The reason you want the job is left as a `[placeholder]` that you must
  write yourself; approval is refused while it is there.
- Facts are ordered by how much they overlap with the job text; nothing from the job text is
  ever written as your claim. Unverified facts are never used. Each draft lists the facts it was
  built from (`evidence_fact_ids`).
- Drafts are Markdown you can edit (`PUT .../drafts/{cv|cover_letter}`), regenerate with
  another template (`POST .../regenerate`), and export (`GET .../export?format=pdf|docx|md|txt`).

**Claim check** (every draft, also after your edits; `issues` in the draft):

| Severity | Code | Meaning |
|---|---|---|
| error | `placeholder_left` | Text in `[square brackets]` is still there. |
| error | `unknown_contact` | An email address or phone number that is not in your profile or verified facts. |
| warning | `unsupported_date` / `unsupported_number` | A year or number no verified fact contains. |
| warning | `unsupported_skill` | A technical skill no verified fact mentions. |
| warning | `unsupported_link` | A web address not in your verified facts. |
| info | `job_terms_not_in_profile`, `language_not_in_profile` | What the posting asks for that your verified facts do not cover. |

`POST .../drafts/{kind}/approve`: errors block approval (422 `draft_has_errors`); warnings need
`acknowledge_warnings: true` (409 `warnings_not_acknowledged` otherwise). Approved versions are
never changed: editing one creates a new version and the application goes back to `draft`.

### Applying: the user sends, DuuniScript records

When the CV (and the cover letter, if included) are approved, the application is `ready` and
has a `package_hash`. DuuniScript **never submits an application or sends an email**:

- `GET .../package`: the final review: employer, role, where to apply (the posting's
  application link), email addresses written in the posting itself (never guessed), the files
  and their hashes, and the cover letter as plain text to paste into a form.
- `GET .../package.zip`: the approved files as PDF and Word plus a README.
- `GET .../email.eml`: an **unsent** email draft with the files attached, to open in your mail
  program, check and send yourself. `To` is filled only when the posting states exactly one
  address.
- After sending it yourself: `POST .../submission` with `confirm: true`, the `package_hash` you
  reviewed, the method (`web_form`, `email`, `other`) and an optional confirmation reference.
  A changed package is refused (409 `package_changed`). The job becomes `applied`; the
  application becomes read-only (withdraw is still possible). Uncertain submissions are never
  recorded automatically.
- `GET .../events`: approvals, reopenings and the submission record. Audit entries never hold
  draft text.

Filling in employers' web forms automatically is not built: it would need per-site browser
automation, which many sites forbid, and it must pause before every final submit (PRD FR-018).

PDF export uses Calibri, Arial or Georgia from the Windows font folder (all characters,
including Finnish letters and dashes); without them it falls back to Helvetica.

## 13. Job match score

Every job gets a **match score** from 0 to 100 computed from your **verified** facts only (rules,
no AI), with readable reasons (`GET /api/v1/jobs/{id}/match`):

| Part | Points | How |
|---|---|---|
| Skills | 60 | Technical skills the posting names (about 100 known terms such as SQL, Python, Power BI) and your verified skills it mentions. Divided by at least 4, so a posting naming one or two terms cannot give full points. |
| Role | 25 | How many words of the job title appear in a verified role, degree or target-role preference. |
| Wording | 15 | Overlap between the posting's words and your verified facts. |
| Your decisions | ±10 | From 3 decisions on: titles like jobs you marked "not relevant" go down, titles like jobs you saved, drafted or applied to go up. Shown as a reason. |

**Blockers** cap the score at 30 and are listed: the job is not open to people in Finland, the
deadline has passed, or the posting requires Finnish or Swedish (not "an advantage") and your
verified language facts do not show it at a working level (native, fluent, B2–C2).

`missing_terms` lists the technical terms the posting names that none of your verified facts
cover: useful for deciding what to learn or what evidence to add, never added to drafts.

Scores are stored (`job_match`) with a fingerprint of the verified facts, the date and the job
text, and recomputed automatically when any of them changes. The score is a ranking aid, not a
judgement: the user decides. Checked 2026-11-11 with the user's verified test facts against the
196 real feed jobs: data and analytics roles ranked first.

## 14. Signing in to DuuniScript

Until a passphrase exists the API is open (it only listens on 127.0.0.1), as before. Create one
in the app (`POST /api/v1/auth/setup`, at least 10 characters); from then on every `/api/v1`
request needs `Authorization: Bearer <token>` from `POST /api/v1/auth/login`. `/health`, the
`/api/v1/auth/*` routes and the Google sign-in return address stay open.

- The passphrase is stored as a salted scrypt hash; session tokens only as SHA-256 hashes.
  Sessions last `AUTH_SESSION_DAYS` (default 30). Five wrong attempts lock sign-in for a minute.
- `POST /api/v1/auth/change` changes it and signs out every other browser; `/logout` signs out.
- Forgotten passphrase: stop the app and delete the `app_credential` row with a SQLite tool (or
  restore a backup); the data itself is not encrypted by the passphrase.

**What this is not:** a password manager for other websites. DuuniScript does not store your
UTU, Google, JobTeaser or employer passwords and cannot sign you in to their sites: a web page
cannot fill another site's sign-in form, and handling those passwords or 2FA codes is
deliberately out of scope. Use your browser's password manager and "stay signed in" for that.

## 15. Connected accounts: Gmail and a Microsoft 365 (UTU) mailbox

Both are optional and read-only for alert emails; you sign in on Google's or Microsoft's own
page (with your own 2FA). DuuniScript keeps only the refresh token, in Windows Credential
Manager. Alert emails are found by the job sites' sender domains, so no Gmail label or filter
is needed. `GET /api/v1/integrations` shows the state; `POST /api/v1/integrations/{google|microsoft}/sync`
checks now; `DELETE /api/v1/integrations/{provider}` disconnects (and revokes the Google token).
While the API runs, connected mailboxes are checked every `MAIL_SYNC_INTERVAL_MINUTES`.

### Gmail (one-time setup, about 10 minutes, free)

1. <https://console.cloud.google.com> → create a project (e.g. "DuuniScript").
2. APIs & Services → Library → enable **Gmail API**.
3. OAuth consent screen → External → add your own Gmail address as a **test user**.
4. Credentials → Create credentials → OAuth client ID → **Desktop app** → Download JSON.
5. Save it outside the repository, e.g. `%LOCALAPPDATA%\DuuniScript\google-client.json`, and in
   `.env`: `GOOGLE_OAUTH_CLIENT_FILE=C:\Users\<you>\AppData\Local\DuuniScript\google-client.json`
6. In DuuniScript: Settings → Connected accounts → Connect Gmail → sign in on Google's page.

Permissions asked: read Gmail (alerts), compose (drafts, and sending an application **only when
you confirm it**). `POST /api/v1/applications/{id}/gmail-draft` puts the approved application in
your Gmail Drafts; `POST /api/v1/applications/{id}/send-email` sends it after your explicit
confirmation with the reviewed `package_hash`, then records it as sent. A failed send is never
retried automatically: check your Sent folder first. Gmail replaces the IMAP app password; IMAP
stays as the fallback when Gmail is not connected.

### Microsoft 365 mailbox, e.g. UTU (JobTeaser alerts arrive there)

1. <https://entra.microsoft.com> (any Microsoft account) → App registrations → New registration →
   "Accounts in any organizational directory" → Register.
2. Authentication → **Allow public client flows: Yes**. API permissions: Microsoft Graph →
   delegated `Mail.Read`, `User.Read` (and `offline_access`).
3. Copy the Application (client) ID into `.env`: `MS_CLIENT_ID=<id>` (`MS_TENANT` defaults to
   `organizations`).
4. In DuuniScript: Settings → Connected accounts → Connect university mail → open
   microsoft.com/devicelogin, type the code shown, sign in with your UTU account and 2FA.

Only emails from known job sites (now including **JobTeaser**) are downloaded; other emails in
the mailbox are never opened. **The university decides whether this is allowed:** many
universities require an administrator to approve such an app. If so, the sign-in ends with
"requires an administrator to approve"; ask UTU IT, or keep uploading JobTeaser emails as
`.eml` files (Outlook on the web: open the email, … → Download).

## 16. Outcomes and notifications

- `PUT /api/v1/applications/{id}/outcome` with `no_response`, `interview`, `rejected`, `offer`,
  `accepted` or `declined` (only after sending; null clears). The dashboard counts interviews
  and offers.
- `GET /api/v1/notifications` (unread first, `unread` count): good matches (70+, no blockers, new
  in the last 14 days), deadlines within 3 days for saved or drafting jobs, applications approved
  but not sent for 2 days, and sent applications without an outcome after 14 days.
  `POST .../{id}/read`, `/read-all`, `/{id}/dismiss` (a dismissed notice never comes back).
- The match score now also learns from your decisions (section 13, "Your decisions", ±10).

## 17. Optional local AI wording (Ollama)

Off by default. To try it: install Ollama from <https://ollama.com>, run
`ollama pull llama3.1:8b` (about 5 GB; fits the RTX 2070's 8 GB), and set `OLLAMA_MODEL=llama3.1:8b`
in `.env`. Only a model on this computer (127.0.0.1) is used. `POST
/api/v1/applications/{id}/drafts/{kind}/polish` returns a reworded suggestion that is **not
saved** and goes through the same claim check (new skills, numbers, dates, changed
placeholders are flagged); you decide whether to use it. The job posting text is never sent to
the model. Benchmark it first as described in `MODEL_SETUP.md`.

## 18. Local AI, RAG, learning from your decisions, and jobs from screenshots

**Set-up on this computer (done 2026-11-14):** Ollama 0.40 (`winget install Ollama.Ollama`), models
`qwen2.5:7b` (4.7 GB, Apache-2.0; text and structured answers) and `bge-m3` (1.2 GB, MIT;
multilingual embeddings), and in `.env`: `OLLAMA_MODEL=qwen2.5:7b`, `OLLAMA_EMBED_MODEL=bge-m3`.
Ollama listens on 127.0.0.1 only; nothing is sent to any cloud service. If Ollama is not running,
start "Ollama" from the Start menu (it also starts with Windows). Everything below falls back to
the rule-based behaviour when it is off.

**RAG (retrieval):** verified facts and jobs are embedded with bge-m3 into the `embedding` table
(`POST /api/v1/ai/index`, and every `RAG_INDEX_INTERVAL_MINUTES`, default 15). Used for the match
score ("closeness in meaning", up to 20 points, rescaled) and to retrieve the verified facts
most relevant to a job. Unverified facts are never indexed. First run on the real data: 43 facts
and 911 jobs in 90 s.

**Learning from your decisions (reward model):** saving, drafting or applying to a job is a
positive reward, an interview or offer a stronger one, "not relevant" a negative one. A small
logistic-regression model over the score parts learns what *you* go for and moves scores by up
to ±10 (from 6 decisions, at least 2 of each kind), always with a reason. It is retrained from
scratch on every change; it does not change any language model. (Deep reinforcement learning is
not used: with tens of decisions it would not learn anything reliable.)

**Jobs from screenshots:** `POST /api/v1/jobs/from-screenshots` (up to 10 PNG/JPEG, in order).
Windows OCR reads the text; the local model fills in title, employer, location, type, mode,
salary, deadline, link and language as structured JSON. Checks: values not in the screenshots
word for word are flagged; dates that are not in the screenshots are left empty; the description
is the posting's own text. Nothing is saved until the user checks the form and saves it with
`added_from: "screenshots"`; such jobs come from the "Screenshots" source and are tagged
**Apply yourself** (`apply_manually`, editable). Tested on 7 real postings (VTT, Arla, imec ×4,
LinkedIn): 3–8 s each once the model is loaded (about 90 s for the very first one); typical
fixes needed were OCR letter mix-ups ("Al" for "AI") and one sub-heading taken as the title.
Then on 9 JobTeaser postings captured as phone-width screenshots (3–6 per posting): titles
split over lines are joined; "Al" is read as "AI" in titles and employers; the language comes
from DuuniScript's detector; "Partial" remote working is hybrid; "not provided" salaries are
left empty; a site name ("Career Services") is never accepted as the employer; and a deadline is
kept only next to words like "deadline", "apply by" or "hakuaika" (an internship's end date is
not a deadline). Still to check by hand: OCR of white text on black boxes (addresses) and the
occasional wrong title or employer, which the warnings and the form make easy to fix.

## 19. Form answers, Finnish templates, AI paragraphs, CV profiles and more

- **Form answers** (`GET /api/v1/applications/{id}/form-answers`): right to work, location, start
  date, salary expectation, notice period, languages, years of experience (verified dates only,
  overlaps counted once), education, matching skills, links, references, relocation and "why us",
  ready to copy. Each says where it comes from; the rest asks you once
  (`PUT /api/v1/form-answers/{key}`; "why us" is saved per application).
- **Finnish templates** `utu_rekry_fi` (Ansioluettelo, Työhakemus): chosen automatically when the
  posting is in Finnish. Your facts are used as written, never machine-translated.
- **AI-written fit paragraphs** (`POST …/drafts/cover_letter/ai-write`): the local model writes the
  "how I fit" paragraphs from the up to 8 verified facts most relevant to the job (RAG). The
  result is not saved and goes through the claim check; the posting is passed as data only.
- **CV profiles** (`/api/v1/cv-profiles`): name, focus words, optional own profile text and
  template. When an application starts, the profile whose words best match the posting is used
  (`auto_profile`), reordering verified facts; it never adds claims.
- **Housekeeping** (every `HOUSEKEEPING_INTERVAL_MINUTES`, `POST /api/v1/jobs/housekeeping`): open
  jobs past their deadline become expired; jobs older than `JOB_ARCHIVE_DAYS` (60) and never acted
  on are archived (hidden from lists, `include_archived=true` shows them).
- **Desktop notifications**: new in-app notifications appear as Windows notifications once,
  at most three per check (`DESKTOP_NOTIFICATIONS`, `DESKTOP_NOTIFY_INTERVAL_MINUTES`).
- **Statistics** (`GET /api/v1/stats/outcomes`): sent, replies, interviews, offers, rates, median
  days to reply, by source and by role word, and sent per week.
- **Pasted text** (`POST /api/v1/jobs/from-text`) works like screenshots; screenshots can be kept
  with the job (`screenshot_draft_id` when saving; `GET /api/v1/jobs/{id}/attachments`) and are
  included in backups.
- **Start at Windows sign-in**: `scripts\install_autostart.ps1` (and `-Remove`) puts a shortcut in
  your Startup folder that starts DuuniScript (and Ollama) in the background without a browser.

