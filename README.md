# DuuniScript

A local-first, human-supervised job-search and application assistant for Finland.

DuuniScript collects job postings, removes duplicates, ranks them against your verified profile,
prepares tailored CVs and cover letters, and keeps track of every application and its outcome.
It runs entirely on your own Windows PC. You review and approve everything; nothing is sent
without your explicit confirmation.

## Features

- **Jobs:** official job feeds, job-alert emails (Gmail / university mail), link import, pasted
  text and screenshots (read by local AI). Reposts and the same job on several sites become one job.
- **Matching:** jobs ranked against your verified facts, with local semantic search and a model that
  learns from your own decisions (save, hide, apply).
- **Applications:** CVs and cover letters in English or Finnish, several CV profiles, AI-written fit
  paragraphs checked against your facts, ready-to-copy answers for application forms.
- **Tracking:** application status, outcomes, statistics, deadlines, desktop notifications,
  automatic expiry and archiving of old jobs.
- **Privacy:** your data stays on your PC in `%LOCALAPPDATA%\DuuniScript`; the app only accepts
  connections from the same computer and is protected by a passphrase.

## Stack

- Frontend: React and TypeScript (Vite, TanStack Router), tested with Vitest.
- Backend: FastAPI and Pydantic, tested with pytest.
- Database: SQLite with SQLAlchemy and Alembic.
- AI (optional, local): Ollama with `qwen2.5:7b` for text and `bge-m3` for embeddings.
- Scheduling: background timers inside the backend.

## Getting started

Requirements: Windows 11, Git, Node.js LTS, [uv](https://docs.astral.sh/uv/); optionally
[Ollama](https://ollama.com) for local AI.

```powershell
git clone https://github.com/SCP619/DuuniScript-JobHunt-AI.git
cd DuuniScript-JobHunt-AI
powershell -ExecutionPolicy Bypass -File scripts\setup_new_pc.ps1
```

Then start **DuuniScript** from the Desktop or Start menu (or double-click `Start DuuniScript.cmd`).
It opens http://127.0.0.1:8080. Stop it with **Stop DuuniScript**.

- Moving to another PC, restoring a backup, starting at sign-in: `docs/WINDOWS_SETUP.md`.
- Backend configuration, API, job sources and integrations: `docs/BACKEND_SETUP.md`.
- Local AI models: `docs/MODEL_SETUP.md`.

## Private data

Everything personal lives outside Git in `%LOCALAPPDATA%\DuuniScript` (or `APP_DATA_DIR`):
profile, documents, database, generated applications, screenshots, backups and logs. Sign-in
tokens and mailbox passwords are kept in Windows Credential Manager. Copy your data between PCs
with a backup zip (Settings > Backups), never through Git.

## Repository guide

```text
backend/app/        FastAPI application (api, core, domain, services, persistence)
backend/migrations/ Alembic migrations
backend/tests/      pytest suite (synthetic data only)
frontend/           React/TypeScript web app (npm run dev, npx vitest run)
contracts/          OpenAPI contract shared by backend and frontend
docs/               Product, technical and setup documents
scripts/            Start/stop, setup, shortcuts, backup restore, OpenAPI export
```

## Tests

```powershell
.venv\Scripts\python.exe -m pytest          # backend
cd frontend; npx vitest run; npx tsc --noEmit -p .   # frontend
```

## Security

The API binds to `127.0.0.1` only. Applications and emails are never sent without your approval,
and uncertain submissions are never retried automatically. Job sites' terms and rate limits are
respected; CAPTCHAs, MFA and other access controls are never bypassed. See `docs/SECURITY.md`.

## Status

What is built and what is left: `docs/STATUS.md`. Job sources and their status:
`docs/SOURCE_EVALUATION.md`.
