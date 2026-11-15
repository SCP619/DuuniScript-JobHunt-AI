// Exact API types, generated from the backend OpenAPI contract. Do not edit by hand.
export type DocumentCategory = "cv" | "cover_letter" | "certificate" | "transcript" | "portfolio" | "publication" | "reference" | "other";
export type ExtractionStatus = "pending" | "succeeded" | "no_text" | "failed";
export type EmploymentType = "full_time" | "part_time" | "contract" | "temporary" | "internship" | "volunteer" | "per_diem" | "other";
export type WorkMode = "onsite" | "hybrid" | "remote";
export type JobStatus = "new" | "reviewed" | "saved" | "not_relevant" | "drafting" | "applied" | "closed" | "expired";
export type ListingStatus = "active" | "removed" | "unknown";
export type FinlandAvailability = "yes" | "no" | "unknown";
export type EvidenceSourceType = "document" | "user_input" | "url" | "integration";
export type FactCategory = "contact" | "summary" | "education" | "work_experience" | "skill" | "project" | "certification" | "language" | "publication" | "reference" | "achievement" | "preference" | "other";
export type VerificationStatus = "unverified" | "verified" | "rejected" | "expired";
export type SourceAccessType = "official_api" | "official_feed" | "public_structured_data" | "public_page_uncertain" | "supported_authenticated" | "user_provided" | "restricted";

export interface Page<T> { items: T[]; total: number; limit: number; offset: number; }
export interface ErrorResponse { error: { code: string; message: string; details?: Record<string, unknown>; }; }
export interface HealthResponse { status: string; version: string; database: string; }

export interface DocumentRead { id: string; category: DocumentCategory; display_name: string; original_filename: string; file_extension: string; mime_type: string; size_bytes: number; sha256: string; extraction_status: ExtractionStatus; extraction_error: string | null; extracted_char_count: number | null; extractor_version: string | null; extracted_at: string | null; extraction_method: "text" | "ocr" | null; created_at: string; updated_at: string; archived_at: string | null; }
export interface DocumentText { document_id: string; extraction_status: ExtractionStatus; extraction_error: string | null; extractor_version: string | null; text: string | null; }
export interface DocumentUpdate { display_name?: string | null; category?: DocumentCategory | null; archived?: boolean | null; }

export interface ProfileRead { id: string; display_name: string; email: string | null; phone: string | null; location: string | null; professional_summary: string | null; created_at: string; updated_at: string; }
export interface ProfileUpsert { display_name: string; email?: string | null; phone?: string | null; location?: string | null; professional_summary?: string | null; }
export interface ProfileDeleteResult { deleted: boolean; deleted_facts: number; deleted_evidence: number; deleted_documents: number; }

export interface FactCreate { category: FactCategory; subject: string; value_text: string; valid_from?: string | null; valid_until?: string | null; }
export interface FactRead { id: string; profile_id: string; category: FactCategory; subject: string; value_text: string; verification_status: VerificationStatus; valid_from: string | null; valid_until: string | null; verified_at: string | null; created_at: string; updated_at: string; evidence_count: number; }
export interface FactUpdate { category?: FactCategory | null; subject?: string | null; value_text?: string | null; valid_from?: string | null; valid_until?: string | null; verification_status?: VerificationStatus | null; }
export interface EvidenceCreate { source_type: EvidenceSourceType; source_reference?: string | null; document_id?: string | null; excerpt?: string | null; }
export interface EvidenceRead { id: string; fact_id: string; document_id: string | null; source_type: EvidenceSourceType; source_reference: string | null; excerpt: string | null; verification_status: VerificationStatus; created_at: string; }

