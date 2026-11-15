import { useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ChevronDown, ExternalLink, Eye, EyeOff, Loader2, Pencil } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ErrorState, LoadingState, NotStated } from "@/components/states";
import { selectClass } from "@/components/field";
import { ApplyYourselfTag, Deadline, JobStatusBadge, PublishedDate } from "@/components/jobs/job-bits";
import { Switch } from "@/components/ui/switch";
import { JobFields, deadlineAtProblem, formToUpdate, jobToForm, type JobFormValues } from "@/components/jobs/job-fields";
import { api, errorMessage, fieldErrors } from "@/api";
import { formatDateOnly, formatDateTime } from "@/lib/format";
import { EMPLOYMENT_TYPE, JOB_STATUS, JOB_STATUSES, LISTING_STATUS, WORK_MODE } from "@/lib/labels";
import { languageLabel, originalPostingUrl } from "@/lib/job-presentation";
import { cameFromAlertEmail } from "@/lib/job-alerts";
import { DuplicateBanner } from "@/components/jobs/duplicate-banner";
import { PrepareApplicationButton } from "@/components/applications/prepare-application";
import { FeedAttribution } from "@/components/jobs/feed-attribution";
import { ScreenshotsSection } from "@/components/jobs/screenshots-section";
import { JobMatchCard } from "@/components/jobs/match";
import type { JobRead, JobStatus, JobUpdate } from "@/api/types";

