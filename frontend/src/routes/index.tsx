import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, X } from "lucide-react";
import { useState } from "react";
import { NOTIFICATIONS_KEY, NotificationList } from "@/components/notifications/notification-list";
import { AUTH_KEY } from "@/components/auth/auth-gate";
import type { ReactNode } from "react";
import { PageHeader } from "@/components/app-shell";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { StatusBadge } from "@/components/status-badge";
import { ApplyYourselfTag, Deadline, JobStatusBadge } from "@/components/jobs/job-bits";
import { DashboardJobSection, DashboardStatusStrip } from "@/components/dashboard/dashboard-sections";
import { api } from "@/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Dashboard — DuuniScript" },
      { name: "description", content: "An overview of your job search: matches, deadlines, applications and recent postings." },
      { property: "og:title", content: "Dashboard — DuuniScript" },
      { property: "og:description", content: "An overview of your job search: matches, deadlines, applications and recent postings." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Dashboard,
});

function Dashboard() {
  const summary = useQuery({ queryKey: ["dashboard"], queryFn: api.getDashboard });
  const recent = useQuery({ queryKey: ["jobs", { sort: "newest", limit: 5 }], queryFn: () => api.listJobs({ sort: "newest", limit: 5 }) });
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const auth = useQuery({ queryKey: AUTH_KEY, queryFn: api.authStatus });
  const notes = useQuery({ queryKey: NOTIFICATIONS_KEY, queryFn: api.listNotifications, refetchInterval: 60_000 });
  const [bannerHidden, setBannerHidden] = useState(false);
  const attention = (notes.data?.items ?? []).filter((n) => !n.read_at).slice(0, 3);
  const s = summary.data;

  return (
    <>
      <PageHeader title="Dashboard" description="Where your job search stands today." />

      {auth.data?.password_set === false && !bannerHidden && (
        <div role="note" className="mb-6 flex items-start gap-3 rounded-lg border border-warning/40 bg-warning-soft p-4 text-sm">
          <p className="mr-auto">Anyone using this computer can open DuuniScript. <Link to="/settings" className="font-medium underline">Create a sign-in passphrase in Settings.</Link></p>
          <button type="button" aria-label="Dismiss this message" className="rounded p-0.5 hover:bg-background/50 focus-visible:outline-2 focus-visible:outline-ring" onClick={() => setBannerHidden(true)}><X aria-hidden className="size-4" /></button>
        </div>
      )}

      {(notes.data?.unread ?? 0) > 0 && attention.length > 0 && (
        <section aria-labelledby="attention-h" className="mb-6 rounded-lg border bg-card px-4 pt-3">
          <h2 id="attention-h" className="text-lg font-medium">Needs your attention</h2>
          <NotificationList items={attention} />
        </section>
      )}

      <div className="mb-6 flex flex-wrap items-center gap-2 text-sm" aria-live="polite">
        <span className="text-muted-foreground">Backend:</span>
        {health.isLoading ? <span className="text-muted-foreground">Checking…</span>
          : health.isError ? <StatusBadge tone="danger" label="Not reachable" />
          : <>
              <StatusBadge tone={health.data!.status === "ok" ? "success" : "warning"} label={health.data!.status === "ok" ? "Running" : "Degraded"} />
              <StatusBadge tone={health.data!.database === "ok" ? "success" : "danger"} label={health.data!.database === "ok" ? "Database ok" : "Database unavailable"} />
            </>}
      </div>

      {(health.isError || summary.isError) && <div className="mb-6"><ErrorState error={summary.error ?? health.error} onRetry={() => Promise.all([health.refetch(), summary.refetch(), recent.refetch()])} /></div>}

      {summary.isLoading ? <LoadingState label="Loading your overview…" /> : s && (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Metric label="Jobs" value={s.counts.jobs} note={`${s.counts.jobs_new_this_week} new this week`} to={<Link to="/jobs">View all jobs</Link>} />
            <Metric label="Good matches" value={s.counts.jobs_good_match} to={<Link to="/jobs" search={{ sort: "match", min_match: 60 }}>View good matches</Link>} />
            <Metric label="Saved" value={s.counts.jobs_saved} to={<Link to="/jobs" search={{ status: ["saved"] }}>View saved jobs</Link>} />
            <Metric label="Drafting" value={s.counts.applications_drafting} to={<Link to="/applications" search={{ status: "draft" }}>View drafting</Link>} />
            <Metric label="Ready to send" value={s.counts.applications_ready} to={<Link to="/applications" search={{ status: "ready" }}>Send them yourself</Link>} />
            <Metric label="Sent" value={s.counts.applications_sent} to={<Link to="/applications" search={{ status: "submitted" }}>View sent applications</Link>} />
            <Metric label="Interviews" value={s.counts.interviews ?? 0} to={<Link to="/applications" search={{ status: "submitted" }}>View sent applications</Link>} />
            <Metric label="Offers" value={s.counts.offers ?? 0} to={<Link to="/applications" search={{ status: "submitted" }}>View sent applications</Link>} />
          </div>
          <div className="mb-8"><DashboardStatusStrip status={s.status} /></div>
          <div className="mb-8 grid gap-6 lg:grid-cols-2">
            <DashboardJobSection title="Deadlines this week" jobs={s.deadlines_soon} empty="No deadlines in the next 7 days." deadlines />
            <DashboardJobSection title="Best matches" jobs={s.best_matches} empty="No scored jobs yet." />
          </div>
        </>
      )}

      <section aria-labelledby="recent-h">
        <div className="mb-3 flex items-center justify-between">
          <h2 id="recent-h" className="text-xl font-medium">Recent jobs</h2>
          <Link to="/jobs" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">All jobs<ArrowRight aria-hidden className="size-4" /></Link>
        </div>
        {recent.isLoading ? <LoadingState /> : recent.isError ? <ErrorState error={recent.error} onRetry={() => recent.refetch()} />
          : recent.data!.items.length === 0 ? <EmptyState title="No jobs yet">Jobs you add will appear here.</EmptyState>
          : (
            <div className="overflow-x-auto rounded-lg border bg-card">
              <table className="w-full text-sm">
                <caption className="sr-only">Five most recent jobs</caption>
                <thead className="border-b bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th scope="col" className="px-4 py-2.5 font-medium">Title</th>
                    <th scope="col" className="hidden px-4 py-2.5 font-medium sm:table-cell">Company</th>
                    <th scope="col" className="px-4 py-2.5 font-medium">Deadline</th>
                    <th scope="col" className="px-4 py-2.5 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {recent.data!.items.map((j) => (
                    <tr key={j.id}>
                      <td className="px-4 py-3">
                        <Link to="/jobs/$id" params={{ id: j.id }} className="font-medium hover:underline">{j.title}</Link>
                        <div><ApplyYourselfTag value={j.apply_manually} /></div>
                        <div className="text-xs text-muted-foreground sm:hidden">{j.company}</div>
                      </td>
                      <td className="hidden px-4 py-3 sm:table-cell">{j.company}</td>
                      <td className="whitespace-nowrap px-4 py-3"><Deadline on={j.deadline_on} /></td>
                      <td className="px-4 py-3"><JobStatusBadge status={j.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </section>
    </>
  );
}

function Metric({ label, value, to, note }: { label: string; value: number; to: ReactNode; note?: string }) {
  return (
    <div className="rounded-lg border bg-card p-5">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 font-display text-4xl font-medium tabular-nums">{value}</p>
      {note && <p className="mt-1 text-xs text-muted-foreground">{note}</p>}
      <p className="mt-2 text-sm text-primary hover:underline">{to}</p>
    </div>
  );
}
