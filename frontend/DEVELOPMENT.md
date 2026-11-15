# Frontend development notes

Design decisions to keep when changing the web app.

- tsconfig: `noPropertyAccessFromIndexSignature` and `exactOptionalPropertyTypes` are off — API types use `?: T | null` and error details are index signatures; other strict flags stay on.
- All backend access goes through `src/api` (`api` object); `VITE_USE_MOCKS` picks `mock.ts` or `real.ts`. No business rules in UI; the mock only simulates server behaviour.
- Data is fetched client-side with React Query (no route loaders) because the backend runs on the user's laptop and is unreachable from SSR. Queries never auto-retry.
- External text (job descriptions, extracted text) renders as plain text with the `plain-text` utility; never HTML/Markdown.
- Shared job metadata display helpers live in `src/lib/job-presentation.ts`; both list and detail use them to keep language labels and original-source selection consistent without translating content.
- `api.importJob` returns `{ job, created }` (created=false for HTTP 200) because the UI must tell "added to existing job" apart from a new job; `requestWithStatus` in `src/api/http.ts` exposes the status.
- Feed switches share one control that refreshes sources and feeds after API updates so both Settings views stay consistent.
- Finland availability selection is URL-backed with a localStorage fallback read after hydration; list queries wait for that preference to avoid a mismatched initial request.
- Feed summaries, attribution lookup and availability query mapping live in browser-safe presentation helpers; scheduling and job eligibility remain API-owned.
- Application payload shaping, issue grouping, event labels and the draft preview parser live in `src/lib/applications.ts`; readiness, issues, versions and package hashes stay API-owned. The preview renders only React text nodes.
- File downloads (exports, package zip, .eml) go through `requestBlob` in `src/api/http.ts`, which reads the Content-Disposition filename (filename* first); the UI saves the blob.
- The sign-in token lives only in memory + sessionStorage (`src/api/auth-token.ts`); `src/api/http.ts` adds the bearer header to every request and blob download and signals `AuthGate` on 401 `auth_required`, which shows Sign in in place of the current route so the user returns to the same page.
- Account, outcome, Gmail-send and template-ordering payload helpers live in `src/lib/account.ts`; sending email needs the explicit dialog checkbox and never retries.
- Extend generated API types in `src/api/job-additions.ts` rather than editing generated contracts; screenshot reading returns an editable review and only its explicit Save creates a job.
- Screenshot thumbnails use revocable browser object URLs; ordered multipart uploads and index updates use the authenticated API request wrapper with a three-minute timeout.

- Form-answer keys, profile-selection payloads and copy-all formatting use browser-safe application helpers; all generated answers, AI paragraphs, profile selection and outcome statistics remain local API-owned.
- Text and screenshot imports share the editable review; attachment images are fetched with the authenticated blob wrapper and use revocable object URLs.
