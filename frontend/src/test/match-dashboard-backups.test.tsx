import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { realApi } from "@/api/real";
import { mockApi } from "@/api/mock";
import type { DashboardSummary, DocumentRead } from "@/api/types";
import type { JobMatchRead } from "@/api/job-additions";

vi.mock("@tanstack/react-router", async (original) => ({
  ...(await original<typeof import("@tanstack/react-router")>()),
  Link: ({ children }: { children: ReactNode }) => <a>{children}</a>,
}));

const { MatchDetails } = await import("@/components/jobs/match");
const { DashboardJobSection, DashboardStatusStrip } = await import("@/components/dashboard/dashboard-sections");
const { ExtractionState } = await import("@/routes/documents");

afterEach(() => vi.restoreAllMocks());

describe("match requests and display", () => {
  it("sends best-match sorting and minimum score as query params", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ items: [], total: 0, limit: 25, offset: 0 })));
    await realApi.listJobs({ sort: "match", min_match: 60 });
    const url = new URL(String(fetchMock.mock.calls[0]?.[0]));
    expect(url.searchParams.get("sort")).toBe("match");
    expect(url.searchParams.get("min_match")).toBe("60");
  });

  it("mock sorts by score and filters out lower and unscored jobs", async () => {
    const result = await mockApi.listJobs({ sort: "match", min_match: 60, limit: 200 });
    expect(result.items.length).toBeGreaterThan(0);
    expect(result.items.every((j) => j.match_score !== null && j.match_score >= 60)).toBe(true);
    const scores = result.items.map((j) => j.match_score!);
    expect(scores).toEqual([...scores].sort((a, b) => b - a));
  });

  const match: JobMatchRead = {
    job_id: "job-1", score: 82, scoring_version: "v1", reasons: ["Relevant verified skills."],
    matched_skills: ["TypeScript"], missing_terms: ["Kubernetes"],
    blockers: [{ code: "language_required", message: "The posting requires a language not covered by verified facts." }],
    parts: { skills: 49, role: 21, wording: 12, semantic: null, learned: 0 }, computed_at: "2026-11-10T12:00:00Z",
  };

  it("renders blockers returned by the API", () => {
    render(<MatchDetails match={match} />);
    expect(screen.getByText(match.blockers[0]!.message)).toBeInTheDocument();
    expect(screen.getByText("49/60")).toBeInTheDocument();
    expect(screen.getByText("Kubernetes")).toBeInTheDocument();
  });

  it("handles a null score without bars or fabricated reasons", () => {
    render(<MatchDetails match={{ ...match, score: null, blockers: [], reasons: [], matched_skills: [], missing_terms: [], parts: { skills: 0, role: 0, wording: 0, semantic: null, learned: 0 } }} />);
    expect(screen.getByText(/Verify some profile facts/)).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).toBeNull();
    expect(screen.queryByText("Relevant verified skills.")).toBeNull();
  });
});

describe("dashboard empty and failing-source states", () => {
  it("shows both requested empty states", () => {
    render(<><DashboardJobSection title="Deadlines this week" jobs={[]} empty="No deadlines in the next 7 days." deadlines /><DashboardJobSection title="Best matches" jobs={[]} empty="No scored jobs yet." /></>);
    expect(screen.getByText("No deadlines in the next 7 days.")).toBeInTheDocument();
    expect(screen.getByText("No scored jobs yet.")).toBeInTheDocument();
  });

  it("shows failing sources in warning content", () => {
    const status: DashboardSummary["status"] = { last_source_check_at: null, sources_turned_off: [], sources_failing: ["Remotive sample"], last_backup_at: null, automatic_backups: true };
    render(<DashboardStatusStrip status={status} />);
    expect(screen.getByText(/Could not check: Remotive sample/)).toBeInTheDocument();
    expect(screen.getByText(/Last checked Not checked yet/)).toBeInTheDocument();
  });
});

describe("backup deletion", () => {
  it("sends confirm=true and escapes the backup name", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    await realApi.deleteBackup("sample backup.zip", true);
    const url = new URL(String(fetchMock.mock.calls[0]?.[0]));
    expect(url.pathname).toBe("/api/v1/backups/sample%20backup.zip");
    expect(url.searchParams.get("confirm")).toBe("true");
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ method: "DELETE" });
  });
});

const document = (method: DocumentRead["extraction_method"], status: DocumentRead["extraction_status"] = "succeeded"): DocumentRead => ({
  id: "doc-1", category: "certificate", display_name: "Sample", original_filename: "sample.jpg", file_extension: "jpg",
  mime_type: "image/jpeg", size_bytes: 1000, sha256: "abc", extraction_status: status, extraction_error: null,
  extracted_char_count: status === "succeeded" ? 20 : 0, extractor_version: "v1", extracted_at: null,
  extraction_method: method, created_at: "2026-11-10T12:00:00Z", updated_at: "2026-11-10T12:00:00Z", archived_at: null,
});

describe("image document labels", () => {
  it("shows the OCR badge only when extraction_method is ocr", () => {
    const { rerender } = render(<ExtractionState doc={document("ocr")} />);
    expect(screen.getByText("Read from an image")).toBeInTheDocument();
    rerender(<ExtractionState doc={document("text")} />);
    expect(screen.queryByText("Read from an image")).toBeNull();
  });

  it("uses the image-specific no-text message", () => {
    render(<ExtractionState doc={document(null, "no_text")} />);
    expect(screen.getByText("No text was found in this image.")).toBeInTheDocument();
  });

  it("mock image upload is marked as OCR", async () => {
    const doc = await mockApi.uploadDocument({ file: new File(["fake image bytes"], "sample.png", { type: "image/png" }), category: "certificate" });
    expect(doc.extraction_method).toBe("ocr");
    expect(doc.mime_type).toBe("image/png");
  });
});
