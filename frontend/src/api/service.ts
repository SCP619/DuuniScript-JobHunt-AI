import type {
  DocumentCategory, DocumentListParams, DocumentRead, DocumentText, DocumentUpdate, EvidenceCreate,
  EvidenceRead, FactCreate, FactListParams, FactRead, FactUpdate, HealthResponse, JobCreate,
  JobImportRequest, JobListParams, JobRead, JobSummary, JobUpdate, Page, ProfileDeleteResult,
  ProfileRead, ProfileUpsert, SourceRead, JobImportResult, JobAlertStatus, AlertSyncResult,
  FeedsStatus, FeedSyncResult, SourceUpdate, FactSuggestionList, FactImportRequest, FactImportResult,
  FactVerifyResult, TemplateRead, ApplicationCreate, ApplicationUpdate, ApplicationRead, ApplicationSummary,
  ApplicationListParams, DraftKind, DraftRead, DraftUpdate, DraftRegenerate, DraftApprove, PackageRead,
  SubmissionRecord, ApplicationEventRead, ExportFormat, DownloadedFile, DashboardSummary,
  BackupsStatus, BackupRead, AuthStatus, AuthToken, PasswordChange, IntegrationsStatus, IntegrationProvider,
  DeviceSignInRead, NotificationList, OutcomeUpdate, GmailDraftResult, SendEmailRequest, PolishResult,
} from "./types";
import type { ScreenshotDraftRead, JobMatchRead, AiStatus, AiIndexResult, FormAnswerRead, CvProfileInput, CvProfileRead, AiWriteResult, JobAttachmentRead, OutcomeStats } from "./job-additions";

export interface UploadDocumentInput { file: File; category: DocumentCategory; display_name?: string | null; }