export interface JobCreate { title: string; company: string; url?: string | null; application_url?: string | null; location?: string | null; description?: string | null; employment_type?: EmploymentType | null; work_mode?: WorkMode | null; salary_text?: string | null; language?: string | null; published_on?: string | null; deadline_on?: string | null; deadline_at?: string | null; }
export interface JobImportRequest { url: string; }
export interface JobUpdate { status?: JobStatus | null; hidden?: boolean | null; user_notes?: string | null; title?: string | null; company?: string | null; location?: string | null; description?: string | null; employment_type?: EmploymentType | null; work_mode?: WorkMode | null; salary_text?: string | null; language?: string | null; application_url?: string | null; published_on?: string | null; deadline_on?: string | null; deadline_at?: string | null; possible_duplicate_of?: null; }
export interface JobSummary { id: string; title: string; company: string; location: string | null; employment_type: EmploymentType | null; work_mode: WorkMode | null; language: string | null; published_on: string | null; deadline_on: string | null; first_seen_at: string; status: JobStatus; hidden: boolean; canonical_url: string | null; sources: string[]; possible_duplicate_of: string | null; available_from_finland: FinlandAvailability; match_score: number | null; match_has_blockers: boolean; }
export interface JobListingRead { source_key: string; source_name: string; source_url: string | null; external_id: string | null; source_published_on: string | null; first_seen_at: string; last_seen_at: string; listing_status: ListingStatus; captured_at: string | null; parser_version: string | null; }
export interface JobRead extends JobSummary { description: string | null; salary_text: string | null; application_url: string | null; deadline_at: string | null; last_seen_at: string; user_notes: string | null; created_at: string; updated_at: string; listings: JobListingRead[]; }
export interface JobMatchRead {
  job_id: string; score: number | null; scoring_version: string;
  reasons: string[]; matched_skills: string[]; missing_terms: string[];
  blockers: { code: "not_open_to_finland" | "deadline_passed" | "language_required"; message: string }[];
  parts: { skills: number; role: number; wording: number }; computed_at: string;
}
export interface DashboardJob { id: string; title: string; company: string; location: string | null; deadline_on: string | null; status: JobStatus; match_score: number | null; }
export interface DashboardSummary {
  counts: { jobs: number; jobs_new_this_week: number; jobs_saved: number; jobs_good_match: number; applications_drafting: number; applications_ready: number; applications_sent: number; interviews?: number; offers?: number };
  deadlines_soon: DashboardJob[]; best_matches: DashboardJob[];
  status: { last_source_check_at: string | null; sources_turned_off: string[]; sources_failing: string[]; last_backup_at: string | null; automatic_backups: boolean };
}
export interface BackupRead { name: string; size_bytes: number; created_at: string; }
export interface BackupsStatus { interval_hours: number; keep: number; backups: BackupRead[]; }
export interface SourceRead { id: string; key: string; name: string; domain: string | null; access_type: SourceAccessType; access_method: string; terms_url: string | null; policy_notes: string | null; enabled: boolean; last_success_at: string | null; last_error_at: string | null; last_error: string | null; }

export interface JobMergeRequest { into_job_id: string; }
export interface AlertSiteRead { key: string; name: string; format_verified: boolean; emails_read: number; last_email_at: string | null; }
export interface JobAlertStatus { configured: boolean; mailbox: string | null; folder: string; sync_interval_minutes: number; last_sync_at: string | null; last_error_at: string | null; last_error: string | null; emails_read: number; jobs_created: number; jobs_merged: number; sites: AlertSiteRead[]; }
export interface AlertSyncResult { emails_checked: number; emails_already_read: number; emails_not_alerts: number; emails_unverified: number; emails_without_jobs: number; jobs_found: number; jobs_created: number; jobs_merged: number; jobs_already_known: number; possible_duplicates: number; unreadable_cards: number; }

export interface FeedRead {
  key: string; name: string; domain: string; enabled: boolean;
  access_method: string; terms_url: string; attribution: string; min_interval_hours: number;
  last_success_at: string | null; last_error_at: string | null; last_error: string | null;
  next_allowed_at: string | null; jobs: number;
}
export interface FeedsStatus { check_interval_minutes: number; skip_unavailable: boolean; keywords: string[]; feeds: FeedRead[]; }
export interface FeedSyncResult {
  key: string; name: string; jobs_found: number; jobs_created: number; jobs_merged: number;
  jobs_already_known: number; possible_duplicates: number; skipped_not_available: number;
  skipped_keywords: number; error: string | null;
}
export interface SourceUpdate { enabled: boolean; }

// Frontend-only helper types for query parameters.
/** importJob result: created=false means the backend answered 200 (added to an existing job). */
export interface JobImportResult { job: JobRead; created: boolean; }
export type JobSort = "newest" | "published" | "deadline" | "company" | "title" | "match";
export interface JobListParams {
  q?: string; company?: string; location?: string; source?: string; status?: JobStatus[];
  employment_type?: EmploymentType; work_mode?: WorkMode; language?: string;
  available_from_finland?: FinlandAvailability[]; min_match?: number;
  published_from?: string; published_to?: string; deadline_from?: string; deadline_to?: string;
  hidden?: boolean; include_hidden?: boolean; sort?: JobSort; limit?: number; offset?: number;
}
export interface FactListParams { category?: FactCategory; verification_status?: VerificationStatus; limit?: number; offset?: number; }
export interface DocumentListParams { category?: DocumentCategory; include_archived?: boolean; limit?: number; offset?: number; }

