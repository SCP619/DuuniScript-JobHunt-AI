import { API_BASE_URL, request, requestBlob, requestWithStatus } from "./http";
import type { JobRead } from "./types";
import type { ApiService } from "./service";

const V = "/api/v1";

export const realApi: ApiService = {
  getFormAnswers: (id) => request("GET", `${V}/applications/${id}/form-answers`),
  saveFormAnswer: (key, body) => request("PUT", `${V}/form-answers/${encodeURIComponent(key)}`, { body }),
  aiWriteLetter: (id) => request("POST", `${V}/applications/${id}/drafts/cover_letter/ai-write`, { timeoutMs: 180_000 }),
  listCvProfiles: () => request("GET", `${V}/cv-profiles`),
  createCvProfile: (body) => request("POST", `${V}/cv-profiles`, { body }),
  updateCvProfile: (id, body) => request("PUT", `${V}/cv-profiles/${id}`, { body }),
  deleteCvProfile: (id) => request("DELETE", `${V}/cv-profiles/${id}`),
  getOutcomeStats: () => request("GET", `${V}/stats/outcomes`),
  readJobText: (body) => request("POST", `${V}/jobs/from-text`, { body, timeoutMs: 180_000 }),
  listJobAttachments: (id) => request("GET", `${V}/jobs/${id}/attachments`),
  downloadJobAttachment: (id, attachmentId) => requestBlob(`${V}/jobs/${id}/attachments/${attachmentId}`, "screenshot.png"),
  housekeepingJobs: () => request("POST", `${V}/jobs/housekeeping`),
  health: () => request("GET", "/health"),
  listJobs: (params = {}) => request("GET", `${V}/jobs`, { query: { ...params } }),
  getJob: (id) => request("GET", `${V}/jobs/${id}`),
  getJobMatch: (id) => request("GET", `${V}/jobs/${id}/match`),
  getDashboard: () => request("GET", `${V}/dashboard`),
  getBackups: () => request("GET", `${V}/backups`),
  createBackup: () => request("POST", `${V}/backups`),
  downloadBackup: (name) => requestBlob(`${V}/backups/${encodeURIComponent(name)}`, name),
  deleteBackup: (name, confirm) => request("DELETE", `${V}/backups/${encodeURIComponent(name)}`, { query: { confirm } }),
  createJob: (body) => request("POST", `${V}/jobs`, { body }),
  readJobScreenshots: (files) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    return request("POST", `${V}/jobs/from-screenshots`, { form, timeoutMs: 180_000 });
  },
  importJob: async (body) => {
    const r = await requestWithStatus<JobRead>("POST", `${V}/jobs/import`, { body });
    return { job: r.data, created: r.status !== 200 };
  },
  mergeJob: (id, intoJobId) => request("POST", `${V}/jobs/${id}/merge`, { body: { into_job_id: intoJobId } }),
  getJobAlerts: () => request("GET", `${V}/job-alerts`),
  syncJobAlerts: () => request("POST", `${V}/job-alerts/sync`),
  uploadAlertEmails: (files) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return request("POST", `${V}/job-alerts/emails`, { form });
  },
  updateJob: (id, body) => request("PATCH", `${V}/jobs/${id}`, { body }),
  listSources: () => request("GET", `${V}/sources`),
  updateSource: (key, body) => request("PATCH", `${V}/sources/${encodeURIComponent(key)}`, { body }),
  getFeeds: () => request("GET", `${V}/feeds`),
  syncFeeds: () => request("POST", `${V}/feeds/sync`),
  syncFeed: (key) => request("POST", `${V}/feeds/${encodeURIComponent(key)}/sync`),
  getProfile: () => request("GET", `${V}/profile`),
  putProfile: (body) => request("PUT", `${V}/profile`, { body }),
  deleteProfile: (confirm) =>
    request("DELETE", `${V}/profile`, { query: confirm ? { confirm: true } : undefined }),
  listFacts: (params = {}) => request("GET", `${V}/profile/facts`, { query: { ...params } }),
  getFact: (id) => request("GET", `${V}/profile/facts/${id}`),
  createFact: (body) => request("POST", `${V}/profile/facts`, { body }),
  updateFact: (id, body) => request("PATCH", `${V}/profile/facts/${id}`, { body }),
  deleteFact: (id) => request("DELETE", `${V}/profile/facts/${id}`),
  listEvidence: (factId) => request("GET", `${V}/profile/facts/${factId}/evidence`),
  createEvidence: (factId, body) => request("POST", `${V}/profile/facts/${factId}/evidence`, { body }),
  listDocuments: (params = {}) => request("GET", `${V}/documents`, { query: { ...params } }),
  getDocument: (id) => request("GET", `${V}/documents/${id}`),
  uploadDocument: ({ file, category, display_name }) => {
    const form = new FormData();
    form.append("file", file);
    form.append("category", category);
    if (display_name) form.append("display_name", display_name);
    return request("POST", `${V}/documents`, { form });
  },
  updateDocument: (id, body) => request("PATCH", `${V}/documents/${id}`, { body }),
  deleteDocument: (id) => request("DELETE", `${V}/documents/${id}`, { query: { confirm: true } }),
  getDocumentText: (id) => request("GET", `${V}/documents/${id}/text`),
  extractDocument: (id) => request("POST", `${V}/documents/${id}/extract`),
  documentContentUrl: (id) => `${API_BASE_URL}${V}/documents/${id}/content`,
  downloadDocument: (id, name) => requestBlob(`${V}/documents/${id}/content`, name),
  getFactSuggestions: (id) => request("GET", `${V}/documents/${id}/fact-suggestions`),
  importFacts: (body) => request("POST", `${V}/profile/facts/import`, { body }),
  verifyFacts: (fact_ids) => request("POST", `${V}/profile/facts/verify`, { body: { fact_ids } }),
  listTemplates: () => request("GET", `${V}/applications/templates`),
  listApplications: (params = {}) => request("GET", `${V}/applications`, { query: { ...params } }),
  getApplication: (id) => request("GET", `${V}/applications/${id}`),
  createApplication: (body) => request("POST", `${V}/applications`, { body }),
  updateApplication: (id, body) => request("PATCH", `${V}/applications/${id}`, { body }),
  deleteApplication: (id) => request("DELETE", `${V}/applications/${id}`, { query: { confirm: true } }),
  saveDraft: (id, kind, body) => request("PUT", `${V}/applications/${id}/drafts/${kind}`, { body }),
  regenerateDraft: (id, kind, body) => request("POST", `${V}/applications/${id}/drafts/${kind}/regenerate`, { body }),
  approveDraft: (id, kind, body) => request("POST", `${V}/applications/${id}/drafts/${kind}/approve`, { body }),
  exportDraft: (id, kind, format) => requestBlob(`${V}/applications/${id}/drafts/${kind}/export?format=${format}`, `${kind}.${format}`),
  getPackage: (id) => request("GET", `${V}/applications/${id}/package`),
  downloadPackageZip: (id) => requestBlob(`${V}/applications/${id}/package.zip`, "application.zip"),
  downloadEmailDraft: (id) => requestBlob(`${V}/applications/${id}/email.eml`, "application.eml"),
  recordSubmission: (id, body) => request("POST", `${V}/applications/${id}/submission`, { body }),
  withdrawApplication: (id) => request("POST", `${V}/applications/${id}/withdraw`),
  listApplicationEvents: (id) => request("GET", `${V}/applications/${id}/events`),
  authStatus: () => request("GET", `${V}/auth/status`),
  setupPassword: (password) => request("POST", `${V}/auth/setup`, { body: { password } }),
  login: (password) => request("POST", `${V}/auth/login`, { body: { password } }),
  logout: () => request("POST", `${V}/auth/logout`),
  changePassword: (body) => request("POST", `${V}/auth/change`, { body }),
  getIntegrations: () => request("GET", `${V}/integrations`),
  connectGoogle: () => request("POST", `${V}/integrations/google/connect`),
  connectMicrosoft: () => request("POST", `${V}/integrations/microsoft/connect`),
  syncIntegration: (p) => request("POST", `${V}/integrations/${p}/sync`),
  disconnectIntegration: (p) => request("DELETE", `${V}/integrations/${p}`),
  listNotifications: () => request("GET", `${V}/notifications`),
  readNotification: (id) => request("POST", `${V}/notifications/${id}/read`),
  readAllNotifications: () => request("POST", `${V}/notifications/read-all`),
  dismissNotification: (id) => request("POST", `${V}/notifications/${id}/dismiss`),
  setOutcome: (id, body) => request("PUT", `${V}/applications/${id}/outcome`, { body }),
  createGmailDraft: (id) => request("POST", `${V}/applications/${id}/gmail-draft`),
  sendEmail: (id, body) => request("POST", `${V}/applications/${id}/send-email`, { body }),
  getAi: () => request("GET", `${V}/ai`),
  indexAi: () => request("POST", `${V}/ai/index`, { timeoutMs: 180_000 }),
  polishDraft: (id, kind) => request("POST", `${V}/applications/${id}/drafts/${kind}/polish`),
};
