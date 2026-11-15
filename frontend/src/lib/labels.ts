import type {
  DocumentCategory, EmploymentType, EvidenceSourceType, FactCategory, JobStatus, ListingStatus,
  SourceAccessType, VerificationStatus, WorkMode,
} from "@/api/types";

export type Tone = "neutral" | "info" | "success" | "warning" | "danger" | "muted" | "primary";

export const JOB_STATUS: Record<JobStatus, { label: string; tone: Tone }> = {
  new: { label: "New", tone: "info" },
  reviewed: { label: "Reviewed", tone: "neutral" },
  saved: { label: "Saved", tone: "primary" },
  not_relevant: { label: "Not relevant", tone: "muted" },
  drafting: { label: "Drafting", tone: "warning" },
  applied: { label: "Applied", tone: "success" },
  closed: { label: "Closed", tone: "muted" },
  expired: { label: "Expired", tone: "muted" },
};
export const JOB_STATUSES = Object.keys(JOB_STATUS) as JobStatus[];

export const EMPLOYMENT_TYPE: Record<EmploymentType, string> = {
  full_time: "Full-time", part_time: "Part-time", contract: "Contract", temporary: "Temporary",
  internship: "Internship", volunteer: "Volunteer", per_diem: "Per diem", other: "Other",
};
export const WORK_MODE: Record<WorkMode, string> = { onsite: "On-site", hybrid: "Hybrid", remote: "Remote" };
export const LISTING_STATUS: Record<ListingStatus, string> = { active: "Active", removed: "Removed", unknown: "Unknown" };

export const VERIFICATION: Record<VerificationStatus, { label: string; tone: Tone }> = {
  unverified: { label: "Not yet confirmed", tone: "neutral" },
  verified: { label: "Confirmed by you", tone: "success" },
  rejected: { label: "Rejected", tone: "danger" },
  expired: { label: "Out of date", tone: "muted" },
};

export const FACT_CATEGORY: Record<FactCategory, string> = {
  contact: "Contact", summary: "Summary", education: "Education", work_experience: "Work experience",
  skill: "Skills", project: "Projects", certification: "Certifications", language: "Languages",
  publication: "Publications", reference: "References", achievement: "Achievements",
  preference: "Preferences", other: "Other",
};
export const FACT_CATEGORIES = Object.keys(FACT_CATEGORY) as FactCategory[];

export const EVIDENCE_TYPE: Record<Exclude<EvidenceSourceType, "integration">, string> = {
  document: "Document", url: "Web link", user_input: "Note",
};
export const EVIDENCE_TYPE_ALL: Record<EvidenceSourceType, string> = { ...EVIDENCE_TYPE, integration: "Integration" };

export const DOCUMENT_CATEGORY: Record<DocumentCategory, string> = {
  cv: "CV", cover_letter: "Cover letter", certificate: "Certificate", transcript: "Transcript",
  portfolio: "Portfolio", publication: "Publication", reference: "Reference", other: "Other",
};
export const DOCUMENT_CATEGORIES = Object.keys(DOCUMENT_CATEGORY) as DocumentCategory[];

export const EXTRACTION_ERROR: Record<string, string> = {
  encrypted: "The file is password-protected",
  too_many_pages: "Too many pages",
  parse_error: "The file couldn't be read",
  unsupported_encoding: "Unsupported text encoding",
  ocr_unavailable: "Text could not be read from this image on this computer (Windows text recognition is not available).",
};

export const ACCESS_TYPE: Record<SourceAccessType, string> = {
  user_provided: "You provide the link",
  official_feed: "Official feed",
  official_api: "Official API",
  public_structured_data: "Public structured data",
  public_page_uncertain: "Public page (terms unclear)",
  supported_authenticated: "Signed-in access",
  restricted: "Restricted",
};
