import { afterEach, describe, expect, it, vi } from "vitest";
import { realApi } from "@/api/real";
import { mockApi } from "@/api/mock";
import { finlandQuery, feedSyncSummary, nextCheckRelative } from "@/lib/job-feeds";
import type { FeedSyncResult } from "@/api/types";

const result = (p: Partial<FeedSyncResult> = {}): FeedSyncResult => ({ key: "feed_remotive", name: "Remotive", jobs_found: 0, jobs_created: 0, jobs_merged: 0, jobs_already_known: 0, possible_duplicates: 0, skipped_not_available: 0, skipped_keywords: 0, error: null, ...p });
afterEach(() => vi.restoreAllMocks());
describe("Finland availability requests", () => {
  it("defaults to yes and unknown as repeated query params", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ items: [] })));
    await realApi.listJobs({ available_from_finland: finlandQuery("yes_unknown") });
    const url = new URL(String(fetchMock.mock.calls[0]?.[0]));
    expect(url.searchParams.getAll("available_from_finland")).toEqual(["yes", "unknown"]);
  });
  it("Yes sends only yes", () => expect(finlandQuery("yes")).toEqual(["yes"]));
  it("All does not send an availability filter", () => expect(finlandQuery("all")).toBeUndefined());
  it("mock default excludes no while All includes no", async () => {
    const filtered = await mockApi.listJobs({ available_from_finland: finlandQuery("yes_unknown") });
    const all = await mockApi.listJobs();
    expect(filtered.items.some((j) => j.available_from_finland === "no")).toBe(false);
    expect(all.items.some((j) => j.available_from_finland === "no")).toBe(true);
    expect(all.total).toBeGreaterThan(filtered.total);
  });
  it("source switch contract uses PATCH with enabled", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ key: "feed_remotive", enabled: false })));
    await realApi.updateSource("feed_remotive", { enabled: false });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://127.0.0.1:8000/api/v1/sources/feed_remotive");
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ method: "PATCH", body: '{"enabled":false}' });
  });
});
describe("feed results", () => {
  it("summarizes concrete API counts and omits zeros", () => {
    expect(feedSyncSummary([result({ jobs_created: 12, jobs_merged: 3, possible_duplicates: 1, skipped_not_available: 40 })])).toBe("12 new jobs, 3 added to jobs already in your list, 1 possible duplicate, 40 skipped (not open to Finland)");
  });
  it("handles nothing due", () => expect(feedSyncSummary([])).toBe("All feeds were checked recently. Nothing is due yet."));
  it("includes named errors unchanged", () => expect(feedSyncSummary([result({ error: "The feed could not be read." })])).toBe("Remotive: The feed could not be read."));
  it("shows future checks as future relative time", () => expect(nextCheckRelative("2026-11-10T18:15:00Z", Date.parse("2026-11-10T17:15:00Z"))).toBe("in 1 hour"));
});