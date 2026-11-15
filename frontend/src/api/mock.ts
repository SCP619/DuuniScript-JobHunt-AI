// Synthetic, obviously fake data that simulates the backend's responses (including errors).
// This simulates the server only; the UI never relies on these rules directly.
import { ApiError } from "./errors";
import { getToken, setToken, signalAuthRequired } from "./auth-token";
import type { ApiService } from "./service";
import type {
  DocumentRead, EvidenceRead, FactRead, JobListingRead, JobRead, JobSummary, Page, ProfileRead,
  SourceRead, JobAlertStatus, AlertSyncResult, FeedsStatus, FeedSyncResult, ApplicationRead,
  ApplicationEventRead, DraftIssue, DraftKind, DraftRead, FactSuggestion, TemplateRead, PackageRead,
  DashboardSummary, DashboardJob, BackupRead, BackupsStatus, IntegrationsStatus, NotificationRead,
} from "./types";
import type { CvProfileRead, FormAnswerRead, JobMatchRead } from "./job-additions";

const uid = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : "xxxxxxxx-xxxx-4xxx-8xxx-xxxxxxxxxxxx".replace(/x/g, () => ((Math.random() * 16) | 0).toString(16));
const now = () => new Date().toISOString();
const daysFromNow = (d: number) => {
  const t = new Date(Date.now() + d * 86400000);
  return t.toISOString().slice(0, 10);
};
const isoDaysAgo = (d: number) => new Date(Date.now() - d * 86400000).toISOString();
const wait = (ms = 250) => new Promise((r) => setTimeout(r, ms));
const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v));
const notFound = (code: string, what: string) => new ApiError(404, code, `${what} was not found.`);
const validation = (loc: string, msg: string) =>
  new ApiError(422, "validation_error", "Some fields need attention.", {
    fields: [{ loc: ["body", loc], msg, type: "value_error" }],
  });

const sources: SourceRead[] = [
  { id: uid(), key: "screenshot_import", name: "Screenshots", domain: null, access_type: "user_provided", access_method: "screenshots", terms_url: null, policy_notes: null, enabled: true, last_success_at: null, last_error_at: null, last_error: null },
  { id: uid(), key: "manual", name: "Added by you", domain: null, access_type: "user_provided", access_method: "manual", terms_url: null, policy_notes: null, enabled: true, last_success_at: isoDaysAgo(1), last_error_at: null, last_error: null },
  { id: uid(), key: "example_feed", name: "Example Jobs Feed (sample)", domain: "feed.example.com", access_type: "official_feed", access_method: "rss", terms_url: "https://feed.example.com/terms", policy_notes: null, enabled: true, last_success_at: isoDaysAgo(0.2), last_error_at: isoDaysAgo(3), last_error: "The sample job feed was temporarily unavailable, so no jobs could be read." },
  { id: uid(), key: "example_board", name: "Sample Public Board", domain: "board.example.org", access_type: "public_structured_data", access_method: "url_import", terms_url: null, policy_notes: "Sample source for demonstration only.", enabled: true, last_success_at: isoDaysAgo(2), last_error_at: null, last_error: null },
  { id: uid(), key: "example_restricted", name: "Restricted Example Site", domain: "restricted.example.net", access_type: "restricted", access_method: "none", terms_url: null, policy_notes: null, enabled: false, last_success_at: null, last_error_at: null, last_error: null },
  { id: uid(), key: "email_alerts", name: "Job alert mailbox", domain: null, access_type: "user_provided", access_method: "imap", terms_url: null, policy_notes: null, enabled: true, last_success_at: isoDaysAgo(0.05), last_error_at: null, last_error: null },
  { id: uid(), key: "alert_linkedin", name: "LinkedIn job alerts", domain: null, access_type: "user_provided", access_method: "email_alert", terms_url: null, policy_notes: null, enabled: true, last_success_at: null, last_error_at: null, last_error: null },
  { id: uid(), key: "alert_glassdoor", name: "Glassdoor job alerts", domain: null, access_type: "user_provided", access_method: "email_alert", terms_url: null, policy_notes: null, enabled: true, last_success_at: null, last_error_at: null, last_error: null },
  { id: uid(), key: "alert_duunitori", name: "Duunitori job alerts", domain: null, access_type: "user_provided", access_method: "email_alert", terms_url: null, policy_notes: null, enabled: true, last_success_at: null, last_error_at: null, last_error: null },
  { id: uid(), key: "alert_jobly", name: "Jobly job alerts", domain: null, access_type: "user_provided", access_method: "email_alert", terms_url: null, policy_notes: null, enabled: true, last_success_at: null, last_error_at: null, last_error: null },
  { id: uid(), key: "alert_indeed", name: "Indeed job alerts", domain: null, access_type: "user_provided", access_method: "email_alert", terms_url: null, policy_notes: null, enabled: true, last_success_at: null, last_error_at: null, last_error: null },
  { id: uid(), key: "alert_oikotie", name: "Oikotie job alerts", domain: null, access_type: "user_provided", access_method: "email_alert", terms_url: null, policy_notes: null, enabled: true, last_success_at: null, last_error_at: null, last_error: null },
  { id: uid(), key: "alert_monster", name: "Monster job alerts", domain: null, access_type: "user_provided", access_method: "email_alert", terms_url: null, policy_notes: null, enabled: true, last_success_at: null, last_error_at: null, last_error: null },
  { id: uid(), key: "alert_kuntarekry", name: "Kuntarekry job alerts", domain: null, access_type: "user_provided", access_method: "email_alert", terms_url: null, policy_notes: null, enabled: true, last_success_at: null, last_error_at: null, last_error: null },
  { id: uid(), key: "alert_tyomarkkinatori", name: "Työmarkkinatori job alerts", domain: null, access_type: "user_provided", access_method: "email_alert", terms_url: null, policy_notes: null, enabled: true, last_success_at: null, last_error_at: null, last_error: null },
];
const feedNames = [
  ["remotive", "Remotive"], ["jobspresso", "Jobspresso"], ["weworkremotely", "We Work Remotely"],
  ["himalayas", "Himalayas"], ["jobicy", "Jobicy"], ["arbeitnow", "Arbeitnow"], ["abo_akademi", "Åbo Akademi"],
];
const feedsStatus: FeedsStatus = {
  check_interval_minutes: 30, skip_unavailable: true, keywords: [],
  feeds: feedNames.map(([slug, name], i) => ({
    key: `feed_${slug}`, name: `${name} (sample)`, domain: `${slug}.example.com`, enabled: i !== 6,
    access_method: "official_feed", terms_url: `https://${slug}.example.com/terms`,
    attribution: `Sample jobs from ${name}. Each job links back to its sample source page.`,
    min_interval_hours: 6, last_success_at: isoDaysAgo(1), last_error_at: i === 3 ? isoDaysAgo(0.1) : null,
    last_error: i === 3 ? "The sample feed was temporarily unavailable. Try again later." : null,
    next_allowed_at: i === 1 ? new Date(Date.now() + 3600000).toISOString() : null, jobs: i === 0 ? 1 : 0,
  })),
};
for (const feed of feedsStatus.feeds) sources.push({
  id: uid(), key: feed.key, name: feed.name, domain: feed.domain, enabled: feed.enabled,
  access_type: "official_feed", access_method: feed.access_method, terms_url: feed.terms_url,
  policy_notes: feed.attribution, last_success_at: feed.last_success_at,
  last_error_at: feed.last_error_at, last_error: feed.last_error,
});
for (const [key, name] of [["europeremotely", "EuropeRemotely"], ["ziprecruiter", "ZipRecruiter"]]) sources.push({
  id: uid(), key: `alert_${key}`, name: `${name} job alerts`, domain: null, access_type: "user_provided",
  access_method: "email_alert", terms_url: null, policy_notes: null, enabled: true,
  last_success_at: null, last_error_at: null, last_error: null,
});
const feedRunning = new Set<string>();
async function runFeed(key: string): Promise<FeedSyncResult> {
  const feed = feedsStatus.feeds.find((f) => f.key === key);
  if (!feed) throw notFound("feed_not_found", "The feed");
  if (!feed.enabled) throw new ApiError(409, "source_disabled", "This feed is turned off.");
  if (feedRunning.has(key)) throw new ApiError(409, "sync_in_progress", "This feed is already being checked.");
  if (feed.next_allowed_at && new Date(feed.next_allowed_at).getTime() > Date.now())
    throw new ApiError(429, "too_soon", "This feed was checked recently. Please wait until its next allowed check.", { next_allowed_at: feed.next_allowed_at });
  feedRunning.add(key);
  try {
    await wait(650);
    feed.last_success_at = now(); feed.last_error = null; feed.last_error_at = null;
    feed.next_allowed_at = new Date(Date.now() + feed.min_interval_hours * 3600000).toISOString();
    const source = sources.find((s) => s.key === key);
    if (source) { source.last_success_at = feed.last_success_at; source.last_error = null; source.last_error_at = null; }
    return { key, name: feed.name, jobs_found: feed.jobs, jobs_created: 0, jobs_merged: 0,
      jobs_already_known: feed.jobs, possible_duplicates: 0, skipped_not_available: 0, skipped_keywords: 0, error: null };
  } finally { feedRunning.delete(key); }
}
const sourceName = (k: string) => sources.find((s) => s.key === k)?.name ?? k;

