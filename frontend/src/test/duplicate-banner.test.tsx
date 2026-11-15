import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import type { JobRead } from "@/api/types";

const navigate = vi.fn();
vi.mock("@tanstack/react-router", () => ({ useNavigate: () => navigate, Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a> }));
const toastSuccess = vi.fn();
vi.mock("sonner", () => ({ toast: { success: (m: string) => toastSuccess(m), error: vi.fn() } }));
const getJob = vi.fn(); const mergeJob = vi.fn(); const updateJob = vi.fn();
vi.mock("@/api", async (orig) => ({ ...(await orig<typeof import("@/api")>()), api: { getJob, mergeJob, updateJob } }));
const { DuplicateBanner } = await import("@/components/jobs/duplicate-banner");

const job = (p: Partial<JobRead>) => ({ id: "a", title: "Dev", company: "Co", status: "new", possible_duplicate_of: "b", listings: [], ...p }) as JobRead;
const setup = (otherStatus: string) => {
  getJob.mockResolvedValue(job({ id: "b", title: "Kehittäjä", company: "Esimerkki Oy", status: otherStatus as JobRead["status"], possible_duplicate_of: null }));
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const spy = vi.spyOn(qc, "invalidateQueries");
  render(<QueryClientProvider client={qc}><DuplicateBanner job={job({})} /></QueryClientProvider>);
  return spy;
};

describe("possible duplicate banner", () => {
  it("names the other job as received and warns when already applied", async () => {
    setup("applied");
    expect(await screen.findByText("Kehittäjä — Esimerkki Oy")).toBeInTheDocument();
    expect(screen.getByText("You have already applied to a job that looks like this one.")).toBeInTheDocument();
  });
  it("merges into the other job and opens it", async () => {
    mergeJob.mockResolvedValue(job({ id: "b", possible_duplicate_of: null }));
    const spy = setup("saved");
    await screen.findByText("Kehittäjä — Esimerkki Oy");
    expect(screen.queryByText(/already applied/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Same job — merge" }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith({ to: "/jobs/$id", params: { id: "b" } }));
    expect(mergeJob).toHaveBeenCalledWith("a", "b");
    expect(toastSuccess).toHaveBeenCalledWith("Merged. Its listings, details and notes are now on this job.");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["jobs"] });
  });
  it("dismisses the flag with Not the same", async () => {
    updateJob.mockResolvedValue(job({ possible_duplicate_of: null }));
    const spy = setup("saved");
    fireEvent.click(await screen.findByRole("button", { name: "Not the same" }));
    await waitFor(() => expect(updateJob).toHaveBeenCalledWith("a", { possible_duplicate_of: null }));
    await waitFor(() => expect(spy).toHaveBeenCalledWith({ queryKey: ["jobs"] }));
  });
});
