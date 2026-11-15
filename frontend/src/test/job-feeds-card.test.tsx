import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { FeedsStatus } from "@/api/types";
import { ApiError } from "@/api/errors";

const getFeeds = vi.fn(), updateSource = vi.fn(), syncFeeds = vi.fn(), syncFeed = vi.fn();
vi.mock("@/api", async (orig) => ({ ...(await orig<typeof import("@/api")>()), api: { getFeeds, updateSource, syncFeeds, syncFeed } }));
const { JobFeedsCard } = await import("@/components/settings/job-feeds-card");
const { FeedAttribution } = await import("@/components/jobs/feed-attribution");
const base: FeedsStatus = { check_interval_minutes: 30, skip_unavailable: true, keywords: ["developer"], feeds: [{ key: "feed_remotive", name: "Remotive sample", domain: "example.com", enabled: true, access_method: "rss", terms_url: "https://example.com/terms", attribution: "Sample jobs from Remotive.", min_interval_hours: 6, last_success_at: null, last_error_at: null, last_error: null, next_allowed_at: null, jobs: 12 }] };
function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(<QueryClientProvider client={client}><JobFeedsCard /></QueryClientProvider>);
  return invalidate;
}
const desktop = () => within(screen.getByRole("table"));
describe("job feeds controls", () => {
  beforeEach(() => { vi.clearAllMocks(); getFeeds.mockResolvedValue(base); });
  it("healthy feeds have no warning", async () => {
    show(); await screen.findByRole("table");
    expect(screen.queryByRole("alert")).toBeNull();
  });
  it("shows the returned feed error as a warning", async () => {
    getFeeds.mockResolvedValue({ ...base, feeds: [{ ...base.feeds[0], last_error: "The sample site is unavailable." }] });
    show(); await screen.findByRole("table");
    expect(desktop().getByRole("alert")).toHaveTextContent("The sample site is unavailable.");
  });
  it("switch sends enabled false and refreshes both cards", async () => {
    updateSource.mockResolvedValue({ enabled: false });
    const invalidate = show();
    await screen.findByRole("table");
    fireEvent.click(desktop().getByRole("switch", { name: "Enable Remotive sample" }));
    await waitFor(() => expect(updateSource).toHaveBeenCalledWith("feed_remotive", { enabled: false }));
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["feeds"] }));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["sources"] });
    expect(getFeeds.mock.calls.length).toBeGreaterThan(1);
  });
  it("disabled feed cannot be checked", async () => {
    getFeeds.mockResolvedValue({ ...base, feeds: [{ ...base.feeds[0], enabled: false }] });
    show(); await screen.findByRole("table");
    expect(desktop().getByRole("button", { name: "Check Remotive sample" })).toBeDisabled();
  });
  it("future next_allowed_at disables per-feed check", async () => {
    getFeeds.mockResolvedValue({ ...base, feeds: [{ ...base.feeds[0], next_allowed_at: new Date(Date.now() + 3600000).toISOString() }] });
    show(); await screen.findByRole("table");
    expect(desktop().getByRole("button", { name: "Check Remotive sample" })).toBeDisabled();
  });
  it("nothing due refreshes the card", async () => {
    syncFeeds.mockResolvedValue([]); show();
    fireEvent.click(await screen.findByRole("button", { name: "Check now" }));
    await screen.findByRole("status");
    expect(syncFeeds).toHaveBeenCalledTimes(1);
    expect(getFeeds.mock.calls.length).toBeGreaterThan(1);
  });
  it("429 leaves the API message visible", async () => {
    syncFeed.mockRejectedValue(new ApiError(429, "too_soon", "Wait before checking this feed.")); show();
    await screen.findByRole("table"); fireEvent.click(desktop().getByRole("button", { name: "Check Remotive sample" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Wait before checking this feed.");
  });
  it("uses only matching feed attribution, not non-feed sources", () => {
    const { container } = render(<FeedAttribution sourceKey="feed_remotive" feeds={base.feeds} />);
    expect(container.textContent).toBe(base.feeds[0]?.attribution);
    const { container: other } = render(<FeedAttribution sourceKey="alert_linkedin" feeds={base.feeds} />);
    expect(other.textContent).toBe("");
  });
});