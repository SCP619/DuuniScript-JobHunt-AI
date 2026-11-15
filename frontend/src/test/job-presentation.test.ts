import { describe, expect, it } from "vitest";
import { languageLabel, originalPostingUrl } from "@/lib/job-presentation";
import type { JobListingRead } from "@/api/types";

describe("posting language labels", () => {
  it.each([["en", "English"], ["fi", "Finnish"], ["sv", "Swedish"], ["en-GB", "English"], ["FI-fi", "Finnish"], ["sv-SE", "Swedish"], ["de", "DE"], ["pt-BR", "PT-BR"], [null, null]])("labels %s as %s", (code, label) => {
    expect(languageLabel(code)).toBe(label);
  });
});

const listing = (url: string | null): JobListingRead => ({
  source_key: "sample", source_name: "Sample source", source_url: url, external_id: null,
  source_published_on: null, first_seen_at: "2026-11-10T00:00:00Z", last_seen_at: "2026-11-10T00:00:00Z",
  listing_status: "active", captured_at: null, parser_version: null,
});

describe("original posting URL", () => {
  it("prefers canonical_url", () => {
    expect(originalPostingUrl({ canonical_url: "https://canonical.example/job", listings: [listing("https://source.example/job")] })).toBe("https://canonical.example/job");
  });
  it("uses the first non-null listing URL", () => {
    expect(originalPostingUrl({ canonical_url: null, listings: [listing(null), listing("https://first.example/job"), listing("https://second.example/job")] })).toBe("https://first.example/job");
  });
  it("returns none when no URL is saved", () => {
    expect(originalPostingUrl({ canonical_url: null, listings: [listing(null)] })).toBeNull();
    expect(originalPostingUrl({ canonical_url: null, listings: [] })).toBeNull();
  });
});