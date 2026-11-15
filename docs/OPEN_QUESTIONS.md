# DuuniScript — Open Questions and Document Conflicts

Found during the initial repository inspection (2026-11-10). Resolve these before the related
features are built. Until then, `contracts/openapi.json` is the source of truth for the API.

1. **Document naming collision.** Resolved 2026-11-15: the separate design brief was removed; the
   built frontend is the design reference, and "DBD" means the Database Design Document only.
2. **Navigation differs.** AFD lists 9 areas (including Documents and Sources and scanning). The
   design brief lists 7 (no Documents or Sources) and uses "Profile & evidence".
3. **Job status values differ.**
   - PRD uses `dismissed` and `interested`.
   - AFD uses `not_relevant` and has no `interested`.
   - Design brief badges include "Interested", "Submission attempted" and "Interview".
   Proposal: one backend enum for job status and a separate one for application status. The UI
   maps both to badge labels.
   **Implemented (jobs milestone):** the job status enum follows AFD (`new`, `reviewed`, `saved`,
   `not_relevant`, `drafting`, `applied`, `closed`, `expired`) plus a separate `hidden` flag.
   "Interested" is not a separate state; the UI can show `saved` as "Saved / interested".
   Confirm or adjust.
4. **Uncertain submission state.** The master prompt says `submission_unknown`; AFD says
   `unknown`. Proposal: `unknown` in the application status enum, displayed as "Submission status
   is uncertain".
5. **Draft endpoints differ.** An early frontend handoff used `/applications/{id}/drafts`; TRD uses
   `/jobs/{id}/drafts` and `/drafts/{id}`. To be decided when drafting is built.
6. **Paths in the docs don't match.** The TRD repository tree lists different doc filenames from
   the real ones. The logo is suggested both at `apps/web/public/brand/` and `assets/brand/`.
   The frontend lives in `frontend/` (see 8).
7. **Logo.** The supplied PNG is black on an opaque white background (not transparent) and about
   700 KB. A dark-mode variant and a smaller web export are needed from the owner.
8. **Repository layout.** Resolved 2026-11-15: the backend and the frontend live in this one
   repository (`backend/`, `frontend/`).
9. **Fact categories.** The backend uses: contact, summary, education, work_experience, skill,
   project, certification, language, publication, reference, achievement, preference, other.
   Confirm or adjust before the profile UI is built.
