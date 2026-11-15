import type { AlertSyncResult, JobAlertStatus, JobListingRead, SourceRead } from "@/api/types";

const n = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/** Summary line for a sync or email upload, built only from counts the API returned. */
export function syncSummary(r: AlertSyncResult): string {
  const parts: string[] = [];
  if (r.jobs_created > 0) parts.push(n(r.jobs_created, "new job", "new jobs"));
  if (r.jobs_merged > 0) parts.push(`${r.jobs_merged} added to jobs already in your list`);
  if (r.possible_duplicates > 0) parts.push(n(r.possible_duplicates, "possible duplicate", "possible duplicates"));
  let text = parts.length ? parts.join(", ") : "No new job alerts.";
  if (r.emails_unverified > 0) {
    text += ` ${r.emails_unverified === 1 ? "1 email" : `${r.emails_unverified} emails`} claimed to be job alerts but failed the sender check and were ignored.`;
  }
  return text;
}

export function syncIntervalText(s: Pick<JobAlertStatus, "sync_interval_minutes">): string {
  const m = s.sync_interval_minutes;
  if (m === 0) return "Automatic checks are off";
  return m === 1 ? "Checks every minute" : `Checks every ${m} minutes`;
}

/** The mailbox itself (email_alerts) has no jobs, so it isn't a job filter option. */
export function jobSourceFilterOptions(sources: SourceRead[]): SourceRead[] {
  return sources.filter((s) => s.key !== "email_alerts");
}

export function cameFromAlertEmail(listings: Pick<JobListingRead, "source_key">[]): boolean {
  return listings.some((l) => l.source_key.startsWith("alert_"));
}

export const MAX_ALERT_EMAILS = 50;
