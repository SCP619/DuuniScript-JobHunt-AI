import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/api";
import { realApi } from "@/api/real";
import { mockApi } from "@/api/mock";
import { setToken } from "@/api/auth-token";
import type { AiStatus, JobMatchRead, ScreenshotDraftRead } from "@/api/job-additions";
import { ScreenshotImport, ScreenshotReview } from "@/components/jobs/screenshot-import";
import { ApplyYourselfTag } from "@/components/jobs/job-bits";
import { LocalAiCard, LocalAiStatus } from "@/components/settings/local-ai-card";
import { toast } from "sonner";

vi.mock("@tanstack/react-router", async (original) => ({ ...(await original<typeof import("@tanstack/react-router")>()), Link: ({ children }: { children: ReactNode }) => <a>{children}</a> }));
const { MatchDetails } = await import("@/components/jobs/match");
const wrap = (ui: ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{ui}</QueryClientProvider>);
const draft: ScreenshotDraftRead = { fields: { title: "Sample role", company: "Example employer", location: "Turku", description: "<b>Not HTML</b>", added_from: "screenshots", apply_manually: true }, method: "ai", text: "<script>no execution</script>", warnings: ["Check the employer."], images: 2 };
const ai: AiStatus = { enabled: true, model: "qwen2.5:7b", reachable: true, message: null, embedding_model: "bge-m3", embeddings_reachable: true, facts_indexed: 7, jobs_indexed: 12 };
beforeEach(() => { vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} unobserve() {} }); vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test"); vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {}); });
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); setToken(null); });

describe("screenshots", () => {
  it("sends repeated files in order with bearer authentication", async () => {
    setToken("screenshot-test-token");
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(draft)));
    await realApi.readJobScreenshots([new File(["2"], "second.png", { type: "image/png" }), new File(["1"], "first.jpg", { type: "image/jpeg" })]);
    const init = f.mock.calls[0]?.[1];
    expect(String(f.mock.calls[0]?.[0])).toContain("/api/v1/jobs/from-screenshots");
    expect(init?.method).toBe("POST");
    expect((init?.body as FormData).getAll("files").map((file) => (file as File).name)).toEqual(["second.png", "first.jpg"]);
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer screenshot-test-token");
    expect(new Headers(init?.headers).has("Content-Type")).toBe(false);
    expect(init?.signal).toBeInstanceOf(AbortSignal);
  });
  it("prefills editable fields, shows warnings and saves only on explicit Save", async () => {
    const result = await mockApi.getJob((await mockApi.listJobs()).items[0]?.id ?? "");
    const save = vi.spyOn(api, "createJob").mockResolvedValue(result);
    wrap(<ScreenshotReview draft={draft} onSaved={() => {}} />);
    expect(screen.getByLabelText(/Job title/)).toHaveValue("Sample role");
    expect(screen.getByLabelText(/Company/)).toHaveValue("Example employer");
    expect(screen.getByLabelText("Description")).toHaveValue("<b>Not HTML</b>");
    expect(screen.getByRole("note")).toHaveTextContent("Check the employer.");
    expect(save).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText(/Job title/), { target: { value: "Edited role" } });
    fireEvent.change(screen.getByLabelText("Link to the posting"), { target: { value: "https://example.com/posting" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(save).toHaveBeenCalledOnce());
    expect(save.mock.calls[0]?.[0]).toMatchObject({ title: "Edited role", url: "https://example.com/posting", description: "<b>Not HTML</b>", added_from: "screenshots", apply_manually: true });
  });
  it("permits opting out of Apply yourself in the save payload", async () => {
    const save = vi.spyOn(api, "createJob").mockRejectedValue(new ApiError(422, "validation_error", "Check fields."));
    wrap(<ScreenshotReview draft={draft} onSaved={() => {}} />);
    fireEvent.click(screen.getByRole("checkbox")); fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(save.mock.calls[0]?.[0]).toMatchObject({ added_from: "screenshots", apply_manually: false }));
  });
  it("keeps text-only response editable without inventing title or employer", () => {
    wrap(<ScreenshotReview draft={{ ...draft, fields: { title: "", company: "", description: "read text", added_from: "screenshots", apply_manually: true }, method: "text_only" }} onSaved={() => {}} />);
    expect(screen.getByLabelText(/Job title/)).toHaveValue(""); expect(screen.getByLabelText(/Company/)).toHaveValue("");
    expect(screen.getByText(/only the text was read/)).toBeInTheDocument();
    expect(screen.getByText("<script>no execution</script>").tagName).toBe("PRE");
  });
  it("reorders and removes files before reading and never creates automatically", async () => {
    const read = vi.spyOn(api, "readJobScreenshots").mockResolvedValue(draft);
    const save = vi.spyOn(api, "createJob");
    wrap(<ScreenshotImport onSaved={() => {}} />);
    fireEvent.change(screen.getByLabelText("Screenshot files"), { target: { files: [new File(["a"], "a.png", { type: "image/png" }), new File(["b"], "b.jpg", { type: "image/jpeg" }), new File(["c"], "c.png", { type: "image/png" })] } });
    fireEvent.click(screen.getByLabelText("Move screenshot 2 up")); fireEvent.click(screen.getByLabelText("Remove screenshot 3"));
    fireEvent.click(screen.getByRole("button", { name: "Read screenshots" }));
    await screen.findByLabelText(/Job title/);
    expect(read.mock.calls[0]?.[0].map((f) => f.name)).toEqual(["b.jpg", "a.png"]);
    expect(save).not.toHaveBeenCalled();
  });
  it("rejects more than ten files without sending a request", () => {
    const read = vi.spyOn(api, "readJobScreenshots");
    wrap(<ScreenshotImport onSaved={() => {}} />);
    fireEvent.change(screen.getByLabelText("Screenshot files"), { target: { files: Array.from({ length: 11 }, (_, n) => new File(["x"], `${n}.png`, { type: "image/png" })) } });
    expect(screen.getByRole("alert")).toHaveTextContent("up to 10"); expect(read).not.toHaveBeenCalled();
  });
  it.each([[409, "ocr_unavailable"], [409, "no_text_found"], [413, "too_large"], [415, "unsupported_type"], [422, "too_many_files"]])("shows the API message for %s %s", async (status, code) => {
    vi.spyOn(api, "readJobScreenshots").mockRejectedValue(new ApiError(Number(status), String(code), "Specific local API message."));
    wrap(<ScreenshotImport onSaved={() => {}} />);
    fireEvent.change(screen.getByLabelText("Screenshot files"), { target: { files: [new File(["a"], "a.png", { type: "image/png" })] } });
    fireEvent.click(screen.getByRole("button", { name: "Read screenshots" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Specific local API message.");
  });
  it("mock read does not save, but explicit create registers screenshot source and flag", async () => {
    const before = (await mockApi.listJobs()).total;
    const read = await mockApi.readJobScreenshots([new File(["x"], "x.png", { type: "image/png" })]);
    expect((await mockApi.listJobs()).total).toBe(before);
    const job = await mockApi.createJob(read.fields);
    expect(job.sources).toContain("screenshot_import"); expect(job.apply_manually).toBe(true);
    const updated = await mockApi.updateJob(job.id, { apply_manually: false }); expect(updated.apply_manually).toBe(false);
  });
});

describe("Apply yourself and match parts", () => {
  it("shows the hand tag only for flagged jobs", () => {
    const { rerender } = render(<ApplyYourselfTag value={true} />);
    expect(screen.getByText("Apply yourself")).toBeInTheDocument(); rerender(<ApplyYourselfTag value={false} />); expect(screen.queryByText("Apply yourself")).toBeNull();
  });
  it("sends the detail toggle as PATCH apply_manually", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));
    await realApi.updateJob("j1", { apply_manually: true });
    expect(f.mock.calls[0]?.[1]).toMatchObject({ method: "PATCH", body: '{"apply_manually":true}' });
  });
  it("shows API semantic and signed learned values, hides null/zero", () => {
    const match: JobMatchRead = { job_id: "j", score: 70, scoring_version: "sample", reasons: [], blockers: [], matched_skills: [], missing_terms: [], computed_at: "", parts: { skills: 40, role: 10, wording: 5, semantic: 20, learned: 10 } };
    const { rerender } = render(<MatchDetails match={match} />);
    expect(screen.getByText("20/20")).toBeInTheDocument(); expect(screen.getByText("+10")).toBeInTheDocument();
    rerender(<MatchDetails match={{ ...match, parts: { ...match.parts, learned: -10 } }} />); expect(screen.getByText("−10")).toBeInTheDocument();
    rerender(<MatchDetails match={{ ...match, parts: { ...match.parts, semantic: null, learned: 0 } }} />);
    expect(screen.queryByText(/Meaning \(/)).toBeNull(); expect(screen.queryByText("Learned from your decisions")).toBeNull();
  });
});

