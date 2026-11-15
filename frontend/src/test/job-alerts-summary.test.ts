import { describe, expect, it } from "vitest";
import { jobSourceFilterOptions, syncIntervalText, syncSummary } from "@/lib/job-alerts";
import type { AlertSyncResult, SourceRead } from "@/api/types";

const r = (p: Partial<AlertSyncResult> = {}): AlertSyncResult => ({ emails_checked: 0, emails_already_read: 0, emails_not_alerts: 0, emails_unverified: 0, emails_without_jobs: 0, jobs_found: 0, jobs_created: 0, jobs_merged: 0, jobs_already_known: 0, possible_duplicates: 0, unreadable_cards: 0, ...p });

describe("sync summary", () => {
  it("lists the non-zero parts", () => {
    expect(syncSummary(r({ jobs_created: 3, jobs_merged: 2, possible_duplicates: 1 }))).toBe("3 new jobs, 2 added to jobs already in your list, 1 possible duplicate");
  });
  it("omits zero parts", () => {
    expect(syncSummary(r({ jobs_created: 1, possible_duplicates: 2 }))).toBe("1 new job, 2 possible duplicates");
  });
  it("says no new alerts when everything is zero", () => {
    expect(syncSummary(r())).toBe("No new job alerts.");
  });
  it("adds the sender check warning", () => {
    expect(syncSummary(r({ emails_unverified: 2 }))).toBe("No new job alerts. 2 emails claimed to be job alerts but failed the sender check and were ignored.");
  });
  it("describes the schedule", () => {
    expect(syncIntervalText({ sync_interval_minutes: 0 })).toBe("Automatic checks are off");
    expect(syncIntervalText({ sync_interval_minutes: 15 })).toBe("Checks every 15 minutes");
  });
  it("leaves the mailbox out of the source filter", () => {
    const s = [{ key: "email_alerts" }, { key: "alert_linkedin" }] as SourceRead[];
    expect(jobSourceFilterOptions(s).map((x) => x.key)).toEqual(["alert_linkedin"]);
  });
});
