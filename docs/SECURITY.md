# DuuniScript — Security and Privacy Requirements

## 1. Purpose

DuuniScript processes sensitive career, contact, education, reference, document and potentially email information. Security and privacy are core requirements.

## 2. Data classification

**Highly sensitive:** OAuth credentials, passwords, cookies, private email, identification details, references and private application answers.

**Sensitive:** CVs, cover letters, education records, employment history, certificates, application packages and interview notes.

**Internal:** scan logs, match explanations, application metadata and diagnostics.

Public job information can still have copyright, terms and retention restrictions.

## 3. Local storage

Default private data directory: `%LOCALAPPDATA%\\DuuniScript`.

Never commit `.env`, databases, CVs, uploaded/generated documents, backups, OAuth credentials, browser profiles, cookies, model weights or personal logs.

## 4. Repository safety

Keep the repository private during development. Before public release inspect the working tree, tracked files, full Git history, secrets, frontend bundles, test fixtures, dependency/model licenses and data obligations. Removing a secret from the latest commit does not remove it from history.

## 5. Secrets

Use untracked `.env`; commit only placeholders in `.env.example`. Never print tokens, return them from APIs, include them in prompts, place secrets in frontend source or commit credentials.

Use a protected local credential store or established authenticated encryption for OAuth credentials. Do not invent cryptography.

## 6. API and files

Bind to loopback by default. Before LAN access, add authentication and firewall controls.

Validate inputs, request/upload sizes, MIME types and paths. Prevent path traversal, use parameterized SQL, restrict CORS, avoid exposing filesystem paths and redact errors.

Store uploads outside the web root, generate internal filenames, preserve originals, record hashes and never execute uploaded content.

## 7. AI security

Treat job posts, employer pages, emails, attachments and imported documents as untrusted data. External instructions cannot override system instructions, trigger tools, access secrets or authorize external actions.

Use structured schemas, validate outputs, limit supplied evidence, avoid exposing secrets to models and keep deterministic approval gates. LLMs may draft but cannot authorize submissions.

## 8. Factual accuracy

Personal claims require verified evidence or explicit user confirmation. Missing evidence must be flagged. Never infer degrees, dates, certifications, proficiency or achievements.

## 9. Browser and email

Use permitted workflows only. Do not bypass CAPTCHA, MFA, rate limits, anti-bot systems or access controls. Stop on unexpected page changes or ambiguous submission results.

Use minimum OAuth scopes. Show recipient, subject, body and attachments before sending. Require explicit approval and avoid bulk outreach.

## 10. Network

Localhost by default. If a second computer is ever used for inference, use a trusted private LAN, authentication and restrictive firewall rules. No public port forwarding. Do not transmit unnecessary profile data.

## 11. Backups and audit

Backups are sensitive: keep them outside Git, restrict access, define retention and test restore.

Audit profile verification, document/application approvals, submission attempts, email sends, integration changes and data export/deletion. Never log passwords, tokens or full private documents.

## 12. Incident response

If a secret is exposed, revoke/rotate it, identify exposure points, inspect Git history/logs/backups and document the incident.

If an application may have been submitted incorrectly, stop automation, preserve the audit trail, notify the user, verify external status and do not retry automatically.

## 13. Acceptance checklist

- [ ] Private data outside Git.
- [ ] `.env` ignored.
- [ ] No secrets in frontend.
- [ ] API loopback by default.
- [ ] Uploads and paths validated.
- [ ] External text treated as untrusted.
- [ ] LLM cannot authorize actions.
- [ ] Submission and email require approval.
- [ ] Logs redacted.
- [ ] Backups protected.
- [ ] Git history audited before public release.