function makeJob(p: Partial<JobRead> & { title: string; company: string }, src = "example_feed"): JobRead {
  const seen = p.first_seen_at ?? isoDaysAgo(Math.random() * 10);
  const listing: JobListingRead = {
    source_key: src, source_name: sourceName(src),
    source_url: src === "manual" ? null : `https://${src === "example_feed" ? "feed.example.com" : src.startsWith("feed_") ? `${src.slice(5)}.example.com` : src.startsWith("alert_") ? `${src.slice(6)}.example.com` : "board.example.org"}/jobs/${Math.floor(Math.random() * 99999)}`,
    external_id: src === "manual" ? null : String(Math.floor(Math.random() * 99999)),
    source_published_on: p.published_on ?? null, first_seen_at: seen, last_seen_at: seen,
    listing_status: "active", captured_at: src === "manual" ? null : seen, parser_version: src === "manual" ? null : "jsonld-1.2.0",
  };
  return {
    id: uid(), available_from_finland: "unknown", location: null, employment_type: null, work_mode: null, published_on: null, deadline_on: null,
    first_seen_at: seen, status: "new", hidden: false, canonical_url: listing.source_url, sources: [src],
    description: null, salary_text: null, language: null, application_url: null, deadline_at: null,
    last_seen_at: seen, user_notes: null, created_at: seen, updated_at: seen, listings: [listing], possible_duplicate_of: null,
    match_score: null, match_has_blockers: false, apply_manually: false, archived: false, ...p,
  };
}

let jobs: JobRead[] = [
  makeJob({ title: "Remote Developer (sample, US only)", company: "Example US Company", location: "United States", available_from_finland: "no", language: "de", work_mode: "remote", first_seen_at: now(), match_score: 22, match_has_blockers: true }, "feed_remotive"),
  makeJob({ title: "Ohjelmistokehittäjä (esimerkki)", company: "Esimerkki Oy", available_from_finland: "yes", location: "Helsinki", employment_type: "full_time", work_mode: "hybrid", published_on: daysFromNow(-3), deadline_on: daysFromNow(3), deadline_at: `${daysFromNow(3)}T14:00:00Z`, salary_text: "3 800–4 600 €/kk (sample)", language: "fi", description: "Tämä on esimerkkiilmoitus.\nEtsimme kehittäjää esimerkkitiimiin.\n\nTehtävät:\n- Esimerkkitehtävä 1\n- Esimerkkitehtävä 2\n\n<b>This tag is shown as plain text, never as HTML.</b>", application_url: "https://apply.example.com/esimerkki/123", status: "saved", match_score: 82 }),
  makeJob({ title: "Data Analyst (sample)", company: "Test Company Ltd", location: "Espoo", employment_type: "full_time", work_mode: "remote", published_on: daysFromNow(-6), deadline_on: null, description: "Sample description without paragraph breaks. ".repeat(30), language: "en", match_score: 64, apply_manually: true }, "example_board"),
  makeJob({ title: "Kesäharjoittelija, IT-tuki", company: "Demo Palvelut Oy", location: "Tampere", employment_type: "internship", work_mode: "onsite", published_on: null, deadline_on: daysFromNow(-2), description: "Esimerkkikuvaus harjoittelupaikasta.", status: "reviewed" }),
  makeJob({ title: "UX Designer (example)", company: "Esimerkki Oy", location: "Turku", employment_type: "contract", work_mode: "hybrid", published_on: daysFromNow(-1), deadline_on: daysFromNow(20) }),
  makeJob({ title: "Projektikoordinaattori", company: "Malli Säätiö sr", location: "Oulu", employment_type: "temporary", published_on: daysFromNow(-10), deadline_on: daysFromNow(4), status: "drafting" }),
  makeJob({ title: "Backend Engineer (sample)", company: "Placeholder Systems Oy", location: "Helsinki", work_mode: "remote", published_on: daysFromNow(-15), deadline_on: daysFromNow(-5), status: "applied" }),
  makeJob({ title: "Asiakaspalvelija (esimerkki)", company: "Testi Kauppa Oy", location: "Vantaa", employment_type: "part_time", status: "not_relevant", hidden: true }, "manual"),
  makeJob({ title: "Backend Engineer (sample)", company: "Placeholder Systems Oy", location: "Helsinki", language: "en", first_seen_at: isoDaysAgo(0.1) }, "alert_linkedin"),
  makeJob({ title: "Technical Writer (sample)", company: "Example Docs Ab", location: "Helsinki", employment_type: "full_time", language: "en-GB", published_on: daysFromNow(-2), deadline_on: null }, "example_board"),
];

// The alert job above looks like the applied "Backend Engineer (sample)" job.
const alertDuplicate = jobs.find((j) => j.sources.includes("alert_linkedin"));
const appliedJob = jobs.find((j) => j.status === "applied");
if (alertDuplicate && appliedJob) alertDuplicate.possible_duplicate_of = appliedJob.id;

let alertStatus: JobAlertStatus = {
  configured: true, mailbox: "test.person@example.com", folder: "DuuniScript", sync_interval_minutes: 30,
  last_sync_at: isoDaysAgo(0.05), last_error_at: null, last_error: null, emails_read: 14, jobs_created: 9, jobs_merged: 3,
  sites: [
    { key: "alert_linkedin", name: "LinkedIn job alerts", format_verified: true, emails_read: 9, last_email_at: isoDaysAgo(0.1) },
    { key: "alert_duunitori", name: "Duunitori job alerts", format_verified: true, emails_read: 4, last_email_at: isoDaysAgo(1) },
    { key: "alert_monster", name: "Monster job alerts", format_verified: false, emails_read: 1, last_email_at: isoDaysAgo(6) },
  ],
};
let syncing = false;
const emptySync = (): AlertSyncResult => ({ emails_checked: 0, emails_already_read: 0, emails_not_alerts: 0, emails_unverified: 0, emails_without_jobs: 0, jobs_found: 0, jobs_created: 0, jobs_merged: 0, jobs_already_known: 0, possible_duplicates: 0, unreadable_cards: 0 });

let profile: ProfileRead | null = {
  id: uid(), display_name: "Test Person", email: "test.person@example.com", phone: "+358 40 000 0000",
  location: "Helsinki (sample)", professional_summary: "Sample summary for a fictional person. Not real data.",
  created_at: isoDaysAgo(30), updated_at: isoDaysAgo(2),
};

const mkFact = (p: Partial<FactRead> & Pick<FactRead, "category" | "subject" | "value_text">): FactRead => ({
  id: uid(), profile_id: profile?.id ?? "", verification_status: "unverified", valid_from: null, valid_until: null,
  verified_at: null, created_at: isoDaysAgo(20), updated_at: isoDaysAgo(5), evidence_count: 0, ...p,
});
let facts: FactRead[] = [
  mkFact({ category: "education", subject: "MSc, Example University", value_text: "Master of Science in Sample Studies", valid_from: "2018-09-01", valid_until: "2020-06-15", verification_status: "verified", verified_at: isoDaysAgo(4) }),
  mkFact({ category: "work_experience", subject: "Developer at Esimerkki Oy", value_text: "Built sample internal tools.", valid_from: "2020-08-01" }),
  mkFact({ category: "skill", subject: "TypeScript", value_text: "Daily use in sample projects." }),
  mkFact({ category: "language", subject: "Finnish", value_text: "Native (sample)", verification_status: "verified", verified_at: isoDaysAgo(10) }),
  mkFact({ category: "certification", subject: "Example Cloud Certificate", value_text: "Sample certification", valid_from: "2021-01-01", valid_until: "2023-01-01", verification_status: "expired" }),
];

let documents: DocumentRead[] = [];
const mkDoc = (p: Partial<DocumentRead> & Pick<DocumentRead, "display_name" | "original_filename" | "category">): DocumentRead => {
  const ext = p.original_filename.split(".").pop()!.toLowerCase();
  return {
    id: uid(), file_extension: ext, mime_type: mimeFor(ext), size_bytes: 120_000, sha256: uid().replace(/-/g, ""),
    extraction_status: "succeeded", extraction_error: null, extracted_char_count: 4210, extractor_version: "extract-0.4.1",
    extracted_at: isoDaysAgo(6), extraction_method: "text", created_at: isoDaysAgo(6), updated_at: isoDaysAgo(6), archived_at: null, ...p,
  };
};
function mimeFor(ext: string) {
  return ({ pdf: "application/pdf", docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", txt: "text/plain", md: "text/markdown", html: "text/html", htm: "text/html", png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg" } as Record<string, string>)[ext] ?? "application/octet-stream";
}
documents = [
  mkDoc({ display_name: "CV – Test Person (sample)", original_filename: "cv_test_person.pdf", category: "cv" }),
  mkDoc({ display_name: "Scanned certificate", original_filename: "certificate_scan.pdf", category: "certificate", extraction_status: "no_text", extracted_char_count: 0, extraction_method: null }),
  mkDoc({ display_name: "Transcript (protected)", original_filename: "transcript.pdf", category: "transcript", extraction_status: "failed", extraction_error: "encrypted", extracted_char_count: null }),
  mkDoc({ display_name: "Old cover letter", original_filename: "cover_letter_old.docx", category: "cover_letter", archived_at: isoDaysAgo(3) }),
  mkDoc({ display_name: "Certificate photo (sample)", original_filename: "certificate_photo.jpg", category: "certificate", extraction_method: "ocr", extracted_char_count: 86 }),
];
const docTexts: Record<string, string> = {
  [documents[0]!.id]: "TEST PERSON\nSample CV — fictional data only\n\nEDUCATION\nMSc, Example University (2018–2020)\n\nEXPERIENCE\nDeveloper, Esimerkki Oy (2020–)\n<script>alert('shown as text')</script>\n\nSKILLS\nTypeScript, sample skill",
  [documents[3]!.id]: "Hyvä vastaanottaja,\n\nTämä on esimerkkihakemus.\n\nYstävällisin terveisin,\nTest Person",
  [documents[4]!.id]: "SAMPLE CERTIFICATE\nTest Person\nExample University\nRecognised from an image; fictional data only.",
};

