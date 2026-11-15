import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/app-shell";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { selectInline } from "@/components/field";
import { ApplicationsTable } from "@/components/applications/applications-table";
import { api } from "@/api";
import { APPLICATION_STATUS } from "@/lib/applications";
import type { ApplicationStatus } from "@/api/types";

export const Route = createFileRoute("/applications/")({
  validateSearch: (search: Record<string, unknown>): { status?: ApplicationStatus } => ({
    status: typeof search.status === "string" && search.status in APPLICATION_STATUS ? search.status as ApplicationStatus : undefined,
  }),
  head: () => ({
    meta: [
      { title: "Applications — DuuniScript" },
      { name: "description", content: "Applications you are preparing, ready to send, or have recorded as sent." },
      { property: "og:title", content: "Applications — DuuniScript" },
      { property: "og:description", content: "Applications you are preparing, ready to send, or have recorded as sent." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: ApplicationsPage,
});

function ApplicationsPage() {
  const { status } = Route.useSearch();
  const navigate = Route.useNavigate();
  const params = { status, limit: 200 };
  const q = useQuery({ queryKey: ["applications", params], queryFn: () => api.listApplications(params) });
  return (
    <>
      <PageHeader title="Applications" description="DuuniScript prepares documents; you send the application yourself and record it here." />
      <div className="mb-4">
        <label className="sr-only" htmlFor="app-status">Status</label>
        <select id="app-status" className={selectInline} value={status ?? ""} onChange={(e) => navigate({ search: { status: (e.target.value || undefined) as ApplicationStatus | undefined }, replace: true })}>
          <option value="">All statuses</option>
          {(Object.keys(APPLICATION_STATUS) as ApplicationStatus[]).map((s) => <option key={s} value={s}>{APPLICATION_STATUS[s].label}</option>)}
        </select>
      </div>
      {q.isLoading ? <LoadingState label="Loading applications…" />
        : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} />
        : q.data!.items.length === 0 ? <EmptyState title={status ? "No applications with this status" : "No applications yet"}>{status ? "Try another status." : "No applications yet. Open a job and choose Prepare application."}</EmptyState>
        : <ApplicationsTable items={q.data!.items} caption="Your applications" />}
    </>
  );
}
