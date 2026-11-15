import type { ReactNode } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { realApi } from "@/api/real";
import { api } from "@/api";
import { getToken, onAuthRequired, setToken } from "@/api/auth-token";
import { buildOutcome, buildSendEmail, integrationsPollInterval, POLL_MS } from "@/lib/account";
import type { IntegrationsStatus, PackageRead } from "@/api/types";

const navigate = vi.fn();
vi.mock("@tanstack/react-router", async (original) => ({
  ...(await original<typeof import("@tanstack/react-router")>()),
  Link: ({ children }: { children: ReactNode }) => <a>{children}</a>,
  useRouter: () => ({ navigate }),
}));

const { AuthGate } = await import("@/components/auth/auth-gate");
const { NotificationList } = await import("@/components/notifications/notification-list");
const { SendEmailDialog } = await import("@/components/applications/gmail-actions");
const { PolishControl } = await import("@/components/applications/polish");
const { DeviceCodePanel } = await import("@/components/settings/connected-accounts-card");

const wrap = (ui: ReactNode) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
};
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;
beforeEach(() => setToken(null));
afterEach(() => { vi.restoreAllMocks(); setToken(null); window.sessionStorage.clear(); });

describe("sign-in token", () => {
  it("is kept in sessionStorage, not localStorage", () => {
    setToken("tok-1");
    expect(window.sessionStorage.getItem("duuniscript-token")).toBe("tok-1");
    expect(window.localStorage?.getItem?.("duuniscript-token") ?? null).toBeNull(); // Node 26: may be undefined
  });

  it("is attached to JSON requests and blob downloads", async () => {
    setToken("tok-2");
    const f = vi.spyOn(globalThis, "fetch").mockImplementation(async () => json({ items: [], total: 0, limit: 50, offset: 0 }));
    await realApi.listJobs();
    f.mockResolvedValueOnce(new Response("zip", { status: 200 }));
    await realApi.downloadPackageZip("app-1");
    for (const call of f.mock.calls) expect(new Headers((call[1] as RequestInit).headers).get("Authorization")).toBe("Bearer tok-2");
  });

  it("a 401 auth_required clears the token and signals sign-in", async () => {
    setToken("old");
    const seen = vi.fn();
    const off = onAuthRequired(seen);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(json({ error: { code: "auth_required", message: "Sign in.", details: {} } }, 401));
    await expect(realApi.getProfile()).rejects.toMatchObject({ code: "auth_required" });
    expect(seen).toHaveBeenCalledOnce();
    expect(getToken()).toBeNull();
    off();
  });

  it("shows the Sign in page in place of the current page after a 401", async () => {
    vi.spyOn(api, "authStatus").mockResolvedValue({ password_set: true, signed_in: true });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(json({ error: { code: "auth_required", message: "Sign in.", details: {} } }, 401));
    wrap(<AuthGate><p>Jobs page</p></AuthGate>);
    expect(await screen.findByText("Jobs page")).toBeInTheDocument();
    await act(async () => { await realApi.listJobs().catch(() => {}); });
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByText("Jobs page")).not.toBeInTheDocument();
  });
});

describe("Microsoft device sign-in polling", () => {
  const base = (status: IntegrationsStatus["microsoft_sign_in"]["status"], gmail = false): IntegrationsStatus => ({
    google: { configured: true, connected: gmail, account: null, connected_at: null, last_sync_at: null, last_error: null },
    microsoft: { configured: true, connected: status === "connected", account: null, connected_at: null, last_sync_at: null, last_error: null },
    microsoft_sign_in: { status, user_code: "ABCD1234", verification_uri: "https://example.com/device", expires_at: null, message: status === "failed" ? "The university must approve the app." : null },
  });
  it("polls every 3 s while waiting and stops on connected or failed", () => {
    expect(integrationsPollInterval(base("waiting"), null)).toBe(POLL_MS);
    expect(integrationsPollInterval(base("connected"), null)).toBe(false);
    expect(integrationsPollInterval(base("failed"), null)).toBe(false);
  });
  it("polls for Gmail only until connected or 5 minutes pass", () => {
    expect(integrationsPollInterval(base("idle"), 10_000, 5_000)).toBe(POLL_MS);
    expect(integrationsPollInterval(base("idle", true), 10_000, 5_000)).toBe(false);
    expect(integrationsPollInterval(base("idle"), 10_000, 11_000)).toBe(false);
  });
  it("shows the code while waiting and the message when failed", () => {
    const { rerender } = render(<DeviceCodePanel s={base("waiting").microsoft_sign_in} />);
    expect(screen.getByTestId("device-code")).toHaveTextContent("ABCD1234");
    rerender(<DeviceCodePanel s={base("failed").microsoft_sign_in} />);
    expect(screen.getByRole("alert")).toHaveTextContent("The university must approve the app.");
  });
});

