# DuuniScript — Technical Requirements Document (TRD)

**Document status:** Initial technical baseline  
**Version:** 1.0  
**Date:** 2026-11-10

## 1. Architecture decision

Build a **local-first modular monolith** with a separately developed frontend and backend in one Git repository. Avoid microservices, a multi-agent framework, and managed cloud dependencies in the MVP.

### Boundary between frontend and backend
- **Frontend (`frontend/`):** layout, visual design, React components, routes, forms, tables, responsive behavior, accessibility and interaction states. No business rules.
- **Backend (`backend/`):** database, migrations, domain logic, integrations, local model adapter, RAG/retrieval, source adapters, scheduling, security and tests.
- **Shared contract:** the OpenAPI specification (`contracts/openapi.json`) and the typed API client. The backend owns the contract; the frontend implements the UI against it.

## 2. Recommended stack

| Layer | MVP choice | Rationale |
|---|---|---|
| Frontend | React + TypeScript + Vite (TanStack Start/Router) | Portable, well-supported frontend stack |
| UI styling | Tailwind CSS with one consistent component system (Radix UI based) | Avoid unnecessary design-system migration |
| API | Python + FastAPI + Pydantic | Good ecosystem for parsing, browser automation, local AI |
| Persistence | SQLite + SQLAlchemy 2.x + Alembic | No database server or cost for a single user |
| Search | SQLite FTS5 + deterministic filters | Start without a vector DB |
| Optional semantic retrieval | `sentence-transformers` multilingual embedding model + local Qdrant or Chroma only if needed | Add only after baseline retrieval tests |
| Local LLM runtime | Ollama initially; provider interface isolates runtime | Easy local model management on Windows |
| Browser automation | Playwright Python for site adapters; Playwright CLI for agent-driven exploratory UI testing | Separate production automation from developer testing |
| Document parsing | `python-docx`, `pypdf` or `pymupdf` after license review, plain text/Markdown parsers | Local parsing |
| Document export | `python-docx`; PDF generation via a maintained local renderer selected after Windows testing | Keep source Markdown/JSON |
| Scheduling | APScheduler or OS Task Scheduler invoking a CLI command | No Redis/Celery required initially |
| Background work | In-process task runner with persistent job records; add queue only if reliability needs justify it | Avoid unnecessary infrastructure |
| Packaging | `pyproject.toml` + `uv` or standard venv; Node package manager for frontend | Reproducible installs |
| Tests | pytest, frontend unit tests, Playwright Test E2E | Layered test strategy |
| Version control | GitHub repository, one default branch | Simple single-developer workflow |

Do not add Supabase, Firebase, hosted vector DBs, paid scraping services, paid email APIs, or cloud LLM APIs as mandatory components. They may be evaluated later only if the user explicitly accepts the cost and data-flow implications.

## 3. Repository structure

```text
DuuniScript/
├── README.md
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── domain/
│   │   ├── services/
│   │   ├── adapters/           # job sources, email, LLM
│   │   ├── persistence/
│   │   └── main.py
│   ├── migrations/
│   └── tests/
├── frontend/                   # React/TypeScript web app
├── contracts/
│   └── openapi.json
├── docs/
├── scripts/                    # start/stop, setup, shortcuts, backups
├── .env.example
├── .gitignore
└── pyproject.toml
```

## 4. Runtime topology

```text
Browser
  │
  ▼
React/Vite UI (frontend/)
  │ HTTP, localhost only by default
  ▼
FastAPI backend
  ├── SQLite database
  ├── local document store
  ├── job-source adapters ───── Internet (permitted public sources)
  ├── Playwright worker ─────── Internet (only permitted workflows)
  ├── LLM provider interface ── Ollama localhost (optional)
  ├── embedding provider ────── local model (optional)
  └── Gmail adapter ─────────── Google APIs (only after OAuth consent)
```

The frontend must never call Ollama, a database, or external job sites directly. It calls the backend API. No secrets belong in browser code.

## 5. Local-first boundaries