let evidence: EvidenceRead[] = [
  { id: uid(), fact_id: facts[0]!.id, document_id: documents[0]!.id, source_type: "document", source_reference: null, excerpt: "MSc, Example University (2018–2020)", verification_status: "unverified", created_at: isoDaysAgo(5) },
  { id: uid(), fact_id: facts[3]!.id, document_id: null, source_type: "user_input", source_reference: "Native speaker", excerpt: null, verification_status: "unverified", created_at: isoDaysAgo(9) },
];
const syncEvidenceCounts = () => {
  facts = facts.map((f) => ({ ...f, evidence_count: evidence.filter((e) => e.fact_id === f.id).length }));
};
syncEvidenceCounts();

function page<T>(items: T[], limit = 50, offset = 0): Page<T> {
  return { items: clone(items.slice(offset, offset + limit)), total: items.length, limit, offset };
}
const summary = (j: JobRead): JobSummary => {
  const { id, title, company, location, employment_type, work_mode, language, published_on, deadline_on, first_seen_at, status, hidden, canonical_url, sources, possible_duplicate_of, available_from_finland, match_score, match_has_blockers, apply_manually } = j;
  return { id, title, company, location, employment_type, work_mode, language, published_on, deadline_on, first_seen_at, status, hidden, canonical_url, sources, possible_duplicate_of, available_from_finland, match_score, match_has_blockers, apply_manually, archived: j.archived ?? false };
};
const requireProfile = () => {
  if (!profile) throw new ApiError(404, "profile_not_found", "No profile has been created yet.");
  return profile;
};
const checkLen = (field: string, v: unknown, max: number) => {
  if (typeof v !== "string" || v.trim().length < 1) throw validation(field, "This field is required.");
  if (v.length > max) throw validation(field, `Must be at most ${max} characters.`);
};
const isHttp = (v: string) => /^https?:\/\/[^\s]+\.[^\s]+/i.test(v);

let backups: BackupRead[] = [{ name: "duuniscript-sample-backup.zip", size_bytes: 248_000, created_at: isoDaysAgo(0.2) }];
let backupRunning = false;
const backupsStatus = (): BackupsStatus => ({ interval_hours: 24, keep: 7, backups: clone(backups) });
const openJob = (j: JobRead) => !["applied", "closed", "expired", "not_relevant"].includes(j.status);
const dashboardJob = (j: JobRead): DashboardJob => ({ id: j.id, title: j.title, company: j.company, location: j.location, deadline_on: j.deadline_on, status: j.status, match_score: j.match_score, apply_manually: j.apply_manually });
function dashboardSummary(): DashboardSummary {
  const open = jobs.filter(openJob);
  const weekAgo = Date.now() - 7 * 86400000;
  const today = daysFromNow(0), weekAhead = daysFromNow(7);
  const checks = sources.map((s) => s.last_success_at).filter((v): v is string => !!v).sort();
  return {
    counts: {
      jobs: jobs.length,
      jobs_new_this_week: jobs.filter((j) => new Date(j.first_seen_at).getTime() >= weekAgo).length,
      jobs_saved: jobs.filter((j) => j.status === "saved").length,
      jobs_good_match: jobs.filter((j) => j.match_score !== null && j.match_score >= 60 && !j.match_has_blockers).length,
      applications_drafting: apps.filter((a) => a.status === "draft").length,
      applications_ready: apps.filter((a) => a.status === "ready").length,
      applications_sent: apps.filter((a) => a.status === "submitted").length,
      interviews: apps.filter((a) => a.outcome === "interview").length,
      offers: apps.filter((a) => a.outcome === "offer" || a.outcome === "accepted").length,
    },
    deadlines_soon: clone(open.filter((j) => j.deadline_on && j.deadline_on >= today && j.deadline_on <= weekAhead).sort((a, b) => a.deadline_on!.localeCompare(b.deadline_on!)).map(dashboardJob)),
    best_matches: clone(open.filter((j) => j.match_score !== null && !j.match_has_blockers).sort((a, b) => b.match_score! - a.match_score!).slice(0, 5).map(dashboardJob)),
    status: {
      last_source_check_at: checks.at(-1) ?? null,
      sources_turned_off: sources.filter((s) => !s.enabled).map((s) => s.name),
      sources_failing: feedsStatus.feeds.filter((f) => f.last_error).map((f) => f.name),
      last_backup_at: backups[0]?.created_at ?? null,
      automatic_backups: backupsStatus().interval_hours > 0,
    },
  };
}
function jobMatch(j: JobRead): JobMatchRead {
  const score = j.match_score;
  const skills = score === null ? 0 : Math.min(60, Math.round(score * 0.6));
  const role = score === null ? 0 : Math.min(25, Math.round(score * 0.25));
  return {
    job_id: j.id, score, scoring_version: "sample-match-1",
    reasons: score === null ? [] : ["Your verified facts overlap with the role's sample requirements.", "The role wording resembles your verified sample experience."],
    matched_skills: score === null ? [] : ["TypeScript", "React"],
    missing_terms: score === null ? [] : ["Kubernetes"],
    blockers: !j.match_has_blockers ? [] : [{ code: j.available_from_finland === "no" ? "not_open_to_finland" : "language_required", message: j.available_from_finland === "no" ? "This sample job is not open to people working from Finland." : "The sample posting names a language requirement not covered by your verified facts." }],
    parts: { skills, role, wording: score === null ? 0 : Math.max(0, score - skills - role), semantic: score === null ? null : 12, learned: score === null ? 0 : 2 },
    computed_at: now(),
  };
}