describe("notifications", () => {
  const item = { id: "n1", kind: "good_match" as const, entity_type: "job" as const, entity_id: "j1", title: "Good match", message: "Sample", link: "/jobs/j1", created_at: "2026-11-14T10:00:00Z", read_at: null, dismissed_at: null };
  it("clicking marks read and navigates; × dismisses", async () => {
    const read = vi.spyOn(api, "readNotification").mockResolvedValue();
    const dismiss = vi.spyOn(api, "dismissNotification").mockResolvedValue();
    wrap(<NotificationList items={[item]} />);
    fireEvent.click(screen.getByRole("button", { name: /Sample/ }));
    await waitFor(() => expect(read).toHaveBeenCalledWith("n1", expect.anything()));
    expect(navigate).toHaveBeenCalledWith({ href: "/jobs/j1" });
    fireEvent.click(screen.getByRole("button", { name: "Dismiss: Good match" }));
    await waitFor(() => expect(dismiss).toHaveBeenCalledWith("n1", expect.anything()));
  });
  it("real API uses the read, read-all and dismiss endpoints", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(null, { status: 204 }));
    await realApi.readNotification("n1"); await realApi.readAllNotifications(); await realApi.dismissNotification("n1");
    expect(f.mock.calls.map((c) => `${(c[1] as RequestInit).method} ${new URL(String(c[0])).pathname}`)).toEqual([
      "POST /api/v1/notifications/n1/read", "POST /api/v1/notifications/read-all", "POST /api/v1/notifications/n1/dismiss",
    ]);
  });
});

describe("outcome", () => {
  it("builds the payload and Clear sends outcome null", async () => {
    expect(buildOutcome("interview", "2026-11-14")).toEqual({ outcome: "interview", outcome_on: "2026-11-14" });
    expect(buildOutcome("", "2026-11-14")).toEqual({ outcome: null });
    const f = vi.spyOn(globalThis, "fetch").mockImplementation(async () => json({}));
    await realApi.setOutcome("a1", { outcome: "offer", outcome_on: "2026-11-14" });
    expect((f.mock.calls[0]![1] as RequestInit).method).toBe("PUT");
    expect(JSON.parse(String((f.mock.calls[0]![1] as RequestInit).body))).toEqual({ outcome: "offer", outcome_on: "2026-11-14" });
  });
});

describe("send from Gmail", () => {
  const pkg: PackageRead = { employer: "Esimerkki Oy", role: "Tester", destination: null, contact_emails: ["jobs@example.com"], files: [{ filename: "cv.pdf", sha256: "abc" }], package_hash: "hash-1", cover_letter_text: null } as unknown as PackageRead;
  it("needs the checkbox and sends confirm and package_hash once", async () => {
    const send = vi.spyOn(api, "sendEmail").mockRejectedValue(Object.assign(new Error("Check your Sent folder."), {}));
    wrap(<SendEmailDialog appId="a1" pkg={pkg} account="test@example.com" onOpenChange={() => {}} onSent={() => {}} />);
    expect(screen.getByLabelText("Recipient")).toHaveValue("jobs@example.com");
    const btn = screen.getByRole("button", { name: "Send email" });
    expect(btn).toBeDisabled();
    fireEvent.click(screen.getByLabelText("I checked the recipient and the documents"));
    expect(btn).toBeEnabled();
    fireEvent.click(btn);
    await waitFor(() => expect(send).toHaveBeenCalledWith("a1", { confirm: true, package_hash: "hash-1", to: "jobs@example.com" }));
    await waitFor(() => expect(btn).toBeDisabled());
    expect(send).toHaveBeenCalledTimes(1);
  });
  it("leaves the recipient empty when the posting has several addresses", () => {
    wrap(<SendEmailDialog appId="a1" pkg={{ ...pkg, contact_emails: ["a@example.com", "b@example.com"] }} account="x" onOpenChange={() => {}} onSent={() => {}} />);
    expect(screen.getByLabelText("Recipient")).toHaveValue("");
    expect(buildSendEmail("h", " a@example.com ")).toEqual({ confirm: true, package_hash: "h", to: "a@example.com" });
  });
});

describe("AI wording suggestion", () => {
  it("is only put in the editor, never saved", async () => {
    vi.spyOn(api, "getAi").mockResolvedValue({ enabled: true, model: "m", reachable: true, message: null, embedding_model: "search", embeddings_reachable: true, facts_indexed: 2, jobs_indexed: 3 });
    vi.spyOn(api, "polishDraft").mockResolvedValue({ suggestion: "Better text", issues: [] });
    const save = vi.spyOn(api, "saveDraft");
    const onUse = vi.fn();
    wrap(<PolishControl appId="a1" kind="cv" current="Old text" onUse={onUse} />);
    fireEvent.click(await screen.findByRole("button", { name: "Suggest wording" }));
    fireEvent.click(await screen.findByRole("button", { name: "Use this text" }));
    expect(onUse).toHaveBeenCalledWith("Better text");
    expect(save).not.toHaveBeenCalled();
  });
  it("shows Local AI is off when not reachable", async () => {
    vi.spyOn(api, "getAi").mockResolvedValue({ enabled: false, model: null, reachable: false, message: "Ollama is not running.", embedding_model: null, embeddings_reachable: false, facts_indexed: 0, jobs_indexed: 0 });
    wrap(<PolishControl appId="a1" kind="cv" current="" onUse={() => {}} />);
    expect(await screen.findByText("Local AI is off")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Suggest wording" })).not.toBeInTheDocument();
  });
});