export const Route = createFileRoute("/jobs/$id")({
  head: () => ({
    meta: [
      { title: "Job details — DuuniScript" },
      { name: "description", content: "Details, status and notes for a saved job posting." },
      { property: "og:title", content: "Job details — DuuniScript" },
      { property: "og:description", content: "Details, status and notes for a saved job posting." },
      { property: "og:type", content: "article" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: JobDetailPage,
});

function JobDetailPage() {
  const { id } = Route.useParams();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["job", id], queryFn: () => api.getJob(id) });
  const feeds = useQuery({ queryKey: ["feeds"], queryFn: api.getFeeds, enabled: q.data?.listings.some((l) => l.source_key.startsWith("feed_")) ?? false });

  const update = useMutation({
    mutationFn: (body: JobUpdate) => api.updateJob(id, body),
    onSuccess: (job) => {
      qc.setQueryData(["job", id], job);
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
  const save = (body: JobUpdate, msg = "Saved") =>
    update.mutateAsync(body).then(
      (j) => { toast.success(msg); return j; },
      (e) => { toast.error(errorMessage(e)); throw e; },
    );

  if (q.isLoading) return <LoadingState label="Loading job…" />;
  if (q.isError) return (<><BackLink /><ErrorState error={q.error} onRetry={() => q.refetch()} /></>);
  const job = q.data;
  if (!job) return <LoadingState label="Loading job…" />;
  const originalUrl = originalPostingUrl(job);

  return (
    <>
      <BackLink />
      <DuplicateBanner key={job.id} job={job} />
      <div className="mb-6">
        <div className="flex flex-wrap items-center gap-2">
          <JobStatusBadge status={job.status} />
          <ApplyYourselfTag value={job.apply_manually} />
          {job.hidden && <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">Hidden</span>}
        </div>
        <h1 className="mt-2 text-3xl font-medium">{job.title}</h1>
        <p className="mt-1 text-lg text-muted-foreground">{job.company}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <PrepareApplicationButton jobId={job.id} />
          {originalUrl && (
            <Button asChild variant="outline" size="sm">
              <a href={originalUrl} target="_blank" rel="noopener noreferrer">Open original posting<ExternalLink aria-hidden className="size-3.5" /><span className="sr-only">(opens in a new tab)</span></a>
            </Button>
          )}
          {job.application_url && (
            <Button asChild size="sm" variant="outline">
              <a href={job.application_url} target="_blank" rel="noopener noreferrer">Apply on employer site<ExternalLink aria-hidden className="size-3.5" /><span className="sr-only">(opens in a new tab)</span></a>
            </Button>
          )}
          <EditJobButton job={job} onSave={(b) => save(b)} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <section aria-labelledby="facts-h" className="rounded-lg border bg-card p-5">
            <h2 id="facts-h" className="sr-only">Key details</h2>
            <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
              <Item label="Location">{job.location ?? <NotStated />}</Item>
              <Item label="Available from Finland">{job.available_from_finland === "yes" ? "Yes" : job.available_from_finland === "no" ? "No — this job is limited to other countries" : <NotStated />}</Item>
              <Item label="Employment type">{job.employment_type ? EMPLOYMENT_TYPE[job.employment_type] : <NotStated />}</Item>
              <Item label="Work mode">{job.work_mode ? WORK_MODE[job.work_mode] : <NotStated />}</Item>
              <Item label="Salary">{job.salary_text ? <span className="plain-text">{job.salary_text}</span> : <NotStated />}</Item>
              <Item label="Posting language">{languageLabel(job.language) ?? <span className="text-muted-foreground">Not known</span>}</Item>
              <Item label="Published"><PublishedDate value={job.published_on} /></Item>
              <Item label="Deadline"><Deadline on={job.deadline_on} at={job.deadline_at} long /></Item>
              <Item label="First seen in DuuniScript">{formatDateTime(job.first_seen_at)}</Item>
            </dl>
          </section>

          <JobMatchCard jobId={job.id} />
          <ScreenshotsSection jobId={job.id} />

          <section aria-labelledby="desc-h" className="rounded-lg border bg-card p-5">
            <h2 id="desc-h" className="mb-3 text-xl font-medium">Description</h2>
            {job.description ? (
              <div className="plain-text max-h-[70vh] overflow-y-auto text-sm leading-relaxed">{job.description}</div>
            ) : cameFromAlertEmail(job.listings) ? (
              <p className="text-sm text-muted-foreground">This job came from a job alert email, which does not include the advertisement. Open the original posting below, or add it with Import from URL to fill in the full text.</p>
            ) : (
              <p className="text-sm text-muted-foreground">No description was provided.</p>
            )}
          </section>

          <section aria-labelledby="original-h" className="space-y-3">
            <h2 id="original-h" className="text-xl font-medium">View the original posting</h2>
            {originalUrl ? (
              <>
                <Button asChild variant="link" className="h-auto justify-start p-0">
                  <a href={originalUrl} target="_blank" rel="noopener noreferrer">Open the original posting<ExternalLink aria-hidden className="size-4" /><span className="sr-only">(opens in a new tab)</span></a>
                </Button>
                <p className="plain-text break-all text-sm text-muted-foreground">{originalUrl}</p>
              </>
            ) : <p className="text-sm text-muted-foreground">No link saved for this job.</p>}
          </section>

          <section aria-labelledby="seen-h" className="rounded-lg border bg-card p-5">
            <h2 id="seen-h" className="mb-3 text-xl font-medium">Seen on</h2>
            {job.listings.length === 0 ? <p className="text-sm text-muted-foreground">No source records.</p> : (
              <ul className="divide-y text-sm">
                {job.listings.map((l, i) => (
                  <li key={`${l.source_key}-${i}`} className="space-y-1 py-3 first:pt-0 last:pb-0">
                    <p className="font-medium">{l.source_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {l.source_published_on && <>Published {formatDateOnly(l.source_published_on)} · </>}First seen {formatDateTime(l.first_seen_at)}
                    </p>
                    {l.source_url && (
                      <a href={l.source_url} target="_blank" rel="noopener noreferrer" className="block break-all underline">
                        {l.source_url}<span className="sr-only"> (opens in a new tab)</span>
                      </a>
                    )}
                    <FeedAttribution sourceKey={l.source_key} feeds={feeds.data?.feeds ?? []} />
                  </li>
                ))}
              </ul>
            )}
            {feeds.isError && <ErrorState error={feeds.error} onRetry={() => feeds.refetch()} />}
          </section>

          <Collapsible className="rounded-lg border bg-card">
            <CollapsibleTrigger className="group flex w-full items-center justify-between p-5 text-left">
              <h2 className="text-xl font-medium">Where this came from</h2>
              <ChevronDown aria-hidden className="size-4 transition-transform group-data-[state=open]:rotate-180" />
            </CollapsibleTrigger>
            <CollapsibleContent className="px-5 pb-5">
              {job.listings.length === 0 ? (
                <p className="text-sm text-muted-foreground">No source records.</p>
              ) : (
                <ul className="divide-y">
                  {job.listings.map((l, i) => (
                    <li key={`${l.source_key}-${i}`} className="py-3 text-sm">
                      <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-[160px_1fr]">
                        <dt className="text-muted-foreground">Source</dt><dd>{l.source_name}</dd>
                        <dt className="text-muted-foreground">Source link</dt>
                        <dd className="break-all">{l.source_url ? <a href={l.source_url} target="_blank" rel="noopener noreferrer" className="underline">{l.source_url}</a> : <NotStated />}</dd>
                        <dt className="text-muted-foreground">Captured at</dt><dd>{formatDateTime(l.captured_at) ?? <NotStated />}</dd>
                        <dt className="text-muted-foreground">Published at source</dt><dd>{formatDateOnly(l.source_published_on) ?? <NotStated />}</dd>
                        <dt className="text-muted-foreground">Parser version</dt><dd className="font-mono text-xs">{l.parser_version ?? "—"}</dd>
                        <dt className="text-muted-foreground">Listing status</dt><dd>{LISTING_STATUS[l.listing_status]}</dd>
                      </dl>
                    </li>
                  ))}
                </ul>
              )}
            </CollapsibleContent>
          </Collapsible>
        </div>

        <aside className="space-y-4" aria-label="Your tracking">
          <section className="space-y-3 rounded-lg border bg-card p-5">
            <h2 className="text-lg font-medium">Status</h2>
            <div className="flex items-center gap-2"><Switch id="apply-yourself" checked={job.apply_manually} disabled={update.isPending} onCheckedChange={(value) => save({ apply_manually: value }).catch(() => undefined)} /><Label htmlFor="apply-yourself">Apply yourself</Label></div>
            <Label htmlFor="job-status" className="sr-only">Status</Label>
            <select id="job-status" className={selectClass} value={job.status} disabled={update.isPending}
              onChange={(e) => save({ status: e.target.value as JobStatus }, "Status saved").catch(() => undefined)}>
              {JOB_STATUSES.map((s) => <option key={s} value={s}>{JOB_STATUS[s].label}</option>)}
            </select>
            <p className="text-xs text-muted-foreground">When you record an application as sent, the job is marked Applied automatically. Applied some other way? Set the status to Applied yourself.</p>
            <Button variant="outline" className="w-full" disabled={update.isPending}
              onClick={() => save({ hidden: !job.hidden }, job.hidden ? "Job is visible again" : "Job hidden").catch(() => undefined)}>
              {job.hidden ? <Eye aria-hidden className="size-4" /> : <EyeOff aria-hidden className="size-4" />}
              {job.hidden ? "Unhide" : "Hide"}
            </Button>
          </section>
          <NotesCard job={job} onSave={(n) => save({ user_notes: n }, "Notes saved")} />
        </aside>
      </div>
    </>
  );
}

function BackLink() {
  return (
    <Link to="/jobs" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
      <ArrowLeft aria-hidden className="size-4" />All jobs
    </Link>
  );
}

function Item({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-0.5">{children}</dd>
    </div>
  );
}

function NotesCard({ job, onSave }: { job: JobRead; onSave: (n: string | null) => Promise<unknown> }) {
  const [notes, setNotes] = useState(job.user_notes ?? "");
  const [pending, setPending] = useState(false);
  useEffect(() => setNotes(job.user_notes ?? ""), [job.user_notes]);
  const dirty = notes !== (job.user_notes ?? "");
  return (
    <section className="space-y-3 rounded-lg border bg-card p-5">
      <h2 className="text-lg font-medium"><Label htmlFor="job-notes" className="text-lg font-medium">Notes</Label></h2>
      <Textarea id="job-notes" rows={6} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Only you can see these." />
      <Button className="w-full" disabled={!dirty || pending} onClick={async () => {
        setPending(true);
        try { await onSave(notes.trim() === "" ? null : notes); } catch { /* toast shown */ } finally { setPending(false); }
      }}>
        {pending && <Loader2 aria-hidden className="size-4 animate-spin" />}Save notes
      </Button>
    </section>
  );
}

function EditJobButton({ job, onSave }: { job: JobRead; onSave: (b: JobUpdate) => Promise<JobRead> }) {
  const [open, setOpen] = useState(false);
  const [initial, setInitial] = useState<JobFormValues>(() => jobToForm(job));
  const [values, setValues] = useState<JobFormValues>(initial);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const openDialog = () => {
    const f = jobToForm(job);
    setInitial(f); setValues(f); setErrors({}); setFormError(null); setOpen(true);
  };
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const p = deadlineAtProblem(values);
    if (p) { setErrors({ deadline_at: p }); return; }
    const body = formToUpdate(initial, values);
    if (Object.keys(body).length === 0) { setOpen(false); return; }
    setPending(true); setErrors({}); setFormError(null);
    try {
      await onSave(body);
      setOpen(false);
    } catch (err) {
      const fe = fieldErrors(err);
      setErrors(fe);
      if (!Object.keys(fe).length) setFormError(errorMessage(err));
    } finally {
      setPending(false);
    }
  };
  return (
    <>
      <Button variant="ghost" size="sm" onClick={openDialog}><Pencil aria-hidden className="size-4" />Edit details</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit job details</DialogTitle>
            <DialogDescription>Correct anything that was read wrongly. The original link can't be changed.</DialogDescription>
          </DialogHeader>
          <form onSubmit={submit} className="space-y-4" noValidate>
            <JobFields idPrefix="edit-job" mode="edit" values={values} errors={errors} onChange={(k, v) => setValues((s) => ({ ...s, [k]: v }))} />
            {formError && <p role="alert" className="text-sm text-destructive">{formError}</p>}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={pending}>{pending && <Loader2 aria-hidden className="size-4 animate-spin" />}Save changes</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
