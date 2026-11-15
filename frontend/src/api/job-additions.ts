import type { AiStatus as BaseAiStatus, JobCreate, JobMatchRead as BaseJobMatchRead } from "./types";

// Extend the generated contract without editing the generated file.
declare module "./types" {
  interface JobCreate { added_from?: "screenshots" | "text"; screenshot_draft_id?: string; apply_manually?: boolean; }
  interface JobUpdate { apply_manually?: boolean; }
  interface JobSummary { apply_manually: boolean; archived?: boolean; }
  interface JobListParams { include_archived?: boolean; }
  interface ApplicationCreate { auto_profile?: boolean; cv_profile_id?: string; }
  interface ApplicationRead { cv_profile_id?: string | null; }
  interface DashboardJob { apply_manually: boolean; }
}

export interface ScreenshotDraftRead {
  fields: JobCreate & { added_from: "screenshots" | "text"; apply_manually: true };
  screenshot_draft_id?: string | null;
  text: string;
  method: "ai" | "text_only";
  warnings: string[];
  images: number;
}
export type JobMatchRead = Omit<BaseJobMatchRead, "parts"> & {
  parts: BaseJobMatchRead["parts"] & { semantic: number | null; learned: number };
};
export interface AiStatus extends BaseAiStatus {
  embedding_model: string | null;
  embeddings_reachable: boolean;
  facts_indexed: number;
  jobs_indexed: number;
}
export interface AiIndexResult { available: boolean; facts: number; jobs: number; }
export interface FormAnswerRead {
  key: string; question: string; answer: string; source: "facts" | "profile" | "saved" | "job" | "none";
  needs_input: boolean; hint: string | null; fact_ids: string[];
}
export interface CvProfileInput { name: string; focus: string; summary: string | null; cv_template: string | null; }
export interface CvProfileRead extends CvProfileInput { id: string; }
export interface AiWriteResult { suggestion: string; issues: import("./types").DraftIssue[]; fact_ids: string[]; }
export interface JobAttachmentRead { id: string; filename: string; }
export interface OutcomeGroup { key: string; sent: number; responses: number; interviews: number; offers: number; response_rate: number | null; }
export interface OutcomeStats {
  sent: number; responses: number; interviews: number; offers: number; response_rate: number | null;
  interview_rate: number | null; median_days_to_reply: number | null; by_source: OutcomeGroup[]; by_role: OutcomeGroup[];
  sent_per_week: { week: string; sent: number }[];
}