const cvProfiles: CvProfileRead[] = [{ id: "sample-profile", name: "Sample technical CV", focus: "TypeScript", summary: "Fictional profile text only.", cv_template: "utu_rekry" }];
const savedAnswers = new Map<string, string>();
const screenshotDrafts = new Map<string, File[]>();
const jobAttachments = new Map<string, File[]>();
const baseMock: ApiService = {
  async getFormAnswers(id) {
    await wait(); findApp(id);
    const questions = [["availability", "When can you start?"], ["salary", "What is your salary expectation?"], ["notice_period", "What is your notice period?"], ["references", "Who are your references?"], ["relocation", "Are you willing to relocate?"], ["why_us", "Why this employer?"]];
    return questions.map(([key = "", question = ""]): FormAnswerRead => {
      const answer = savedAnswers.get(key === "why_us" ? `why_us:${id}` : key);
      return { key, question, answer: answer ?? "", source: answer !== undefined ? "saved" : "none", needs_input: answer === undefined, hint: "Write your own answer", fact_ids: [] };
    });
  },
  async saveFormAnswer(key, body) { await wait(); savedAnswers.set(key, body.answer); },
  async aiWriteLetter(id) {
    await wait(900); editable(findApp(id));
    const verified = facts.filter((f) => f.verification_status === "verified");
    return { suggestion: "Sample AI fit paragraphs — fictional data only.\n" + verified.map((f) => `${f.subject}: ${f.value_text}`).join("\n"), issues: [], fact_ids: verified.map((f) => f.id) };
  },
  async listCvProfiles() { await wait(); return clone(cvProfiles); },
  async createCvProfile(body) { await wait(); checkLen("name", body.name, 300); const item = { id: uid(), ...body }; cvProfiles.push(item); return clone(item); },
  async updateCvProfile(id, body) { await wait(); const item = cvProfiles.find((p) => p.id === id); if (!item) throw notFound("cv_profile_not_found", "CV profile"); checkLen("name", body.name, 300); Object.assign(item, body); return clone(item); },
  async deleteCvProfile(id) { await wait(); const index = cvProfiles.findIndex((p) => p.id === id); if (index < 0) throw notFound("cv_profile_not_found", "CV profile"); cvProfiles.splice(index, 1); },
  async getOutcomeStats() {
    await wait();
    const sent = apps.filter((a) => a.submitted_at);
    const counts = (items: ApplicationRead[]) => {
      const responses = items.filter((a) => a.outcome && a.outcome !== "no_response").length;
      return { sent: items.length, responses, interviews: items.filter((a) => a.outcome === "interview").length, offers: items.filter((a) => a.outcome === "offer" || a.outcome === "accepted").length, response_rate: items.length ? responses / items.length : 0 };
    };
    const group = (keyOf: (a: ApplicationRead) => string) => [...new Set(sent.map(keyOf))].map((key) => ({ key, ...counts(sent.filter((a) => keyOf(a) === key)) }));
    const c = counts(sent);
    const weekOf = (a: ApplicationRead) => { const d = new Date(a.submitted_at ?? a.created_at); d.setUTCDate(d.getUTCDate() - (d.getUTCDay() + 6) % 7); return d.toISOString().slice(0, 10); };
    const replies = sent.filter((a) => a.outcome_on && a.outcome && a.outcome !== "no_response").map((a) => Math.max(0, (Date.parse(a.outcome_on ?? "") - Date.parse((a.submitted_at ?? "").slice(0, 10))) / 86400000)).sort((a,b) => a-b);
    const middle = Math.floor(replies.length / 2);
    return { ...c, interview_rate: c.sent ? c.interviews / c.sent : 0, median_days_to_reply: replies.length ? ((replies[middle] ?? 0) + (replies[Math.floor((replies.length - 1) / 2)] ?? 0)) / 2 : null,
      by_source: group((a) => jobs.find((j) => j.id === a.job.id)?.sources[0] ?? "manual"), by_role: group((a) => a.job.title.split(" ")[0] ?? "sample"), sent_per_week: group(weekOf).map((g) => ({ week: g.key, sent: g.sent })).sort((a,b) => a.week.localeCompare(b.week)) };
  },
  async readJobText(body) { await wait(700); if (!body.text.trim()) throw validation("text", "Paste the posting text."); return { fields: { title: "Pasted Role (sample)", company: "Example Text Company", description: body.text, added_from: "text", apply_manually: true }, text: body.text, method: "ai", warnings: ["Sample fields only: check every field against your posting."], images: 0 }; },
  async listJobAttachments(id) { await wait(); return (jobAttachments.get(id) ?? []).map((file, index) => ({ id: String(index), filename: file.name })); },
  async downloadJobAttachment(id, attachmentId) { await wait(); const file = jobAttachments.get(id)?.[Number(attachmentId)]; if (!file) throw notFound("attachment_not_found", "Screenshot"); return { blob: file, filename: file.name }; },
  async housekeepingJobs() { await wait(); let expired = 0, archived = 0; for (const j of jobs) { if (openJob(j) && j.deadline_on && j.deadline_on < daysFromNow(0)) { j.status = "expired"; expired++; } if (j.status === "expired" && !j.archived) { j.archived = true; archived++; } } return { expired, archived }; },
  async health() {
    await wait(120);
    return { status: "ok", version: "0.1.0-sample", database: "ok" };
  },

  async listJobs(p = {}) {
    await wait();
    let list = jobs.filter((j) => p.include_archived || !j.archived);
    if (p.hidden) list = list.filter((j) => j.hidden);
    else if (!p.include_hidden) list = list.filter((j) => !j.hidden);
    const has = (v: string | null, q?: string) => !q || (v ?? "").toLowerCase().includes(q.toLowerCase());
    if (p.q) list = list.filter((j) => has(j.title, p.q) || has(j.company, p.q) || has(j.description, p.q));
    list = list.filter((j) => has(j.company, p.company) && has(j.location, p.location));
    if (p.source) list = list.filter((j) => j.sources.includes(p.source!));
    if (p.status?.length) list = list.filter((j) => p.status!.includes(j.status));
    if (p.employment_type) list = list.filter((j) => j.employment_type === p.employment_type);
    if (p.work_mode) list = list.filter((j) => j.work_mode === p.work_mode);
    if (p.available_from_finland?.length) list = list.filter((j) => p.available_from_finland?.includes(j.available_from_finland));
    if (p.min_match !== undefined) list = list.filter((j) => j.match_score !== null && j.match_score >= p.min_match!);
    if (p.language) list = list.filter((j) => p.language === "unknown" ? j.language === null : j.language?.split("-")[0]?.toLowerCase() === p.language);
    const inRange = (v: string | null, from?: string, to?: string) =>
      (!from && !to) || (v != null && (!from || v >= from) && (!to || v <= to));
    list = list.filter((j) => inRange(j.published_on, p.published_from, p.published_to) && inRange(j.deadline_on, p.deadline_from, p.deadline_to));
    const sort = p.sort ?? "newest";
    const nullLast = (a: string | null, b: string | null, dir: 1 | -1) => (a === b ? 0 : a == null ? 1 : b == null ? -1 : a < b ? -dir : dir);
    list.sort((a, b) =>
      sort === "published" ? nullLast(a.published_on, b.published_on, -1)
      : sort === "deadline" ? nullLast(a.deadline_on, b.deadline_on, 1)
      : sort === "company" ? a.company.localeCompare(b.company)
      : sort === "title" ? a.title.localeCompare(b.title)
      : sort === "match" ? (a.match_score === b.match_score ? b.first_seen_at.localeCompare(a.first_seen_at) : a.match_score === null ? 1 : b.match_score === null ? -1 : b.match_score - a.match_score)
      : b.first_seen_at.localeCompare(a.first_seen_at));
    return page(list.map(summary), p.limit ?? 50, p.offset ?? 0);
  },

  async getJob(id) {
    await wait();
    const j = jobs.find((x) => x.id === id);
    if (!j) throw notFound("job_not_found", "The job");
    return clone(j);
  },
  async getJobMatch(id) {
    await wait();
    const j = jobs.find((x) => x.id === id);
    if (!j) throw notFound("job_not_found", "The job");
    return jobMatch(j);
  },
  async getDashboard() { await wait(); return dashboardSummary(); },
  async getBackups() { await wait(); return backupsStatus(); },
  async createBackup() {
    if (backupRunning) throw new ApiError(409, "backup_in_progress", "A backup is already being made.");
    backupRunning = true;
    try {
      await wait(800);
      const created_at = now();
      const backup = { name: `duuniscript-sample-${created_at.replace(/[:.]/g, "-")}.zip`, size_bytes: 250_000 + backups.length * 1000, created_at };
      backups = [backup, ...backups].slice(0, backupsStatus().keep);
      return clone(backup);
    } finally { backupRunning = false; }
  },
  async downloadBackup(name) {
    await wait(300);
    if (!backups.some((b) => b.name === name)) throw notFound("backup_not_found", "The backup");
    return { blob: new Blob(["Sample backup placeholder, not a real backup."], { type: "application/zip" }), filename: name };
  },
  async deleteBackup(name, confirm) {
    await wait(300);
    if (!confirm) throw new ApiError(409, "confirmation_required", "Deleting a backup needs confirmation.");
    if (!backups.some((b) => b.name === name)) throw notFound("backup_not_found", "The backup");
    backups = backups.filter((b) => b.name !== name);
  },

  async readJobScreenshots(files) {
    await wait(900);
    if (files.length > 10) throw new ApiError(422, "too_many_files", "Choose up to 10 screenshots of one posting.");
    if (!files.length) throw validation("files", "Choose at least one screenshot.");
    if (files.some((f) => !["image/png", "image/jpeg"].includes(f.type))) throw new ApiError(415, "unsupported_type", "Choose PNG or JPEG screenshots.");
    const draftId = uid(); screenshotDrafts.set(draftId, files);
    return { screenshot_draft_id: draftId, fields: { title: "Screenshot Role (sample)", company: "Example Screenshot Company", description: "Synthetic screenshot text, not extracted from your images.\n<b>Plain text only.</b>", added_from: "screenshots", apply_manually: true }, text: "Synthetic screenshot text, not extracted from your images.\n<b>Plain text only.</b>", method: "ai", warnings: ["Sample data only: check every field against your posting."], images: files.length };
  },
  async createJob(body) {
    await wait(400);
    checkLen("title", body.title, 300);
    checkLen("company", body.company, 300);
    if (body.url && !isHttp(body.url)) throw validation("url", "Enter a valid http(s) URL.");
    if (body.application_url && !isHttp(body.application_url)) throw validation("application_url", "Enter a valid http(s) URL.");
    if (body.url) {
      const dup = jobs.find((j) => j.canonical_url === body.url);
      if (dup) throw new ApiError(409, "duplicate_job", "This job is already in your list.", { job_id: dup.id });
    }
    const { url, ...rest } = body;
    const j = makeJob({ ...rest, title: body.title, company: body.company, canonical_url: url ?? null, first_seen_at: now() }, body.added_from === "screenshots" ? "screenshot_import" : "manual");
    const listing = j.listings[0];
    if (listing) listing.source_url = url ?? null;
    const like = jobs.find((x) => x.title.toLowerCase() === j.title.toLowerCase() && x.company.toLowerCase() === j.company.toLowerCase());
    if (like) j.possible_duplicate_of = like.id;
    if (body.screenshot_draft_id) { jobAttachments.set(j.id, screenshotDrafts.get(body.screenshot_draft_id) ?? []); screenshotDrafts.delete(body.screenshot_draft_id); }
    jobs.unshift(j);
    return clone(j);
  },

  async importJob({ url }) {
    await wait(1600);
    const u = url.trim();
    if (!isHttp(u)) throw new ApiError(422, "invalid_url", "Enter a full web address starting with http:// or https://.", {});
    const f = (status: number, reason: string, message: string) => new ApiError(status, "fetch_failed", message, { reason });
    if (u.includes("duplicate") || jobs.some((j) => j.canonical_url === u)) {
      const target = jobs.find((j) => j.canonical_url === u) ?? jobs[0]!;
      throw new ApiError(409, "duplicate_job", "This job is already in your list.", { job_id: target.id });
    }
    if (u.includes("existing")) {
      const target = jobs[0]!;
      const seen = now();
      target.listings.push({ source_key: "example_board", source_name: sourceName("example_board"), source_url: u, external_id: null, source_published_on: null, first_seen_at: seen, last_seen_at: seen, listing_status: "active", captured_at: seen, parser_version: "jsonld-1.2.0" });
      if (!target.sources.includes("example_board")) target.sources.push("example_board");
      return { job: clone(target), created: false };
    }
    if (u.includes("nodata")) throw new ApiError(422, "no_structured_job_data", "The page doesn't publish job details in a format DuuniScript can read.");
    if (u.includes("robots")) throw f(422, "robots_disallowed", "The site asks automated tools not to open this page.");
    if (u.includes("blocked")) throw f(422, "blocked_address", "This address points to a private or local network and was not opened.");
    if (u.includes("pdf")) throw f(422, "not_html", "The link doesn't point to a web page.");
    if (u.includes("dns")) throw f(502, "dns_failed", "The site's address couldn't be found.");
    if (u.includes("http-status")) throw f(502, "http_status", "The sample site returned an error instead of the job page.");
    if (u.includes("timeout")) throw f(504, "timeout", "The site took too long to respond.");
    if (u.includes("disabled")) throw new ApiError(403, "url_import_disabled", "Importing by link is turned off in the backend settings.");
    const j = makeJob({ title: "Imported Role (sample)", company: "Esimerkki Import Oy", location: "Helsinki", canonical_url: u, description: "Sample description imported from structured data.", published_on: daysFromNow(-1), first_seen_at: now() }, "example_board");
    j.listings[0]!.source_url = u;
    jobs.unshift(j);
    return { job: clone(j), created: true };
  },

  async mergeJob(id, intoJobId) {
    await wait(400);
    const from = jobs.find((x) => x.id === id);
    const into = jobs.find((x) => x.id === intoJobId);
    if (!from || !into) throw notFound("job_not_found", "The job");
    into.listings.push(...from.listings);
    into.sources = [...new Set([...into.sources, ...from.sources])];
    into.description ??= from.description;
    if (from.user_notes) into.user_notes = into.user_notes ? `${into.user_notes}\n\n${from.user_notes}` : from.user_notes;
    into.updated_at = now();
    jobs = jobs.filter((x) => x.id !== id).map((x) => (x.possible_duplicate_of === id ? { ...x, possible_duplicate_of: null } : x));
    return clone(into);
  },

  async getJobAlerts() {
    await wait();
    return clone(alertStatus);
  },
  async syncJobAlerts() {
    if (!alertStatus.configured) throw new ApiError(409, "mailbox_not_configured", "The job alert mailbox is not set up yet.");
    if (syncing) throw new ApiError(409, "sync_in_progress", "A check is already running. Try again in a moment.");
    syncing = true;
    try {
      await wait(1200);
      alertStatus = { ...alertStatus, last_sync_at: now() };
      return { ...emptySync(), emails_checked: 2, emails_already_read: 2 };
    } finally { syncing = false; }
  },
  async uploadAlertEmails(files) {
    await wait(800);
    if (files.length > 50) throw validation("files", "Add at most 50 emails at a time.");
    const r = emptySync();
    r.emails_checked = files.length;
    r.emails_not_alerts = files.length;
    return r;
  },

  async updateJob(id, body) {
    await wait(300);
    const i = jobs.findIndex((x) => x.id === id);
    if (i < 0) throw notFound("job_not_found", "The job");
    if ("title" in body) checkLen("title", body.title, 300);
    if ("company" in body) checkLen("company", body.company, 300);
    if (body.application_url && !isHttp(body.application_url)) throw validation("application_url", "Enter a valid http(s) URL.");
    jobs[i] = { ...jobs[i]!, ...(body as Partial<JobRead>), updated_at: now() };
    return clone(jobs[i]!);
  },

  async listSources() {
    await wait();
    return clone(sources);
  },

  async getFeeds() { await wait(); return clone(feedsStatus); },
  async syncFeed(key) { return runFeed(key); },
  async syncFeeds() {
    const due = feedsStatus.feeds.filter((f) => f.enabled && (!f.next_allowed_at || new Date(f.next_allowed_at).getTime() <= Date.now()));
    return Promise.all(due.map(async (f) => {
      try { return await runFeed(f.key); }
      catch (e) { return { key: f.key, name: f.name, jobs_found: 0, jobs_created: 0, jobs_merged: 0, jobs_already_known: 0, possible_duplicates: 0, skipped_not_available: 0, skipped_keywords: 0, error: e instanceof Error ? e.message : "The sample feed could not be checked." }; }
    }));
  },
  async updateSource(key, body) {
    await wait();
    const source = sources.find((s) => s.key === key);
    if (!source) throw notFound("source_not_found", "The source");
    source.enabled = body.enabled;
    const feed = feedsStatus.feeds.find((f) => f.key === key);
    if (feed) feed.enabled = body.enabled;
    return clone(source);
  },

  async getProfile() {
    await wait();
    return clone(requireProfile());
  },
  async putProfile(body) {
    await wait(300);
    checkLen("display_name", body.display_name, 200);
    if (body.email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(body.email)) throw validation("email", "Enter a valid email address.");
    const t = now();
    profile = { id: profile?.id ?? uid(), created_at: profile?.created_at ?? t, updated_at: t, display_name: body.display_name, email: body.email ?? null, phone: body.phone ?? null, location: body.location ?? null, professional_summary: body.professional_summary ?? null };
    return clone(profile);
  },
  async deleteProfile(confirm) {
    await wait(300);
    requireProfile();
    if (!confirm) throw new ApiError(409, "confirmation_required", "Deleting the profile needs confirmation.", { facts: facts.length, evidence: evidence.length, documents: documents.length });
    const r = { deleted: true, deleted_facts: facts.length, deleted_evidence: evidence.length, deleted_documents: documents.length };
    profile = null; facts = []; evidence = []; documents = [];
    return r;
  },

  async listFacts(p = {}) {
    await wait();
    requireProfile();
    let l = facts.slice();
    if (p.category) l = l.filter((f) => f.category === p.category);
    if (p.verification_status) l = l.filter((f) => f.verification_status === p.verification_status);
    return page(l, p.limit ?? 200, p.offset ?? 0);
  },
  async getFact(id) {
    await wait();
    const f = facts.find((x) => x.id === id);
    if (!f) throw notFound("fact_not_found", "The fact");
    return clone(f);
  },
  async createFact(body) {
    await wait(300);
    const pr = requireProfile();
    checkLen("subject", body.subject, 300);
    checkLen("value_text", body.value_text, 5000);
    if (body.valid_from && body.valid_until && body.valid_from > body.valid_until)
      throw new ApiError(422, "invalid_date_range", "The end date must be on or after the start date.");
    const f = mkFact({ ...body, profile_id: pr.id, created_at: now(), updated_at: now() });
    facts.push(f);
    return clone(f);
  },
  async updateFact(id, body) {
    await wait(300);
    const i = facts.findIndex((x) => x.id === id);
    if (i < 0) throw notFound("fact_not_found", "The fact");
    const cur = facts[i]!;
    const next = { ...cur, ...(body as Partial<FactRead>), updated_at: now() };
    if (next.valid_from && next.valid_until && next.valid_from > next.valid_until)
      throw new ApiError(422, "invalid_date_range", "The end date must be on or after the start date.");
    const contentChanged = (["category", "subject", "value_text", "valid_from", "valid_until"] as const).some((k) => k in body && body[k] !== cur[k]);
    if (body.verification_status) next.verified_at = body.verification_status === "verified" ? now() : null;
    else if (contentChanged && cur.verification_status === "verified") { next.verification_status = "unverified"; next.verified_at = null; }
    facts[i] = next;
    return clone(next);
  },
  async deleteFact(id) {
    await wait(300);
    if (!facts.some((f) => f.id === id)) throw notFound("fact_not_found", "The fact");
    facts = facts.filter((f) => f.id !== id);
    evidence = evidence.filter((e) => e.fact_id !== id);
  },
  async listEvidence(factId) {
    await wait();
    if (!facts.some((f) => f.id === factId)) throw notFound("fact_not_found", "The fact");
    return clone(evidence.filter((e) => e.fact_id === factId));
  },
  async createEvidence(factId, body) {
    await wait(300);
    if (!facts.some((f) => f.id === factId)) throw notFound("fact_not_found", "The fact");
    if (body.source_type === "document") {
      if (!body.document_id) throw validation("document_id", "Choose a document.");
      const d = documents.find((x) => x.id === body.document_id);
      if (!d) throw notFound("document_not_found", "The document");
      if (d.archived_at) throw new ApiError(422, "document_archived", "Archived documents can't be used as new evidence.");
    }
    if (body.source_type === "url" && !(body.source_reference && isHttp(body.source_reference)))
      throw validation("source_reference", "Enter a valid http(s) URL.");
    if (body.excerpt && body.excerpt.length > 2000) throw validation("excerpt", "Must be at most 2000 characters.");
    const e: EvidenceRead = { id: uid(), fact_id: factId, document_id: body.document_id ?? null, source_type: body.source_type, source_reference: body.source_reference ?? null, excerpt: body.excerpt ?? null, verification_status: "unverified", created_at: now() };
    evidence.push(e);
    syncEvidenceCounts();
    return clone(e);
  },

  async listDocuments(p = {}) {
    await wait();
    let l = documents.slice();
    if (!p.include_archived) l = l.filter((d) => !d.archived_at);
    if (p.category) l = l.filter((d) => d.category === p.category);
    return page(l, p.limit ?? 50, p.offset ?? 0);
  },
  async getDocument(id) {
    await wait();
    const d = documents.find((x) => x.id === id);
    if (!d) throw notFound("document_not_found", "The document");
    return clone(d);
  },
  async uploadDocument({ file, category, display_name }) {
    await wait(900);
    const ext = (file.name.split(".").pop() ?? "").toLowerCase();
    if (!["pdf", "docx", "txt", "md", "html", "htm", "png", "jpg", "jpeg"].includes(ext)) throw new ApiError(415, "unsupported_file_type", "This file type isn't supported. Use PDF, Word (.docx), text, Markdown, a saved web page (.html), or a photo or scan (.png, .jpg).");
    if (file.size > 20 * 1024 * 1024) throw new ApiError(413, "file_too_large", "The file is larger than 20 MB.");
    if (file.size === 0) throw new ApiError(422, "empty_file", "The file is empty.");
    const dup = documents.find((d) => d.original_filename === file.name && d.size_bytes === file.size);
    if (dup) throw new ApiError(409, "duplicate_document", "This file has already been uploaded.", { document_id: dup.id });
    const isText = ext === "txt" || ext === "md";
    const text = isText ? await file.text() : "Sample extracted text for an uploaded file (sample data mode).";
    const d = mkDoc({ display_name: display_name || file.name.replace(/\.[^.]+$/, ""), original_filename: file.name, category, size_bytes: file.size, extracted_char_count: text.length, extraction_method: ["png", "jpg", "jpeg"].includes(ext) ? "ocr" : "text", created_at: now(), updated_at: now(), extracted_at: now() });
    documents.unshift(d);
    docTexts[d.id] = text;
    return clone(d);
  },
  async updateDocument(id, body) {
    await wait(300);
    const i = documents.findIndex((x) => x.id === id);
    if (i < 0) throw notFound("document_not_found", "The document");
    if (body.display_name !== undefined && body.display_name !== null) checkLen("display_name", body.display_name, 200);
    const d = { ...documents[i]!, updated_at: now() };
    if (body.display_name) d.display_name = body.display_name;
    if (body.category) d.category = body.category;
    if (body.archived === true) d.archived_at = now();
    if (body.archived === false) d.archived_at = null;
    documents[i] = d;
    return clone(d);
  },
  async deleteDocument(id) {
    await wait(300);
    if (!documents.some((d) => d.id === id)) throw notFound("document_not_found", "The document");
    if (evidence.some((e) => e.document_id === id)) throw new ApiError(409, "document_in_use", "Profile evidence uses this document.");
    documents = documents.filter((d) => d.id !== id);
  },
  async getDocumentText(id) {
    await wait();
    const d = documents.find((x) => x.id === id);
    if (!d) throw notFound("document_not_found", "The document");
    return { document_id: id, extraction_status: d.extraction_status, extraction_error: d.extraction_error, extractor_version: d.extractor_version, text: d.extraction_status === "succeeded" ? docTexts[id] ?? "Sample extracted text." : null };
  },
  async extractDocument(id) {
    await wait(1000);
    const i = documents.findIndex((x) => x.id === id);
    if (i < 0) throw notFound("document_not_found", "The document");
    // Simulate: protected files still fail; others succeed.
    if (documents[i]!.extraction_error !== "encrypted") {
      const image = ["png", "jpg", "jpeg"].includes(documents[i]!.file_extension);
      documents[i] = { ...documents[i]!, extraction_status: "succeeded", extraction_error: null, extracted_char_count: 1200, extracted_at: now(), extraction_method: image ? "ocr" : "text" };
    }
    return clone(documents[i]!);
  },
  documentContentUrl: () => null,
  async downloadDocument() { throw new ApiError(404, "not_available", "Downloads are not available with sample data."); },

  async getFactSuggestions(id) {
    await wait(500);
    const d = documents.find((x) => x.id === id);
    if (!d) throw notFound("document_not_found", "The document");
    if (d.extraction_status !== "succeeded") throw new ApiError(409, "no_extracted_text", "This document has no extracted text to read facts from.");
    const has = (subject: string) => facts.some((f) => f.subject.toLowerCase() === subject.toLowerCase());
    const mk = (category: FactSuggestion["category"], subject: string, value_text: string, excerpt: string, valid_from: string | null = null, valid_until: string | null = null): FactSuggestion =>
      ({ category, subject, value_text, excerpt, valid_from, valid_until, already_in_profile: has(subject) });
    return {
      document_id: id, parser_version: "cv-rules-0.1 (sample)", items: [
        mk("contact", "Email", "test.person@example.com", "test.person@example.com"),
        mk("education", "MSc, Example University", "Master of Science in Sample Studies", "MSc, Example University (2018–2020)", "2018-09-01", "2020-06-15"),
        mk("work_experience", "Developer at Esimerkki Oy", "Built sample internal tools.", "Developer, Esimerkki Oy (2020–)", "2020-08-01"),
        mk("skill", "React", "Sample skill read from the CV.", "SKILLS\nTypeScript, React, sample skill"),
        mk("language", "English", "Fluent (sample)", "English – fluent"),
      ],
    };
  },
  async importFacts(body) {
    await wait(400);
    const prof = requireProfile();
    let created = 0, skipped = 0; const out: FactRead[] = [];
    for (const it of body.items) {
      if (facts.some((f) => f.subject.toLowerCase() === it.subject.toLowerCase() && f.category === it.category)) { skipped++; continue; }
      const f = mkFact({ profile_id: prof.id, category: it.category, subject: it.subject, value_text: it.value_text, valid_from: it.valid_from ?? null, valid_until: it.valid_until ?? null, created_at: now(), updated_at: now() });
      facts.push(f); out.push(f); created++;
      if (it.excerpt) evidence.push({ id: uid(), fact_id: f.id, document_id: body.document_id, source_type: "document", source_reference: null, excerpt: it.excerpt, verification_status: "unverified", created_at: now() });
    }
    syncEvidenceCounts();
    return { created, skipped_existing: skipped, facts: clone(facts.filter((f) => out.some((o) => o.id === f.id))) };
  },
  async verifyFacts(ids) {
    await wait(300);
    requireProfile();
    let n = 0;
    facts = facts.map((f) => (ids.includes(f.id) && f.verification_status !== "verified" ? (n++, { ...f, verification_status: "verified" as const, verified_at: now(), updated_at: now() }) : f));
    return { verified: n, facts: clone(facts.filter((f) => ids.includes(f.id))) };
  },
  async listTemplates() { await wait(); return clone(templates); },
  async listApplications(p = {}) {
    await wait();
    let items = apps.filter((a) => (!p.status || a.status === p.status) && (!p.job_id || a.job.id === p.job_id));
    items = [...items].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    return page(items.map(appSummary), p.limit ?? 50, p.offset ?? 0);
  },
  async getApplication(id) { await wait(); return clone(findApp(id)); },
  async createApplication(body) {
    await wait(600);
    const job = jobs.find((j) => j.id === body.job_id);
    if (!job) throw notFound("job_not_found", "The job");
    const open = apps.find((a) => a.job.id === job.id && (a.status === "draft" || a.status === "ready"));
    if (open) throw new ApiError(409, "application_exists", "There is already an open application for this job.", { application_id: open.id });
    const verified = facts.filter((f) => f.verification_status === "verified");
    const needsFacts = (body.cv_source ?? "generated") === "generated" || (body.include_cover_letter ?? true);
    if (needsFacts && verified.length === 0) throw new ApiError(409, "no_verified_facts", "You have no verified facts yet. Verify some facts on your profile first.");
    const t = now();
    let cv: DraftRead;
    if (body.cv_source === "uploaded") {
      const d = documents.find((x) => x.id === body.cv_document_id && !x.archived_at);
      if (!d) throw notFound("document_not_found", "The document");
      cv = uploadedDraft(d.id, d.display_name, 1);
    } else cv = generatedDraft("cv", body.cv_template || (job.language?.split("-")[0] === "fi" ? "utu_rekry_fi" : "utu_rekry"), 1);
    const a: ApplicationRead = {
      id: uid(), job: { id: job.id, title: job.title, company: job.company, location: job.location, deadline_on: job.deadline_on, status: job.status },
      status: "draft", include_cover_letter: body.include_cover_letter ?? true, submission_method: null, outcome: null, outcome_on: null, ready_at: null, submitted_at: null,
      withdrawn_at: null, created_at: t, updated_at: t, destination: job.application_url ?? job.canonical_url, contact_emails: ["jobs@example.com"],
      cv_profile_id: body.cv_profile_id ?? (body.auto_profile ? cvProfiles[0]?.id ?? null : null),
      package_hash: null, confirmation_reference: null, notes: null, cv,
      cover_letter: generatedDraft("cover_letter", body.letter_template || (job.language?.split("-")[0] === "fi" ? "utu_rekry_fi" : "utu_rekry"), 1),
    };
    apps.unshift(a); addEvent(a.id, "created");
    return clone(a);
  },
  async updateApplication(id, body) {
    await wait();
    const a = findApp(id); editable(a);
    if (body.include_cover_letter !== undefined) a.include_cover_letter = body.include_cover_letter;
    if (body.notes !== undefined) a.notes = body.notes;
    recomputeReady(a);
    return clone(a);
  },
  async deleteApplication(id) {
    await wait();
    const a = findApp(id);
    if (a.submitted_at) throw new ApiError(409, "application_submitted", "Applications that were recorded as sent can't be deleted.");
    apps = apps.filter((x) => x.id !== id);
  },
  async saveDraft(id, kind, body) {
    await wait(300);
    const a = findApp(id); editable(a);
    const cur = a[kind];
    const v = (cur?.version ?? 0) + (cur?.status === "approved" || !cur ? 1 : 0);
    let next: DraftRead;
    if (body.source === "uploaded") {
      if (kind !== "cv") throw validation("source", "Only a CV can be an uploaded file.");
      const d = documents.find((x) => x.id === body.document_id);
      if (!d) throw notFound("document_not_found", "The document");
      if (d.archived_at) throw new ApiError(422, "document_archived", "Archived documents can't be used.");
      next = uploadedDraft(d.id, d.display_name, v);
    } else {
      next = { ...(cur?.source === "generated" ? cur : generatedDraft(kind, kind === "cv" ? "classic" : "standard", v)), version: v, content: body.content ?? "", status: "draft", approved_at: null, updated_at: now() };
      next.issues = checkContent(kind, next.content ?? "");
    }
    if (cur?.status === "approved") addEvent(a.id, "reopened", { kind });
    a[kind] = next; recomputeReady(a);
    return clone(next);
  },
  async regenerateDraft(id, kind, body) {
    await wait(500);
    const a = findApp(id); editable(a);
    if (!facts.some((f) => f.verification_status === "verified")) throw new ApiError(409, "no_verified_facts", "You have no verified facts yet.");
    const cur = a[kind];
    if (cur?.status === "approved") addEvent(a.id, "reopened", { kind });
    a[kind] = generatedDraft(kind, body.template ?? cur?.template ?? (kind === "cv" ? "classic" : "standard"), (cur?.version ?? 0) + 1);
    recomputeReady(a);
    return clone(a[kind]!);
  },
  async approveDraft(id, kind, body) {
    await wait(300);
    const a = findApp(id); editable(a);
    const d = a[kind];
    if (!d) throw notFound("draft_not_found", "The draft");
    const issues = d.issues ?? [];
    const errors = issues.filter((i) => i.severity === "error");
    if (errors.length) throw new ApiError(422, "draft_has_errors", "Fix the problems marked as errors before approving.", { issues: errors });
    const warnings = issues.filter((i) => i.severity === "warning");
    if (warnings.length && !body.acknowledge_warnings) throw new ApiError(409, "warnings_not_acknowledged", "Confirm that you checked the warnings before approving.", { issues: warnings });
    a[kind] = { ...d, status: "approved", approved_at: now(), updated_at: now() };
    addEvent(a.id, kind === "cv" ? "cv_approved" : "cover_letter_approved", { version: d.version });
    recomputeReady(a);
    return clone(a[kind]!);
  },
  async exportDraft(id, kind, format) {
    await wait(300);
    const d = findApp(id)[kind];
    if (!d) throw notFound("draft_not_found", "The draft");
    return { blob: new Blob([d.content ?? "Sample uploaded file."], { type: "text/plain" }), filename: `sample_${kind}_v${d.version}.${format === "pdf" || format === "docx" ? "txt" : format}` };
  },
  async getPackage(id) { await wait(); return pkg(findApp(id)); },
  async downloadPackageZip(id) {
    await wait(300); findApp(id);
    return { blob: new Blob(["Sample package (not a real zip)."], { type: "text/plain" }), filename: "sample_application_package.txt" };
  },
  async downloadEmailDraft(id) {
    await wait(300);
    const p = pkg(findApp(id));
    return { blob: new Blob([`X-Unsent: 1\r\nTo: ${p.contact_emails.join(", ")}\r\nSubject: Application: ${p.role}\r\n\r\n${p.cover_letter_text ?? ""}`], { type: "message/rfc822" }), filename: "sample_application.eml" };
  },
  async recordSubmission(id, body) {
    await wait(400);
    const a = findApp(id);
    if (a.status !== "ready") throw new ApiError(409, "not_ready", "Approve the documents before recording the application as sent.");
    if (!body.confirm) throw validation("confirm", "Confirm that you sent these files.");
    if (body.package_hash !== a.package_hash) throw new ApiError(409, "package_changed", "The documents changed after you reviewed them.");
    const t = now();
    Object.assign(a, { status: "submitted", submitted_at: t, updated_at: t, submission_method: body.method, confirmation_reference: body.confirmation_reference ?? null });
    addEvent(a.id, "submitted_by_user", { method: body.method });
    const j = jobs.find((x) => x.id === a.job.id);
    if (j) { j.status = "applied"; a.job.status = "applied"; }
    return clone(a);
  },
  async withdrawApplication(id) {
    await wait();
    const a = findApp(id);
    if (a.status !== "submitted") throw new ApiError(409, "not_submitted", "Only sent applications can be withdrawn.");
    Object.assign(a, { status: "withdrawn", withdrawn_at: now(), updated_at: now() });
    addEvent(a.id, "withdrawn");
    return clone(a);
  },
  async setOutcome(id, body) {
    await wait();
    const a = findApp(id);
    if (a.status !== "submitted") throw new ApiError(409, "not_submitted", "You can record an outcome only after the application was sent.");
    a.outcome = body.outcome;
    a.outcome_on = body.outcome ? (body.outcome_on ?? daysFromNow(0)) : null;
    a.updated_at = now();
    return clone(a);
  },
  async createGmailDraft(id) {
    await wait(500);
    const a = findApp(id);
    if (!integrations.google.connected) throw new ApiError(409, "not_connected", "Gmail is not connected.");
    if (a.status !== "ready") throw new ApiError(409, "not_ready", "Approve the documents first.");
    return { draft_id: "sample-draft", open_url: "https://mail.example.com/#drafts" };
  },
  async sendEmail(id, body) {
    await wait(800);
    const a = findApp(id);
    if (!integrations.google.connected) throw new ApiError(409, "not_connected", "Gmail is not connected.");
    if (a.status !== "ready") throw new ApiError(409, "not_ready", "Approve the documents first.");
    if (body.confirm !== true) throw validation("confirm", "Confirm that you checked the email.");
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(body.to)) throw validation("to", "Enter a valid email address.");
    if (body.package_hash !== a.package_hash) throw new ApiError(409, "package_changed", "The documents changed after you reviewed them.");
    const t = now();
    Object.assign(a, { status: "submitted", submitted_at: t, updated_at: t, submission_method: "email" });
    addEvent(a.id, "submitted_by_user", { method: "email", to: body.to });
    const j = jobs.find((x) => x.id === a.job.id);
    if (j) { j.status = "applied"; a.job.status = "applied"; }
    return clone(a);
  },
  async getAi() { await wait(); return { enabled: true, model: "sample-local-model", reachable: true, message: null, embedding_model: "sample-search-model", embeddings_reachable: true, facts_indexed: facts.filter((f) => f.verification_status === "verified").length, jobs_indexed: jobs.length }; },
  async indexAi() { await wait(900); return { available: true, facts: facts.filter((f) => f.verification_status === "verified").length, jobs: jobs.length }; },
  async polishDraft(id, kind) {
    await wait(900);
    const d = findApp(id)[kind];
    if (!d || d.source !== "generated") throw new ApiError(409, "not_generated", "Only drafts built from your facts can be reworded.");
    const suggestion = (d.content ?? "").replace("I am writing to apply for", "I would like to apply for");
    return { suggestion, issues: checkContent(kind, suggestion) };
  },
  async authStatus() {
    await wait(100);
    const pw = mockPassphrase();
    return { password_set: !!pw, signed_in: !pw || getToken() === mockToken(pw) };
  },
  async setupPassword(password) {
    await wait();
    if (mockPassphrase()) throw new ApiError(409, "password_already_set", "A passphrase is already set. Change it instead.");
    if (password.length < 10) throw new ApiError(422, "password_too_short", "Use at least 10 characters.");
    setMockPassphrase(password);
    return { token: mockToken(password), expires_at: new Date(Date.now() + 12 * 3600000).toISOString() };
  },
  async login(password) {
    await wait(400);
    const pw = mockPassphrase();
    if (!pw || password !== pw) throw new ApiError(401, "wrong_password", "That passphrase is not correct.");
    return { token: mockToken(pw), expires_at: new Date(Date.now() + 12 * 3600000).toISOString() };
  },
  async logout() { await wait(100); },
  async changePassword(body) {
    await wait();
    const pw = mockPassphrase();
    if (!pw || body.current_password !== pw) throw new ApiError(401, "wrong_password", "The current passphrase is not correct.");
    if (body.new_password.length < 10) throw new ApiError(422, "password_too_short", "Use at least 10 characters.");
    setMockPassphrase(body.new_password);
    setToken(mockToken(body.new_password));
  },
  async getIntegrations() { await wait(150); return clone(integrations); },
  async connectGoogle() {
    await wait();
    // Sample only: pretend the user finishes the Google consent page after a few seconds.
    setTimeout(() => { Object.assign(integrations.google, { connected: true, account: "test.person@example.com", connected_at: now() }); }, 6000);
    return { url: "https://example.com/sample-google-consent" };
  },
  async connectMicrosoft() {
    await wait();
    msAttempts += 1;
    const fail = msAttempts === 1;
    integrations.microsoft_sign_in = { status: "waiting", user_code: "SAMPLE42", verification_uri: "https://example.com/devicelogin", expires_at: new Date(Date.now() + 900000).toISOString(), message: null };
    setTimeout(() => {
      if (fail) integrations.microsoft_sign_in = { ...integrations.microsoft_sign_in, status: "failed", message: "Your university has not approved this app yet (sample). You can upload saved .eml files instead." };
      else {
        integrations.microsoft_sign_in = { ...integrations.microsoft_sign_in, status: "connected", message: null };
        Object.assign(integrations.microsoft, { connected: true, account: "test.person@student.example.com", connected_at: now(), last_error: "One sample message could not be read." });
      }
    }, 9000);
    return clone(integrations.microsoft_sign_in);
  },
  async syncIntegration(provider) {
    await wait(700);
    const p = integrations[provider];
    if (!p.connected) throw new ApiError(409, "not_connected", "This account is not connected.");
    p.last_sync_at = now();
    return { ...emptySync(), emails_checked: 4, emails_already_read: 2, jobs_found: 2, jobs_created: 1, jobs_merged: 1 };
  },
  async disconnectIntegration(provider) {
    await wait();
    Object.assign(integrations[provider], { connected: false, account: null, connected_at: null, last_sync_at: null, last_error: null });
    if (provider === "microsoft") integrations.microsoft_sign_in = { status: "idle", user_code: null, verification_uri: null, expires_at: null, message: null };
  },
  async listNotifications() {
    await wait(150);
    const items = notifications.filter((n) => !n.dismissed_at);
    return { unread: items.filter((n) => !n.read_at).length, items: clone(items) };
  },
  async readNotification(id) { await wait(100); const n = notifications.find((x) => x.id === id); if (n && !n.read_at) n.read_at = now(); },
  async readAllNotifications() { await wait(100); notifications.forEach((n) => { n.read_at ??= now(); }); },
  async dismissNotification(id) { await wait(100); const n = notifications.find((x) => x.id === id); if (n) n.dismissed_at = now(); },
  async listApplicationEvents(id) {
    await wait(); findApp(id);
    return clone(events.filter((e) => e.app === id).map(({ app: _a, ...e }) => e).reverse());
  },
};