export interface ApiService {
  getFormAnswers(id: string): Promise<FormAnswerRead[]>;
  saveFormAnswer(key: string, body: { answer: string }): Promise<void>;
  aiWriteLetter(id: string): Promise<AiWriteResult>;
  listCvProfiles(): Promise<CvProfileRead[]>;
  createCvProfile(body: CvProfileInput): Promise<CvProfileRead>;
  updateCvProfile(id: string, body: CvProfileInput): Promise<CvProfileRead>;
  deleteCvProfile(id: string): Promise<void>;
  getOutcomeStats(): Promise<OutcomeStats>;
  readJobText(body: { text: string }): Promise<ScreenshotDraftRead>;
  listJobAttachments(id: string): Promise<JobAttachmentRead[]>;
  downloadJobAttachment(id: string, attachmentId: string): Promise<DownloadedFile>;
  housekeepingJobs(): Promise<{ expired: number; archived: number }>;
  health(): Promise<HealthResponse>;
  listJobs(params?: JobListParams): Promise<Page<JobSummary>>;
  getJob(id: string): Promise<JobRead>;
  getJobMatch(id: string): Promise<JobMatchRead>;
  getDashboard(): Promise<DashboardSummary>;
  getBackups(): Promise<BackupsStatus>;
  createBackup(): Promise<BackupRead>;
  downloadBackup(name: string): Promise<DownloadedFile>;
  deleteBackup(name: string, confirm: boolean): Promise<void>;
  createJob(body: JobCreate): Promise<JobRead>;
  readJobScreenshots(files: File[]): Promise<ScreenshotDraftRead>;
  importJob(body: JobImportRequest): Promise<JobImportResult>;
  mergeJob(id: string, intoJobId: string): Promise<JobRead>;
  getJobAlerts(): Promise<JobAlertStatus>;
  syncJobAlerts(): Promise<AlertSyncResult>;
  uploadAlertEmails(files: File[]): Promise<AlertSyncResult>;
  updateJob(id: string, body: JobUpdate): Promise<JobRead>;
  listSources(): Promise<SourceRead[]>;
  updateSource(key: string, body: SourceUpdate): Promise<SourceRead>;
  getFeeds(): Promise<FeedsStatus>;
  syncFeeds(): Promise<FeedSyncResult[]>;
  syncFeed(key: string): Promise<FeedSyncResult>;
  getProfile(): Promise<ProfileRead>;
  putProfile(body: ProfileUpsert): Promise<ProfileRead>;
  deleteProfile(confirm: boolean): Promise<ProfileDeleteResult>;
  listFacts(params?: FactListParams): Promise<Page<FactRead>>;
  getFact(id: string): Promise<FactRead>;
  createFact(body: FactCreate): Promise<FactRead>;
  updateFact(id: string, body: FactUpdate): Promise<FactRead>;
  deleteFact(id: string): Promise<void>;
  listEvidence(factId: string): Promise<EvidenceRead[]>;
  createEvidence(factId: string, body: EvidenceCreate): Promise<EvidenceRead>;
  listDocuments(params?: DocumentListParams): Promise<Page<DocumentRead>>;
  getDocument(id: string): Promise<DocumentRead>;
  uploadDocument(input: UploadDocumentInput): Promise<DocumentRead>;
  updateDocument(id: string, body: DocumentUpdate): Promise<DocumentRead>;
  deleteDocument(id: string): Promise<void>;
  getDocumentText(id: string): Promise<DocumentText>;
  extractDocument(id: string): Promise<DocumentRead>;
  /** Download URL for the original file, or null when downloads are unavailable (sample data). */
  documentContentUrl(id: string): string | null;
  /** Downloads the original file with the sign-in token attached. */
  downloadDocument(id: string, fallbackName: string): Promise<DownloadedFile>;
  getFactSuggestions(documentId: string): Promise<FactSuggestionList>;
  importFacts(body: FactImportRequest): Promise<FactImportResult>;
  verifyFacts(factIds: string[]): Promise<FactVerifyResult>;
  listTemplates(): Promise<TemplateRead[]>;
  listApplications(params?: ApplicationListParams): Promise<Page<ApplicationSummary>>;
  getApplication(id: string): Promise<ApplicationRead>;
  createApplication(body: ApplicationCreate): Promise<ApplicationRead>;
  updateApplication(id: string, body: ApplicationUpdate): Promise<ApplicationRead>;
  deleteApplication(id: string): Promise<void>;
  saveDraft(id: string, kind: DraftKind, body: DraftUpdate): Promise<DraftRead>;
  regenerateDraft(id: string, kind: DraftKind, body: DraftRegenerate): Promise<DraftRead>;
  approveDraft(id: string, kind: DraftKind, body: DraftApprove): Promise<DraftRead>;
  exportDraft(id: string, kind: DraftKind, format: ExportFormat): Promise<DownloadedFile>;
  getPackage(id: string): Promise<PackageRead>;
  downloadPackageZip(id: string): Promise<DownloadedFile>;
  downloadEmailDraft(id: string): Promise<DownloadedFile>;
  recordSubmission(id: string, body: SubmissionRecord): Promise<ApplicationRead>;
  withdrawApplication(id: string): Promise<ApplicationRead>;
  listApplicationEvents(id: string): Promise<ApplicationEventRead[]>;
  authStatus(): Promise<AuthStatus>;
  setupPassword(password: string): Promise<AuthToken>;
  login(password: string): Promise<AuthToken>;
  logout(): Promise<void>;
  changePassword(body: PasswordChange): Promise<void>;
  getIntegrations(): Promise<IntegrationsStatus>;
  connectGoogle(): Promise<{ url: string }>;
  connectMicrosoft(): Promise<DeviceSignInRead>;
  syncIntegration(provider: IntegrationProvider): Promise<AlertSyncResult>;
  disconnectIntegration(provider: IntegrationProvider): Promise<void>;
  listNotifications(): Promise<NotificationList>;
  readNotification(id: string): Promise<void>;
  readAllNotifications(): Promise<void>;
  dismissNotification(id: string): Promise<void>;
  setOutcome(id: string, body: OutcomeUpdate): Promise<ApplicationRead>;
  createGmailDraft(id: string): Promise<GmailDraftResult>;
  sendEmail(id: string, body: SendEmailRequest): Promise<ApplicationRead>;
  getAi(): Promise<AiStatus>;
  indexAi(): Promise<AiIndexResult>;
  polishDraft(id: string, kind: DraftKind): Promise<PolishResult>;
}
