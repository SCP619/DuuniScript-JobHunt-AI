import { describe, expect, it } from "vitest";
import { mockApi } from "@/api/mock";
import { realApi } from "@/api/real";
import { vi } from "vitest";

describe("mock posting-language filter", () => {
  it("en includes both en and en-GB", async () => {
    const page = await mockApi.listJobs({ language: "en" });
    expect(page.items.map((job) => job.language).sort()).toEqual(["en", "en", "en-GB"]);
    expect(page.total).toBe(3);
  });
  it("fi selects Finnish postings", async () => {
    const page = await mockApi.listJobs({ language: "fi" });
    expect(page.items.map((job) => job.language)).toEqual(["fi"]);
    expect(page.total).toBe(1);
  });
  it("unknown selects only null language", async () => {
    const page = await mockApi.listJobs({ language: "unknown" });
    expect(page.total).toBe(4);
    expect(page.items.map((job) => job.language)).toEqual([null, null, null, null]);
  });
});

describe("real language query", () => {
  it("sends the selected language to the local API", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 })));
    try {
      await realApi.listJobs({ language: "fi" });
      expect(fetchMock.mock.calls[0]?.[0]).toBe("http://127.0.0.1:8000/api/v1/jobs?language=fi");
    } finally { fetchMock.mockRestore(); }
  });
});