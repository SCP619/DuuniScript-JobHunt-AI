import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/app-shell";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { ApplicationsTable } from "@/components/applications/applications-table";
import { api } from "@/api";
import type { ApplicationStatus } from "@/api/types";

export const Route = createFileRoute("/approvals")({
  head: () => ({
    meta: [
      { title: "Pending approvals — DuuniScript" },
      { name: "description", content: "Drafts waiting for your check and approval, and approved applications you have not sent yet." },
      { property: "og:title", content: "Pending approvals — DuuniScript" },
      { property: "og:description", content: "Drafts waiting for your check and approval, and approved applications you have not sent yet." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: ApprovalsPage,
});

function ApprovalsPage() {
  return (
    <>
      <PageHeader title="Pending approvals" description="Nothing is sent without you. Check drafts here, then send approved applications yourself." />
      <div className="space-y-8">
        <List status="draft" title="Drafts to check and approve" empty="No drafts waiting for approval." />
        <List status="ready" title="Approved, not sent yet" empty="No approved applications waiting to be sent." />
      </div>
    </>
  );
}

function List({ status, title, empty }: { status: ApplicationStatus; title: string; empty: string }) {
  const q = useQuery({ queryKey: ["applications", { status, limit: 200 }], queryFn: () => api.listApplications({ status, limit: 200 }) });
  return (
    <section aria-labelledby={`ap-${status}`}>
      <h2 id={`ap-${status}`} className="mb-3 text-xl font-medium">{title}</h2>
      {q.isLoading ? <LoadingState /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} />
        : q.data!.items.length === 0 ? <EmptyState title={empty} />
        : <ApplicationsTable items={q.data!.items} caption={title} />}
    </section>
  );
}
