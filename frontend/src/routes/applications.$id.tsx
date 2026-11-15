import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ChevronDown, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { ErrorState, LoadingState } from "@/components/states";
import { StatusBadge } from "@/components/status-badge";
import { Deadline } from "@/components/jobs/job-bits";
import { FormAnswers } from "@/components/applications/form-answers";
import { DraftTab } from "@/components/applications/draft-tab";
import { SendPanel } from "@/components/applications/send-panel";
import { OutcomeControl } from "@/components/applications/outcome-control";
import { api, errorMessage } from "@/api";
import { APPLICATION_STATUS, SUBMISSION_METHOD, eventLabel } from "@/lib/applications";
import { formatDateTime } from "@/lib/format";

export const Route = createFileRoute("/applications/$id")({
  head: () => ({
    meta: [
      { title: "Application — DuuniScript" },
      { name: "description", content: "Check and approve your CV and cover letter drafts, then send the application yourself." },
      { property: "og:title", content: "Application — DuuniScript" },
      { property: "og:description", content: "Check and approve your CV and cover letter drafts, then send the application yourself." },
      { property: "og:type", content: "article" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: ApplicationPage,
});

function ApplicationPage() {
  const { id } = Route.useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const q = useQuery({ queryKey: ["application", id], queryFn: () => api.getApplication(id) });
  const profiles = useQuery({ queryKey: ["cvProfiles"], queryFn: api.listCvProfiles });
  const templates = useQuery({ queryKey: ["templates"], queryFn: api.listTemplates });
  const [tab, setTab] = useState("cv");
  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["application", id] });
    qc.invalidateQueries({ queryKey: ["applications"] });
    qc.invalidateQueries({ queryKey: ["package", id] });
    qc.invalidateQueries({ queryKey: ["appEvents", id] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
  };
  const toggleLetter = useMutation({ mutationFn: (v: boolean) => api.updateApplication(id, { include_cover_letter: v }), onSuccess: () => { toast.success("Saved"); refresh(); }, onError: (e) => toast.error(errorMessage(e)) });
  const withdraw = useMutation({ mutationFn: () => api.withdrawApplication(id), onSuccess: () => { setWithdrawOpen(false); toast.success("Withdrawn"); refresh(); }, onError: (e) => toast.error(errorMessage(e)) });
  const del = useMutation({
    mutationFn: () => api.deleteApplication(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["applications"] }); toast.success("Application deleted"); navigate({ to: "/applications" }); },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (q.isLoading) return <LoadingState label="Loading application…" />;
  if (q.isError) return <><Back /><ErrorState error={q.error} onRetry={() => q.refetch()} /></>;
  const app = q.data;
  if (!app) return <LoadingState />;
  const s = APPLICATION_STATUS[app.status];
  const locked = app.status === "submitted" || app.status === "withdrawn";
  const current = !app.include_cover_letter && tab === "cover_letter" ? "cv" : tab;

  return (
    <>
      <Back />
      <header className="mb-6 space-y-2">
        <StatusBadge tone={s.tone} label={s.label} />
        <h1 className="text-3xl font-medium">{app.job.title}</h1>
        <p className="text-lg text-muted-foreground"><Link to="/jobs/$id" params={{ id: app.job.id }} className="hover:underline">{app.job.company}</Link></p>
        <p className="text-sm"><span className="text-muted-foreground">Deadline: </span><Deadline on={app.job.deadline_on} /></p>
        <p className="plain-text text-sm text-muted-foreground">CV profile: {app.cv_profile_id ? profiles.data?.find((p) => p.id === app.cv_profile_id)?.name ?? app.cv_profile_id : "None"}</p>
      </header>

      {app.submitted_at && (
        <div role="status" className="mb-6 flex flex-wrap items-center gap-3 rounded-lg border border-success/40 bg-success-soft p-4 text-sm">
          <span className="mr-auto">Sent on {formatDateTime(app.submitted_at)} ({app.submission_method ? SUBMISSION_METHOD[app.submission_method] : "method not recorded"}){app.confirmation_reference && <> · Reference: <span className="plain-text">{app.confirmation_reference}</span></>}{app.withdrawn_at && <> · Withdrawn {formatDateTime(app.withdrawn_at)}</>}</span>
          {app.status === "submitted" && <Button size="sm" variant="outline" onClick={() => setWithdrawOpen(true)}>Withdraw</Button>}
        </div>
      )}

      {app.status === "submitted" && <OutcomeControl key={`${app.outcome}-${app.outcome_on}`} app={app} onChanged={refresh} />}

      {app.status === "ready" && <div className="mb-6"><SendPanel appId={id} onChanged={refresh} /></div>}

      <div className="mb-3 flex items-center gap-2">
        <Switch id="app-letter" checked={app.include_cover_letter} disabled={locked || toggleLetter.isPending} onCheckedChange={(v) => toggleLetter.mutate(v)} />
        <Label htmlFor="app-letter">Include a cover letter</Label>
      </div>

      <Tabs value={current} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="form_answers">Form answers</TabsTrigger>
          <TabsTrigger value="cv">CV</TabsTrigger>
          {app.include_cover_letter && <TabsTrigger value="cover_letter">Cover letter</TabsTrigger>}
        </TabsList>
        <TabsContent value="form_answers" className="mt-4"><FormAnswers appId={id} /></TabsContent>
        <TabsContent value="cv" className="mt-4"><DraftTab app={app} kind="cv" templates={templates.data ?? []} locked={locked} onChanged={refresh} /></TabsContent>
        {app.include_cover_letter && <TabsContent value="cover_letter" className="mt-4"><DraftTab app={app} kind="cover_letter" templates={templates.data ?? []} locked={locked} onChanged={refresh} /></TabsContent>}
      </Tabs>

      <History appId={id} />

      {!app.submitted_at && (
        <div className="mt-8 border-t pt-6">
          <Button variant="ghost" className="text-destructive" onClick={() => setDeleteOpen(true)}><Trash2 aria-hidden className="size-4" />Delete application</Button>
        </div>
      )}

      <ConfirmDialog open={withdrawOpen} onOpenChange={setWithdrawOpen} title="Mark as withdrawn?" destructive={false}
        description="This only records that you withdrew the application. DuuniScript does not contact the employer."
        confirmLabel="Mark as withdrawn" pending={withdraw.isPending} onConfirm={() => withdraw.mutate()} />
      <ConfirmDialog open={deleteOpen} onOpenChange={setDeleteOpen} title="Delete this application?"
        description="This permanently deletes the drafts and history for this application. The job stays in your list."
        confirmLabel="Delete application" pending={del.isPending} onConfirm={() => del.mutate()} />
    </>
  );
}

function History({ appId }: { appId: string }) {
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ["appEvents", appId], queryFn: () => api.listApplicationEvents(appId), enabled: open });
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="mt-8 rounded-lg border bg-card p-4">
      <CollapsibleTrigger className="inline-flex items-center gap-1 font-medium hover:underline"><ChevronDown aria-hidden className="size-4" />History</CollapsibleTrigger>
      <CollapsibleContent className="mt-3">
        {q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : !q.data ? <LoadingState className="py-2" />
          : q.data!.length === 0 ? <p className="text-sm text-muted-foreground">Nothing recorded yet.</p>
          : <ul className="space-y-1 text-sm">{q.data!.map((e) => <li key={e.id}><span className="text-muted-foreground">{formatDateTime(e.occurred_at)}</span> · {eventLabel(e)}</li>)}</ul>}
      </CollapsibleContent>
    </Collapsible>
  );
}

function Back() {
  return <Link to="/applications" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft aria-hidden className="size-4" />All applications</Link>;
}
