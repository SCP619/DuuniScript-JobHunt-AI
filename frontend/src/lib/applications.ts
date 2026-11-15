// Browser-safe helpers for applications: labels, request payload shaping and the plain-text preview parser.
// No application rules live here; the API decides issues, readiness and versions.
import type {
  ApplicationCreate, ApplicationEventRead, ApplicationStatus, DraftIssue, DraftSource, FactImportRequest,
  FactSuggestion, SubmissionMethod, SubmissionRecord,
} from "@/api/types";
import type { Tone } from "@/lib/labels";

export const APPLICATION_STATUS: Record<ApplicationStatus, { label: string; tone: Tone }> = {
  draft: { label: "Drafting", tone: "warning" },
  ready: { label: "Ready to send", tone: "info" },
  submitted: { label: "Sent", tone: "success" },
  withdrawn: { label: "Withdrawn", tone: "muted" },
};
export const SUBMISSION_METHOD: Record<SubmissionMethod, string> = {
  web_form: "Through the employer's website", email: "By email", other: "Other",
};

/** Editable copy of a suggestion in the review dialog. */
export interface SuggestionRow extends FactSuggestion { key: string; checked: boolean; }
export const toRows = (items: FactSuggestion[]): SuggestionRow[] =>
  items.map((s, i) => ({ ...s, key: String(i), checked: !s.already_in_profile }));

export function buildFactImport(documentId: string, rows: SuggestionRow[]): FactImportRequest {
  return {
    document_id: documentId,
    items: rows.filter((r) => r.checked).map((r) => ({
      category: r.category, subject: r.subject, value_text: r.value_text,
      valid_from: r.valid_from || null, valid_until: r.valid_until || null, excerpt: r.excerpt || null,
    })),
  };
}

export interface PrepareChoice {
  cvSource: DraftSource; cvTemplate: string; cvDocumentId: string; includeLetter: boolean; letterTemplate: string; cvProfile?: string;
}
export function buildApplicationCreate(jobId: string, c: PrepareChoice): ApplicationCreate {
  const body: ApplicationCreate = { job_id: jobId, cv_source: c.cvSource, include_cover_letter: c.includeLetter };
  if (c.cvSource === "generated") { if (c.cvTemplate) body.cv_template = c.cvTemplate; }
  else body.cv_document_id = c.cvDocumentId || null;
  if (c.includeLetter && c.letterTemplate) body.letter_template = c.letterTemplate;
  if (c.cvProfile !== undefined) Object.assign(body, profileSelection(c.cvProfile));
  return body;
}

export function buildSubmission(packageHash: string, method: SubmissionMethod, reference: string): SubmissionRecord {
  const ref = reference.trim();
  return { confirm: true, package_hash: packageHash, method, confirmation_reference: ref || null };
}

export const groupIssues = (issues: DraftIssue[] = []) => ({
  error: issues.filter((i) => i.severity === "error"),
  warning: issues.filter((i) => i.severity === "warning"),
  info: issues.filter((i) => i.severity === "info"),
});

export function eventLabel(e: ApplicationEventRead): string {
  const v = e.details?.["version"];
  switch (e.event_type) {
    case "cv_approved": return `CV version ${v ?? "?"} approved`;
    case "cover_letter_approved": return `Cover letter version ${v ?? "?"} approved`;
    case "ready": return "Ready to send";
    case "reopened": return "Changed after approval; approve again";
    case "submitted_by_user": return "Recorded as sent";
    case "withdrawn": return "Withdrawn";
    case "created": return "Application started";
    default: return e.event_type.replace(/_/g, " ");
  }
}

export type PreviewBlock =
  | { type: "name" | "section" | "entry" | "meta" | "para"; text: string }
  | { type: "list"; items: string[] };

/** Parse the small draft syntax into blocks. Output is plain strings only. */
export function parseDraft(content: string): PreviewBlock[] {
  const out: PreviewBlock[] = [];
  for (const raw of content.split(/\r?\n/)) {
    const line = raw.trimEnd();
    if (!line.trim()) continue;
    if (line.startsWith("- ")) {
      const last = out[out.length - 1];
      if (last?.type === "list") last.items.push(line.slice(2));
      else out.push({ type: "list", items: [line.slice(2)] });
    } else if (line.startsWith("### ")) out.push({ type: "entry", text: line.slice(4) });
    else if (line.startsWith("## ")) out.push({ type: "section", text: line.slice(3) });
    else if (line.startsWith("# ")) out.push({ type: "name", text: line.slice(2) });
    else if (/^\*[^*].*\*$/.test(line.trim())) out.push({ type: "meta", text: line.trim().slice(1, -1) });
    else out.push({ type: "para", text: line });
  }
  return out;
}

export function saveBlob(file: { blob: Blob; filename: string }) {
  const url = URL.createObjectURL(file.blob);
  const a = document.createElement("a");
  a.href = url; a.download = file.filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function profileSelection(value: string): Pick<ApplicationCreate, "auto_profile" | "cv_profile_id"> {
  if (value === "auto") return { auto_profile: true };
  if (value === "none") return { auto_profile: false };
  return { cv_profile_id: value };
}
export function formAnswerKey(key: string, appId: string) { return key === "why_us" ? `why_us:${appId}` : key; }
export function copyAllAnswers(items: import("@/api/job-additions").FormAnswerRead[]) {
  return items.map((item) => `${item.question}\n${item.answer ?? ""}`).join("\n\n");
}