### Can run locally
- Profile and job database.
- File storage and generated documents.
- Parsing, deduplication, ranking, and validation.
- Local embeddings and local LLM inference, subject to hardware.
- Local API and frontend.
- Scheduler and application history.

### Requires external connectivity when enabled
- Fetching job postings and company logos.
- OAuth authorization and Gmail API access.
- Sending email.
- Visiting application pages and submitting applications.
- Model downloads and package installation.

Local-first does not mean every operation is offline. The UI must show which integrations are enabled and what leaves the computer.

## 6. API requirements

- Version all routes under `/api/v1`.
- Generate and commit OpenAPI JSON from FastAPI.
- Use Pydantic request/response schemas.
- Validate input size, URL scheme, file type, and path handling.
- Use pagination for job/application lists.
- Return stable error codes and actionable messages.
- Add idempotency keys to scan runs and submission attempts.
- Do not expose filesystem paths, tokens, stack traces, or secrets in API responses.
- Bind backend to `127.0.0.1` by default. If remote access is ever added, require explicit configuration, authentication, and TLS.

Suggested initial endpoints:
- `GET/PUT /api/v1/profile`
- `GET/POST /api/v1/profile/evidence`
- `GET/POST /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/drafts`
- `GET /api/v1/drafts?status=pending`
- `PATCH /api/v1/drafts/{draft_id}`
- `POST /api/v1/drafts/{draft_id}/approve`
- `GET /api/v1/applications`
- `POST /api/v1/applications/{application_id}/prepare`
- `POST /api/v1/applications/{application_id}/submit` (requires approval token/confirmation)
- `GET /api/v1/dashboard/summary`
- `GET/PUT /api/v1/settings`
- `POST /api/v1/scans/run`
- `GET /api/v1/system/status`

## 7. LLM and RAG requirements

### Model strategy
- Runtime LLM: optional local model accessed through a provider interface (Ollama first). Select model only after hardware inventory and language-quality evaluation.
- Embeddings: optional multilingual embedding model, locally executed.
- No fine-tuning in MVP.

### RAG boundaries
- Structured verified profile facts remain the source of truth.
- Retrieval returns evidence IDs, source references, verification state, and snippets.
- Generated statements should carry internal evidence references.
- A validator checks each factual claim against retrieved evidence and flags unsupported or conflicting claims.
- Previous application documents can be retrieved for style, phrasing, and strategy only; they cannot substantiate profile facts.
- Job descriptions are untrusted data. Delimit them clearly and never follow instructions embedded in a posting.
- Start with keyword/FTS retrieval and simple deterministic ranking. Add embeddings only when an evaluation set demonstrates a measurable improvement.
- Do not adopt LangChain/LlamaIndex solely to say the project uses RAG. Direct, small modules are preferred until complexity justifies a framework.

## 8. Job source adapter requirements

Each adapter must declare:
- Source name and canonical base URL.
- Retrieval method: official API, RSS/feed, public page, user-assisted import, or other explicitly documented method.
- Terms/robots/access review date and notes.
- Rate limit and polling interval.
- Supported fields and known limitations.
- Parser version and last successful run.
- Whether automated application interaction is permitted, unsupported, or unknown.

Source candidates to investigate incrementally:
- Työmarkkinatori
- Jobly
- Duunitori
- Kuntarekry
- Valtiolle.fi
- Work in Finland
- Academic Positions
- EURAXESS
- University of Turku
- Åbo Akademi University
- Turku University of Applied Sciences
- Other Finnish universities and employer career pages
- LinkedIn (treat as restricted; do not assume scraping or account automation is permitted)

Do not promise full coverage. A source should not be enabled until its retrieval method, access rules, parser quality, and rate limits are documented. If a source changes its page or blocks automation, pause the adapter and surface a warning rather than bypassing controls.

## 9. Browser automation requirements