// Facts from CVs, drafts and applications.
export type DraftKind = "cv" | "cover_letter";
export type DraftSource = "generated" | "uploaded";
export type DraftStatus = "draft" | "approved";
export type ApplicationStatus = "draft" | "ready" | "submitted" | "withdrawn";
export type SubmissionMethod = "web_form" | "email" | "other";
export interface FactSuggestion { already_in_profile: boolean; category: FactCategory; excerpt: string; subject: string; valid_from: string | null; valid_until: string | null; value_text: string; }
export interface FactSuggestionList { document_id: string; items: FactSuggestion[]; parser_version: string; }
export interface FactImportItem { category: FactCategory; excerpt?: string | null; subject: string; valid_from?: string | null; valid_until?: string | null; value_text: string; }
export interface FactImportRequest { document_id: string; items: FactImportItem[]; }
export interface FactImportResult { created: number; facts: FactRead[]; skipped_existing: number; }
export interface FactVerifyRequest { fact_ids: string[]; }
export interface FactVerifyResult { facts: FactRead[]; verified: number; }
export interface TemplateRead { description: string; key: string; kind: DraftKind; name: string; }
export interface ApplicationCreate { job_id: string; cv_source?: DraftSource; cv_template?: string; cv_document_id?: string | null; include_cover_letter?: boolean; letter_template?: string; }
export interface ApplicationUpdate { include_cover_letter?: boolean; notes?: string | null; }
export interface DraftIssue { severity: "error" | "warning" | "info"; code: string; message: string; excerpt?: string | null; }
export interface DraftRead { id: string; kind: DraftKind; version: number; source: DraftSource; template: string | null; document_id: string | null; document_name?: string | null; content: string | null; evidence_fact_ids: string[]; status: DraftStatus; content_sha256: string; approved_at: string | null; created_at: string; updated_at: string; issues?: DraftIssue[]; }
export interface DraftUpdate { source?: DraftSource; content?: string | null; document_id?: string | null; }
export interface DraftRegenerate { template?: string | null; }
export interface DraftApprove { acknowledge_warnings?: boolean; }
export interface JobBrief { id: string; title: string; company: string; location: string | null; deadline_on: string | null; status: JobStatus; }
export interface ApplicationSummary { id: string; job: JobBrief; status: ApplicationStatus; include_cover_letter: boolean; submission_method: SubmissionMethod | null; ready_at: string | null; submitted_at: string | null; withdrawn_at: string | null; created_at: string; updated_at: string; outcome?: ApplicationOutcome | null; outcome_on?: string | null; }
export interface ApplicationRead extends ApplicationSummary { destination: string | null; contact_emails: string[]; package_hash: string | null; confirmation_reference: string | null; notes: string | null; cv: DraftRead | null; cover_letter: DraftRead | null; }
export interface PackageFile { kind: DraftKind; version: number; filename: string; sha256: string; }
export interface PackageRead { application_id: string; ready: boolean; package_hash: string | null; employer: string; role: string; destination: string | null; contact_emails: string[]; files: PackageFile[]; cover_letter_text: string | null; }
export interface SubmissionRecord { confirm: true; package_hash: string; method: SubmissionMethod; destination?: string | null; confirmation_reference?: string | null; }
export interface ApplicationEventRead { id: string; event_type: string; package_hash: string | null; details: Record<string, unknown> | null; occurred_at: string; }
export interface ApplicationListParams { status?: ApplicationStatus; job_id?: string; limit?: number; offset?: number; }
export type ExportFormat = "pdf" | "docx" | "md" | "txt";
/** Frontend helper: a downloaded file. */
export interface DownloadedFile { blob: Blob; filename: string; }

// ---- Sign-in, connected accounts, notifications, outcomes, Gmail, local AI ----
export interface AuthStatus { password_set: boolean; signed_in: boolean; }
export interface AuthToken { token: string; expires_at: string; }
export interface PasswordChange { current_password: string; new_password: string; }
export interface ProviderStatus { configured: boolean; connected: boolean; account: string | null; connected_at: string | null; last_sync_at: string | null; last_error: string | null; }
export interface DeviceSignInRead { status: "idle" | "waiting" | "connected" | "failed"; user_code: string | null; verification_uri: string | null; expires_at: string | null; message: string | null; }
export interface IntegrationsStatus { google: ProviderStatus; microsoft: ProviderStatus; microsoft_sign_in: DeviceSignInRead; }
export type IntegrationProvider = "google" | "microsoft";
export type NotificationKind = "good_match" | "deadline_soon" | "ready_not_sent" | "follow_up";
export interface NotificationRead { id: string; kind: NotificationKind; entity_type: "job" | "application"; entity_id: string; title: string; message: string; link: string; created_at: string; read_at: string | null; dismissed_at: string | null; }
export interface NotificationList { unread: number; items: NotificationRead[]; }
export type ApplicationOutcome = "no_response" | "interview" | "rejected" | "offer" | "accepted" | "declined";
export interface OutcomeUpdate { outcome: ApplicationOutcome | null; outcome_on?: string | null; }
export interface GmailDraftResult { draft_id: string; open_url: string; }
export interface SendEmailRequest { confirm: true; package_hash: string; to: string; }
export interface AiStatus { enabled: boolean; model: string | null; reachable: boolean; message: string | null; }
export interface PolishResult { suggestion: string; issues: DraftIssue[]; }
