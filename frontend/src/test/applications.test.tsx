import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { buildApplicationCreate, buildFactImport, buildSubmission, toRows } from "@/lib/applications";
import { DraftPreview } from "@/components/applications/draft-preview";
import { ApproveControl } from "@/components/applications/approve-control";
import { filenameFromDisposition } from "@/api/http";
import { realApi } from "@/api/real";
import type { FactSuggestion } from "@/api/types";

const sug = (p: Partial<FactSuggestion>): FactSuggestion => ({ already_in_profile: false, category: "skill", excerpt: "x", subject: "S", valid_from: null, valid_until: null, value_text: "V", ...p });

describe("fact suggestion import payload", () => {
  it("sends only checked items with edited values", () => {
    const rows = toRows([sug({ subject: "React" }), sug({ subject: "MSc", already_in_profile: true }), sug({ subject: "Go" })]);
    expect(rows.map((r) => r.checked)).toEqual([true, false, true]);
    rows[0] = { ...rows[0]!, subject: "React (edited)", valid_from: "2020-01-01" };
    rows[2] = { ...rows[2]!, checked: false };
    expect(buildFactImport("doc-1", rows)).toEqual({
      document_id: "doc-1",
      items: [{ category: "skill", subject: "React (edited)", value_text: "V", valid_from: "2020-01-01", valid_until: null, excerpt: "x" }],
    });
  });
});

describe("API calls", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("bulk verify posts the selected fact ids", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ verified: 2, facts: [] }), { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    await realApi.verifyFacts(["a", "b"]);
    const [url, init] = fetch.mock.calls[0]!;
    expect(url).toMatch(/\/api\/v1\/profile\/facts\/verify$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ fact_ids: ["a", "b"] });
  });
  it("reads the UTF-8 download filename first", () => {
    expect(filenameFromDisposition(`attachment; filename="cv.pdf"; filename*=UTF-8''Ty%C3%B6hakemus.pdf`, "x")).toBe("Työhakemus.pdf");
    expect(filenameFromDisposition(`attachment; filename="cv.pdf"`, "x")).toBe("cv.pdf");
  });
});

describe("application create payload", () => {
  const base = { cvTemplate: "classic", cvDocumentId: "doc-9", includeLetter: true, letterTemplate: "standard" };
  it("builds from verified facts with a template", () => {
    expect(buildApplicationCreate("job-1", { ...base, cvSource: "generated" })).toEqual({ job_id: "job-1", cv_source: "generated", cv_template: "classic", include_cover_letter: true, letter_template: "standard" });
  });
  it("uses an uploaded CV as it is", () => {
    expect(buildApplicationCreate("job-1", { ...base, cvSource: "uploaded", includeLetter: false })).toEqual({ job_id: "job-1", cv_source: "uploaded", cv_document_id: "doc-9", include_cover_letter: false });
  });
});

describe("approve with warnings", () => {
  it("sends acknowledge_warnings: true only after the checkbox", async () => {
    const onApprove = vi.fn().mockResolvedValue(undefined);
    render(<ApproveControl label="Approve CV" issues={[{ severity: "warning", code: "c", message: "Unbacked claim", excerpt: "5 years" }]} onApprove={onApprove} />);
    fireEvent.click(screen.getByRole("button", { name: "Approve CV" }));
    await screen.findByText("I checked these statements and they are true");
    const confirm = screen.getAllByRole("button", { name: "Approve CV" }).at(-1)!;
    expect(confirm).toBeDisabled();
    fireEvent.click(confirm);
    expect(onApprove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText("I checked these statements and they are true"));
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);
    await waitFor(() => expect(onApprove).toHaveBeenCalledWith(true));
  });
  it("is disabled while errors exist", () => {
    render(<ApproveControl label="Approve CV" issues={[{ severity: "error", code: "p", message: "Placeholder" }]} onApprove={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Approve CV" })).toBeDisabled();
  });
});

describe("submission payload", () => {
  it("includes the package hash and confirm", () => {
    expect(buildSubmission("abc123", "email", "  REF-1 ")).toEqual({ confirm: true, package_hash: "abc123", method: "email", confirmation_reference: "REF-1" });
    expect(buildSubmission("abc123", "web_form", "").confirmation_reference).toBeNull();
  });
});

describe("draft preview", () => {
  it("renders <script> as text, never as an element", () => {
    const { container } = render(<DraftPreview content={"# Test Person\n## Skills\n- <script>alert(1)</script>\n<b>bold?</b>"} />);
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(screen.getByText("<script>alert(1)</script>")).toBeInTheDocument();
    expect(screen.getByText("<b>bold?</b>")).toBeInTheDocument();
    expect(screen.getByText("Test Person")).toBeInTheDocument();
  });
});