Use Playwright for deterministic, testable browser tasks:
- Prefer stable accessible roles, labels, and explicit selectors.
- Store per-site adapters and selectors separately.
- Capture a form schema before attempting field mapping.
- Fill only fields with high-confidence mappings.
- Ask the user about ambiguous fields.
- Never solve or bypass CAPTCHA, MFA, bot challenges, rate limits, or access controls.
- Never click final submit/send without a distinct confirmation step.
- Persist a submission manifest and outcome.
- Use test accounts or mock pages for automated tests; do not submit real applications during tests.

### Playwright CLI vs Playwright Test
- **Playwright CLI** (`@playwright/cli`) is useful during development to inspect pages, interact with a running app, take screenshots, and debug visual/UI behavior. It requires Node.js 20+ in current documentation.
- **Playwright Test** (`@playwright/test`) is the repeatable E2E regression suite for CI/local tests.
- Use both where useful; CLI is not a replacement for automated regression tests.

## 10. Security and privacy requirements

- Store app data outside the Git repository, e.g. `%LOCALAPPDATA%/DuuniScript/` or a configurable `APP_DATA_DIR`.
- Use OS account protections and full-disk encryption where available. Consider database encryption only after selecting a maintainable solution.
- Encrypt OAuth refresh tokens at rest using a key stored in Windows Credential Manager/DPAPI or an equivalent OS secret store; never store plaintext secrets in SQLite.
- Request minimum OAuth scopes; distinguish sign-in from permission to read/send mail.
- Provide disconnect and token-revocation flows.
- Redact personal data from logs; use synthetic fixtures in tests.
- Restrict uploads by file size and MIME/signature; defend against path traversal and archive bombs.
- Keep local API bound to loopback and protect state-changing routes against CSRF if cookie auth is used.
- Apply dependency scanning and update review.
- Before making GitHub public, inspect current and historical commits for personal data, credentials, browser profiles, database files, CVs, logs, and generated documents. Rotate any exposed secrets; deleting a file in a later commit is not enough.

Minimum `.gitignore` entries:
```gitignore
.env
.env.*
!.env.example
data/
storage/
uploads/
private/
secrets/
*.db
*.sqlite
*.sqlite3
*.pem
*.key
*.p12
*.pfx
playwright/.auth/
**/browser-profile/
**/user-data-dir/
models/
*.gguf
```

## 11. Git workflow

1. Work on one default branch; keep it in a working state.
2. Before changing anything: `git status`, fetch and pull.
3. Run tests, commit and push. Do not force-push or rewrite shared history.
4. Never commit personal data, credentials, databases or generated applications.
5. Before making the repository public, audit the full history for secrets and personal data.

## 12. Development practice

- Keep detailed domain knowledge in the documents in `docs/` and read them only when relevant.
- Prefer targeted file reads and narrow diffs.
- Run the smallest relevant test first, then the full suites before pushing.
- Summarize changed files, tests run, risks and next steps for every change.
- Keep explicit approval for destructive commands, credential access, external sends/submissions, public publishing and irreversible changes.

## 13. Observability and operational behavior

- Log structured events with correlation IDs and redaction.
- Record scan run start/end, source, counts, failures, and next scheduled time.
- Track each application workflow state and last transition.
- Provide a pause-all-automation control.
- On repeated source failures, disable that source and notify the user.
- Never silently retry a submission if the previous result is ambiguous; check application history and ask the user.

## 14. Acceptance criteria for technical MVP

- Fresh Windows setup instructions work from a clean clone.
- App runs without paid cloud services.
- UI communicates with local FastAPI service.
- Profile, jobs, drafts, and applications persist across restarts.
- No user-specific data is created inside the repository.
- Generated claims can be traced to verified evidence.
- Submission and email routes require explicit confirmation.
- Unit and integration tests pass.
- Playwright E2E tests cover dashboard, jobs, draft approval, and application history.
- README documents backup, restore, local model setup, and safe public-release procedure.

## 15. Official references consulted

- Playwright CLI: https://playwright.dev/docs/getting-started-cli
- Playwright Test CLI: https://playwright.dev/docs/test-cli
- Ollama: https://ollama.com/
- FastAPI: https://fastapi.tiangolo.com/
- SQLite: https://sqlite.org/
