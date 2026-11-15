# DuuniScript — Status (2026-11-14)

What works today, and what is left. PRD requirement IDs in brackets.

## Done

**Profile and documents**
- Local profile, facts with evidence and verification, bulk verify [FR-001, FR-002].
- Upload PDF, Word, text, Markdown, HTML and images; OCR for images and scanned PDFs [FR-003].
- Fact suggestions read from a CV; the user picks and verifies them.

**Finding jobs**
- Manual entry, URL import, seven official feeds, alert emails from 16 job sites
  (LinkedIn and Glassdoor verified; JobTeaser, Valtiolle and others waiting for a first email)
  [FR-004, FR-005, FR-016, FR-017].
- Alert emails from Gmail or a Microsoft 365 (UTU) mailbox through a sign-in on Google's or
  Microsoft's own page, or from IMAP, or uploaded as .eml files.
- Duplicate detection, "Can I work from Finland?", search and filters [FR-006, FR-007].
- Match score with reasons, blockers, missing skills, meaning-based closeness (RAG) and a
  reward model that learns from your decisions and outcomes [FR-008, FR-024].
- Jobs from screenshots, checked by you and tagged "Apply yourself".

**Applying**
- CV and cover letter from verified facts; UTU Rekry layout by default, plus five other
  templates; uploaded CVs sent unchanged [FR-009].
- Claim check, length and repetition checks, approval, immutable versions [FR-010, FR-011].
- PDF/Word/Markdown/text export, package zip, .eml draft, Gmail draft, and sending from Gmail
  after explicit confirmation [FR-015, FR-019].
- Submission record, outcomes (interview, rejection, offer…) [FR-012, FR-022].
- Local AI (Ollama, qwen2.5:7b + bge-m3, installed): RAG search over verified facts and jobs,
  rewording suggestions behind the claim check, and jobs read from screenshots.

**Running it**
- Dashboard, notifications [FR-013, FR-020], backups and restore, sign-in to the app.

## Left to do

**Needs you (DuuniScript cannot do these for you)**
- Verify your profile facts: only you can confirm they are true.
- Write the "why this job" sentence in each cover letter.
- One-time setups: Gmail (Google Cloud OAuth client), Microsoft 365 app registration for UTU
  mail (UTU IT may need to approve it), job alert subscriptions on the sites you want
  (accounts and sign-ins on those sites are yours).
- Optional: add Finnish as a Windows language for OCR of Finnish documents and screenshots.

**Next to build**
- Windows desktop notifications (today: in the app).
- Outcome statistics over time (response rates by source and role).
- A first real alert email from JobTeaser, Valtiolle, Europe Remotely and ZipRecruiter, to
  verify their formats.

**Deliberately not built**
- Signing in to other websites for you, storing their passwords, or getting around 2FA.
- Filling in and submitting employers' web forms automatically [FR-018].
