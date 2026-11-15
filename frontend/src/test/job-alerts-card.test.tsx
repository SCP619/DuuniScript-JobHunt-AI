import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { JobAlertStatus } from "@/api/types";
import { ApiError } from "@/api/errors";

const getJobAlerts = vi.fn();
const syncJobAlerts = vi.fn();
vi.mock("@/api", async (orig) => ({ ...(await orig<typeof import("@/api")>()), api: { getJobAlerts, syncJobAlerts, uploadAlertEmails: vi.fn() } }));
const { JobAlertsCard } = await import("@/components/settings/job-alerts-card");

const base: JobAlertStatus = { configured: true, mailbox: "someone@example.com", folder: "DuuniScript", sync_interval_minutes: 30, last_sync_at: null, last_error_at: null, last_error: null, emails_read: 4, jobs_created: 2, jobs_merged: 1, sites: [{ key: "alert_linkedin", name: "LinkedIn", format_verified: true, emails_read: 4, last_email_at: null }, { key: "alert_monster", name: "Monster", format_verified: false, emails_read: 0, last_email_at: null }] };
const show = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><JobAlertsCard /></QueryClientProvider>);

describe("job alert emails card", () => {
  beforeEach(() => { getJobAlerts.mockReset(); syncJobAlerts.mockReset(); });
  it("shows setup steps and no password field when not set up", async () => {
    getJobAlerts.mockResolvedValue({ ...base, configured: false, mailbox: null, sites: [] });
    const { container } = show();
    expect(await screen.findByText("Job alert emails are not set up yet.")).toBeInTheDocument();
    expect(screen.getByText(/MAIL_IMAP_USER/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Check now" })).toBeNull();
    expect(container.querySelector('input[type="password"]')).toBeNull();
  });
  it("shows the last error as a warning when set up", async () => {
    getJobAlerts.mockResolvedValue({ ...base, last_error: "Gmail refused the app password.", last_error_at: "2026-11-10T10:00:00Z" });
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent("Gmail refused the app password.");
  });
  it("shows a healthy status, sites and the sync summary", async () => {
    getJobAlerts.mockResolvedValue(base);
    syncJobAlerts.mockResolvedValue({ emails_checked: 3, emails_already_read: 0, emails_not_alerts: 0, emails_unverified: 0, emails_without_jobs: 0, jobs_found: 3, jobs_created: 3, jobs_merged: 0, jobs_already_known: 0, possible_duplicates: 0, unreadable_cards: 0 });
    show();
    expect(await screen.findByText("someone@example.com")).toBeInTheDocument();
    expect(screen.getByText("Checks every 30 minutes")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("Format checked")).toBeInTheDocument();
    expect(screen.getByText("Not yet checked")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Check now" }));
    expect(await screen.findByRole("status")).toHaveTextContent("3 new jobs");
  });
  it("shows the API message when a check fails", async () => {
    getJobAlerts.mockResolvedValue(base);
    syncJobAlerts.mockRejectedValue(new ApiError(409, "sync_in_progress", "A check is already running."));
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Check now" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("A check is already running.");
    expect(getJobAlerts.mock.calls.length).toBeGreaterThan(1);
  });
});