// ---- Applications (sample simulation of server behaviour) ----
const templates: TemplateRead[] = [
  { key: "utu_rekry_fi", kind: "cv", name: "UTU Rekry (suomeksi)", description: "Finnish UTU Rekry CV template." },
  { key: "utu_rekry_fi", kind: "cover_letter", name: "UTU Rekry (suomeksi)", description: "Finnish UTU Rekry cover letter template." },
  { key: "utu_rekry", kind: "cv", name: "UTU Rekry", description: "Follows the CV guidance from the sample career services." },
  { key: "utu_rekry", kind: "cover_letter", name: "UTU Rekry", description: "Follows the cover letter guidance from the sample career services." },
  { key: "classic", kind: "cv", name: "Classic", description: "One column, clear headings. Works well for most employers." },
  { key: "compact", kind: "cv", name: "Compact", description: "Fits more on one page with tighter spacing." },
  { key: "standard", kind: "cover_letter", name: "Standard", description: "A short, polite letter in three paragraphs." },
  { key: "brief", kind: "cover_letter", name: "Brief", description: "A few lines for web forms with a text box." },
];
let apps: ApplicationRead[] = [];
const events: (ApplicationEventRead & { app: string })[] = [];
function addEvent(app: string, event_type: string, details: Record<string, unknown> | null = null) {
  events.push({ app, id: uid(), event_type, details, package_hash: apps.find((a) => a.id === app)?.package_hash ?? null, occurred_at: now() });
}
function findApp(id: string) {
  const a = apps.find((x) => x.id === id);
  if (!a) throw notFound("application_not_found", "The application");
  return a;
}
function editable(a: ApplicationRead) {
  if (a.status === "submitted" || a.status === "withdrawn") throw new ApiError(409, "application_locked", "This application was recorded as sent and can't be changed.");
}
const appSummary = (a: ApplicationRead) => {
  const { id, job, status, include_cover_letter, submission_method, ready_at, submitted_at, withdrawn_at, created_at, updated_at, outcome = null, outcome_on = null } = a;
  return { id, job, status, include_cover_letter, submission_method, ready_at, submitted_at, withdrawn_at, created_at, updated_at, outcome, outcome_on };
};
const hash = (s: string) => { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) >>> 0; return h.toString(16).padStart(8, "0").repeat(8); };
function checkContent(kind: DraftKind, content: string): DraftIssue[] {
  const out: DraftIssue[] = [];
  for (const m of content.match(/\[[^\]\n]+\]/g) ?? []) out.push({ severity: "error", code: "placeholder", message: "A placeholder is still in the text.", excerpt: m });
  for (const line of content.split("\n")) if (/\d+\s+years/i.test(line)) out.push({ severity: "warning", code: "unsupported_claim", message: "This statement doesn't match any verified fact.", excerpt: line.trim() });
  if (kind === "cover_letter") out.push({ severity: "info", code: "posting_requirement", message: "The job posting mentions this requirement.", excerpt: "Finnish or English (sample)" });
  return out;
}
function generatedDraft(kind: DraftKind, template: string, version: number): DraftRead {
  const vf = facts.filter((f) => f.verification_status === "verified");
  const name = profile?.display_name ?? "Test Person";
  const content = kind === "cv"
    ? [`# ${name}`, "", ...vf.flatMap((f) => [`## ${({ education: "Education", language: "Languages", work_experience: "Experience", skill: "Skills" } as Record<string, string>)[f.category] ?? "Other"}`, `### ${f.subject}`, ...(f.valid_from ? [`*${f.valid_from} – ${f.valid_until ?? "present"}*`] : []), `- ${f.value_text}`, ""])].join("\n")
    : [`# ${name}`, "", "Dear [Hiring manager],", "", "I am writing to apply for this sample position. I have 5 years of experience with sample tools.", "", "Kind regards,", name].join("\n");
  const t = now();
  return { id: uid(), kind, version, source: "generated", template, document_id: null, document_name: null, content, evidence_fact_ids: vf.map((f) => f.id), status: "draft", content_sha256: hash(content), approved_at: null, created_at: t, updated_at: t, issues: checkContent(kind, content) };
}
function uploadedDraft(docId: string, name: string, version: number): DraftRead {
  const t = now();
  return { id: uid(), kind: "cv", version, source: "uploaded", template: null, document_id: docId, document_name: name, content: null, evidence_fact_ids: [], status: "draft", content_sha256: hash(docId), approved_at: null, created_at: t, updated_at: t, issues: [] };
}
function recomputeReady(a: ApplicationRead) {
  const ok = a.cv?.status === "approved" && (!a.include_cover_letter || a.cover_letter?.status === "approved");
  const was = a.status;
  a.status = ok ? "ready" : "draft";
  a.ready_at = ok ? (a.ready_at ?? now()) : null;
  a.package_hash = ok ? hash(`${a.cv?.content_sha256}${a.include_cover_letter ? a.cover_letter?.content_sha256 : ""}`) : null;
  a.updated_at = now();
  if (ok && was !== "ready") addEvent(a.id, "ready");
}
function pkg(a: ApplicationRead): PackageRead {
  const files = [a.cv, a.include_cover_letter ? a.cover_letter : null].filter((d): d is DraftRead => !!d)
    .map((d) => ({ kind: d.kind, version: d.version, filename: d.source === "uploaded" ? `${d.document_name ?? "cv"}.pdf` : `Test_Person_${d.kind}_v${d.version}.pdf`, sha256: d.content_sha256 }));
  return { application_id: a.id, ready: a.status === "ready", package_hash: a.package_hash, employer: a.job.company, role: a.job.title, destination: a.destination, contact_emails: a.contact_emails, files, cover_letter_text: a.include_cover_letter ? a.cover_letter?.content ?? null : null };
}