describe("Local AI", () => {
  it("shows model readiness and exact index counts", () => {
    render(<LocalAiStatus status={ai} />);
    expect(screen.getByText("Writing model: qwen2.5:7b — ready")).toBeInTheDocument(); expect(screen.getByText("Search model: bge-m3 — ready")).toBeInTheDocument(); expect(screen.getByText("Search index: 7 facts, 12 jobs")).toBeInTheDocument();
  });
  it("shows off/unreachable API status rather than readiness", () => {
    render(<LocalAiStatus status={{ ...ai, enabled: false, reachable: false, message: "Ollama is not running.", embeddings_reachable: false }} />);
    expect(screen.getByText(/Ollama is not running/)).toBeInTheDocument(); expect(screen.getByText("Search model: bge-m3 — unavailable")).toBeInTheDocument();
  });
  it("updates the index only when clicked and reports the returned counts", async () => {
    vi.spyOn(api, "getAi").mockResolvedValue(ai); const update = vi.spyOn(api, "indexAi").mockResolvedValue({ available: true, facts: 9, jobs: 14 }); const notice = vi.spyOn(toast, "success");
    wrap(<LocalAiCard />); const button = await screen.findByRole("button", { name: "Update search index" }); expect(update).not.toHaveBeenCalled(); fireEvent.click(button);
    await waitFor(() => expect(notice).toHaveBeenCalledWith("Indexed 9 facts and 14 jobs"));
  });
  it("uses the local AI index endpoint", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response('{"available":true,"facts":9,"jobs":14}'));
    expect(await realApi.indexAi()).toEqual({ available: true, facts: 9, jobs: 14 }); expect(String(f.mock.calls[0]?.[0])).toContain("/api/v1/ai/index"); expect(f.mock.calls[0]?.[1]?.method).toBe("POST");
  });
});