import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorState, LoadingState } from "@/components/states";
import { StatusBadge } from "@/components/status-badge";
import { api, errorMessage } from "@/api";
import type { AlertSyncResult, JobAlertStatus } from "@/api/types";
import { formatDateTime, formatRelative } from "@/lib/format";
import { MAX_ALERT_EMAILS, syncIntervalText, syncSummary } from "@/lib/job-alerts";

type Outcome = { kind: "ok"; text: string } | { kind: "error"; text: string } | null;

export function JobAlertsCard() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["job-alerts"], queryFn: api.getJobAlerts });
  const [outcome, setOutcome] = useState<Outcome>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const onDone = (r: AlertSyncResult) => {
    setOutcome({ kind: "ok", text: syncSummary(r) });
    qc.invalidateQueries({ queryKey: ["job-alerts"] });
    qc.invalidateQueries({ queryKey: ["jobs"] });
    qc.invalidateQueries({ queryKey: ["job"] });
  };
  const onFail = (e: unknown) => {
    setOutcome({ kind: "error", text: errorMessage(e) });
    qc.invalidateQueries({ queryKey: ["job-alerts"] });
  };
  const sync = useMutation({ mutationFn: api.syncJobAlerts, onSuccess: onDone, onError: onFail });
  const upload = useMutation({ mutationFn: api.uploadAlertEmails, onSuccess: onDone, onError: onFail });
  const busy = sync.isPending || upload.isPending;

  const pickFiles = (list: FileList | null) => {
    const files = Array.from(list ?? []);
    if (fileRef.current) fileRef.current.value = "";
    if (!files.length) return;
    if (files.length > MAX_ALERT_EMAILS) {
      setOutcome({ kind: "error", text: `Choose at most ${MAX_ALERT_EMAILS} emails at a time.` });
      return;
    }
    setOutcome(null);
    upload.mutate(files);
  };

  return (
    <section aria-labelledby="s-alerts" className="rounded-lg border bg-card p-5">
      <h2 id="s-alerts" className="mb-4 text-xl font-medium">Job alert emails</h2>
      {status.isLoading ? <LoadingState className="py-2" /> : status.isError ? <ErrorState error={status.error} onRetry={() => status.refetch()} /> : status.data && (
        <div className="space-y-5">
          {status.data.configured ? <ConfiguredDetails s={status.data} /> : <SetupSteps />}

          <div className="flex flex-wrap items-center gap-3">
            {status.data.configured && (
              <Button onClick={() => { setOutcome(null); sync.mutate(); }} disabled={busy}>
                {sync.isPending ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <RefreshCw aria-hidden className="size-4" />}
                Check now
              </Button>
            )}
            <input ref={fileRef} id="alert-emails" type="file" accept=".eml,message/rfc822" multiple className="sr-only"
              aria-describedby="alert-emails-help" onChange={(e) => pickFiles(e.target.files)} disabled={busy} />
            <Button variant="outline" disabled={busy} onClick={() => fileRef.current?.click()}>
              {upload.isPending ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <Upload aria-hidden className="size-4" />}
              Add saved alert emails
            </Button>
          </div>
          <p id="alert-emails-help" className="-mt-3 text-xs text-muted-foreground">In Gmail: open the email, ⋮ → Download message. Up to {MAX_ALERT_EMAILS} .eml files at a time.</p>

          <div aria-live="polite">
            {outcome?.kind === "ok" && <p role="status" className="rounded-md border bg-muted/50 p-3 text-sm">{outcome.text}</p>}
            {outcome?.kind === "error" && <p role="alert" className="plain-text rounded-md border border-warning/40 bg-warning-soft p-3 text-sm">{outcome.text}</p>}
          </div>

          {status.data.sites.length > 0 && <SitesTable s={status.data} />}
        </div>
      )}
    </section>
  );
}

function SetupSteps() {
  return (
    <div className="space-y-2 text-sm">
      <p className="font-medium">Job alert emails are not set up yet.</p>
      <ol className="list-decimal space-y-1 pl-5 text-muted-foreground">
        <li>In Gmail, make a label (e.g. "DuuniScript") and a filter that puts job alert emails in it.</li>
        <li>Create a Gmail app password (Google Account → Security → App passwords).</li>
        <li>Put the mailbox address in the <code className="rounded bg-muted px-1 font-mono text-xs">.env</code> file as <code className="rounded bg-muted px-1 font-mono text-xs">MAIL_IMAP_USER</code>.</li>
        <li>Run <code className="break-all rounded bg-muted px-1 font-mono text-xs">.venv\Scripts\python.exe scripts\set_mail_password.py</code> and restart the API.</li>
      </ol>
    </div>
  );
}

function ConfiguredDetails({ s }: { s: JobAlertStatus }) {
  return (
    <div className="space-y-4">
      <dl className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
        <div><dt className="text-muted-foreground">Mailbox</dt><dd className="mt-1 break-all">{s.mailbox ?? "—"}</dd></div>
        <div><dt className="text-muted-foreground">Label</dt><dd className="mt-1">{s.folder}</dd></div>
        <div><dt className="text-muted-foreground">Schedule</dt><dd className="mt-1">{syncIntervalText(s)}</dd></div>
        <div><dt className="text-muted-foreground">Last checked</dt><dd className="mt-1" title={formatDateTime(s.last_sync_at) ?? undefined}>{formatRelative(s.last_sync_at) ?? "Never"}</dd></div>
        <div><dt className="text-muted-foreground">Emails read</dt><dd className="mt-1">{s.emails_read}</dd></div>
        <div><dt className="text-muted-foreground">Jobs added</dt><dd className="mt-1">{s.jobs_created} new, {s.jobs_merged} added to existing jobs</dd></div>
      </dl>
      {s.last_error && (
        <div role="alert" className="rounded-md border border-warning/40 bg-warning-soft p-3 text-sm">
          <p className="plain-text">{s.last_error}</p>
          {s.last_error_at && <p className="mt-1 text-xs text-muted-foreground">{formatDateTime(s.last_error_at)}</p>}
        </div>
      )}
    </div>
  );
}

function SitesTable({ s }: { s: JobAlertStatus }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">Job alert sites</caption>
        <thead className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
          <tr>{["Site", "Emails read", "Last email", "Format"].map((h) => <th key={h} scope="col" className="px-3 py-2 font-medium">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y">
          {s.sites.map((site) => (
            <tr key={site.key}>
              <td className="px-3 py-2.5 font-medium">{site.name}</td>
              <td className="px-3 py-2.5">{site.emails_read}</td>
              <td className="whitespace-nowrap px-3 py-2.5">{formatDateTime(site.last_email_at) ?? <span className="text-muted-foreground">Never</span>}</td>
              <td className="px-3 py-2.5"><StatusBadge tone={site.format_verified ? "success" : "muted"} label={site.format_verified ? "Format checked" : "Not yet checked"} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