// ---- Sign-in, connected accounts and notifications (sample simulation) ----
// The sample passphrase lives in sessionStorage so a reload of the preview behaves like the real backend.
const PW_KEY = "duuniscript-sample-passphrase";
function mockPassphrase(): string | null {
  try { return typeof window === "undefined" ? null : window.sessionStorage.getItem(PW_KEY); } catch { return null; }
}
function setMockPassphrase(v: string) {
  try { window.sessionStorage.setItem(PW_KEY, v); } catch { /* sample only */ }
}
const mockToken = (pw: string) => `sample-token-${hash(pw).slice(0, 16)}`;

let msAttempts = 0;
const integrations: IntegrationsStatus = {
  google: { configured: true, connected: false, account: null, connected_at: null, last_sync_at: null, last_error: null },
  microsoft: { configured: true, connected: false, account: null, connected_at: null, last_sync_at: null, last_error: null },
  microsoft_sign_in: { status: "idle", user_code: null, verification_uri: null, expires_at: null, message: null },
};

const notifications: NotificationRead[] = (() => {
  const good = jobs.find((j) => (j.match_score ?? 0) >= 60) ?? jobs[0]!;
  const soon = jobs.find((j) => j.deadline_on) ?? jobs[1] ?? jobs[0]!;
  const mk = (kind: NotificationRead["kind"], j: JobRead, title: string, message: string, hoursAgo: number): NotificationRead => ({
    id: uid(), kind, entity_type: "job", entity_id: j.id, title, message, link: `/jobs/${j.id}`, created_at: new Date(Date.now() - hoursAgo * 3600000).toISOString(), read_at: null, dismissed_at: null,
  });
  return [
    mk("good_match", good, `Good match: ${good.title}`, `${good.company} · sample notification`, 2),
    mk("deadline_soon", soon, `Deadline soon: ${soon.title}`, "The application period ends in a few days (sample).", 5),
    mk("follow_up", jobs[2] ?? good, "Time to follow up?", "No answer for two weeks on a sample application.", 30),
  ];
})();

/** Endpoints that work without signing in. */
const OPEN = new Set<keyof ApiService>(["health", "authStatus", "setupPassword", "login", "documentContentUrl"]);

/** Simulates the backend's 401 auth_required once a passphrase exists. */
export const mockApi: ApiService = new Proxy(baseMock, {
  get(target, prop: string) {
    const v = (target as unknown as Record<string, unknown>)[prop];
    if (typeof v !== "function" || OPEN.has(prop as keyof ApiService)) return v;
    return (...args: unknown[]) => {
      const pw = mockPassphrase();
      if (pw && getToken() !== mockToken(pw)) {
        return Promise.reject(new ApiError(401, "auth_required", "Sign in to DuuniScript to continue.")).catch((e) => { setToken(null); signalAuthRequired(); throw e; });
      }
      return (v as (...a: unknown[]) => unknown).apply(target, args);
    };
  },
});
