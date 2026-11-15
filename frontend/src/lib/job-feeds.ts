import type { FeedRead, FeedSyncResult, FinlandAvailability } from "@/api/types";

export type FinlandFilter = "yes" | "yes_unknown" | "all";
export const FINLAND_FILTER_STORAGE_KEY = "duuniscript.finland-filter";
export function parseFinlandFilter(value: unknown): FinlandFilter | undefined {
  return value === "yes" || value === "yes_unknown" || value === "all" ? value : undefined;
}
export function finlandQuery(choice: FinlandFilter): FinlandAvailability[] | undefined {
  return choice === "yes" ? ["yes"] : choice === "yes_unknown" ? ["yes", "unknown"] : undefined;
}

/** Summarizes returned counts only; never decides which jobs are available. */
export function feedSyncSummary(results: FeedSyncResult[]): string {
  if (!results.length) return "All feeds were checked recently. Nothing is due yet.";
  const total = (key: "jobs_created" | "jobs_merged" | "possible_duplicates" | "skipped_not_available" | "skipped_keywords") => results.reduce((sum, r) => sum + r[key], 0);
  const parts: string[] = [];
  const created = total("jobs_created"), merged = total("jobs_merged"), duplicates = total("possible_duplicates"), unavailable = total("skipped_not_available"), keywords = total("skipped_keywords");
  if (created) parts.push(`${created} new job${created === 1 ? "" : "s"}`);
  if (merged) parts.push(`${merged} added to jobs already in your list`);
  if (duplicates) parts.push(`${duplicates} possible duplicate${duplicates === 1 ? "" : "s"}`);
  if (unavailable) parts.push(`${unavailable} skipped (not open to Finland)`);
  if (keywords) parts.push(`${keywords} skipped (keywords did not match)`);
  const errors = results.filter((r) => r.error !== null).map((r) => `${r.name}: ${r.error}`);
  const summary = parts.length ? parts.join(", ") : errors.length ? "" : "No new jobs.";
  return [summary, ...errors].filter(Boolean).join("\n");
}

export function feedAttribution(key: string, feeds: FeedRead[]): string | null {
  return key.startsWith("feed_") ? feeds.find((f) => f.key === key)?.attribution ?? null : null;
}

export function nextCheckRelative(iso: string | null, now = Date.now()): string {
  if (!iso || new Date(iso).getTime() <= now) return "Now";
  const minutes = Math.max(1, Math.ceil((new Date(iso).getTime() - now) / 60000));
  if (minutes < 60) return `in ${minutes} minute${minutes === 1 ? "" : "s"}`;
  const hours = Math.ceil(minutes / 60);
  if (hours < 24) return `in ${hours} hour${hours === 1 ? "" : "s"}`;
  const days = Math.ceil(hours / 24);
  return `in ${days} day${days === 1 ? "" : "s"}`;
}