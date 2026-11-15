import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/app-shell";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { ErrorState, LoadingState } from "@/components/states";
import { Field } from "@/components/field";
import { StatusBadge } from "@/components/status-badge";
import { JobAlertsCard } from "@/components/settings/job-alerts-card";
import { JobFeedsCard } from "@/components/settings/job-feeds-card";
import { FeedSourceSwitch } from "@/components/settings/feed-source-switch";
import { BackupsCard } from "@/components/settings/backups-card";
import { SignInCard } from "@/components/settings/sign-in-card";
import { ConnectedAccountsCard } from "@/components/settings/connected-accounts-card";
import { CvProfilesCard } from "@/components/settings/cv-profiles-card";
import { Housekeeping } from "@/components/settings/housekeeping";
import { LocalAiCard } from "@/components/settings/local-ai-card";
import { api, errorMessage, isApiError } from "@/api";
import { formatDateTime } from "@/lib/format";
import { ACCESS_TYPE } from "@/lib/labels";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings — DuuniScript" },
      { name: "description", content: "Sign-in, connected accounts, job alerts, job sources, backups and where your data is stored." },
      { property: "og:title", content: "Settings — DuuniScript" },
      { property: "og:description", content: "Sign-in, connected accounts, job alerts, job sources, backups and where your data is stored." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: SettingsPage,
});

function Section({ title, children, id }: { title: string; children: React.ReactNode; id: string }) {
  return (
    <section aria-labelledby={id} className="rounded-lg border bg-card p-5">
      <h2 id={id} className="mb-4 text-xl font-medium">{title}</h2>
      {children}
    </section>
  );
}

function SettingsPage() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const sources = useQuery({ queryKey: ["sources"], queryFn: api.listSources });

  return (
    <>
      <PageHeader title="Settings" description="How DuuniScript is set up on this computer." />
      <div className="space-y-6">
        <Section title="Backend status" id="s-health">
          {health.isLoading ? <LoadingState className="py-2" /> : health.isError ? <ErrorState error={health.error} onRetry={() => health.refetch()} /> : (
            <dl className="grid gap-4 text-sm sm:grid-cols-3">
              <div><dt className="text-muted-foreground">Version</dt><dd className="mt-1 font-mono">{health.data!.version}</dd></div>
              <div><dt className="text-muted-foreground">Status</dt><dd className="mt-1"><StatusBadge tone={health.data!.status === "ok" ? "success" : "warning"} label={health.data!.status === "ok" ? "Running normally" : "Degraded"} /></dd></div>
              <div><dt className="text-muted-foreground">Database</dt><dd className="mt-1"><StatusBadge tone={health.data!.database === "ok" ? "success" : "danger"} label={health.data!.database === "ok" ? "Available" : "Unavailable"} /></dd></div>
            </dl>
          )}
        </Section>

        <SignInCard />
        <ConnectedAccountsCard />
        <LocalAiCard />
        <CvProfilesCard />
        <Housekeeping />
        <JobAlertsCard />
        <JobFeedsCard />
        <BackupsCard />

        <Section title="Job sources" id="s-sources">
          <p className="mb-4 text-sm text-muted-foreground">Where jobs can come from. Job feeds can be turned on or off; other sources are read-only.</p>
          {sources.isLoading ? <LoadingState className="py-2" /> : sources.isError ? <ErrorState error={sources.error} onRetry={() => sources.refetch()} /> : (
            <>
              <div className="hidden overflow-x-auto md:block">
                <table className="w-full text-sm">
                  <caption className="sr-only">Job sources</caption>
                  <thead className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <tr>
                      {["Name", "Access", "Enabled", "Last success", "Last error"].map((h) => <th key={h} scope="col" className="px-3 py-2 font-medium">{h}</th>)}
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {sources.data!.map((s) => (
                      <tr key={s.id} className="align-top">
                        <td className="px-3 py-3 font-medium">{s.name}{s.domain && <div className="text-xs font-normal text-muted-foreground">{s.domain}</div>}</td>
                        <td className="px-3 py-3">{ACCESS_TYPE[s.access_type]}</td>
                          <td className="px-3 py-3">{s.key.startsWith("feed_") ? <FeedSourceSwitch sourceKey={s.key} name={s.name} enabled={s.enabled} /> : <StatusBadge tone={s.enabled ? "success" : "muted"} label={s.enabled ? "Enabled" : "Disabled"} />}</td>
                        <td className="whitespace-nowrap px-3 py-3">{formatDateTime(s.last_success_at) ?? <span className="text-muted-foreground">Never</span>}</td>
                        <td className="px-3 py-3">
                          {s.last_error_at ? <><div className="whitespace-nowrap">{formatDateTime(s.last_error_at)}</div><div className="plain-text text-xs text-muted-foreground">{s.last_error}</div></> : <span className="text-muted-foreground">None</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <ul className="space-y-3 md:hidden">
                {sources.data!.map((s) => (
                  <li key={s.id} className="rounded-md border p-3 text-sm">
                    <div className="flex items-center justify-between gap-2"><span className="font-medium">{s.name}</span>{s.key.startsWith("feed_") ? <FeedSourceSwitch sourceKey={s.key} name={s.name} enabled={s.enabled} /> : <StatusBadge tone={s.enabled ? "success" : "muted"} label={s.enabled ? "Enabled" : "Disabled"} />}</div>
                    <p className="text-muted-foreground">{ACCESS_TYPE[s.access_type]}</p>
                    <p className="mt-1 text-xs">Last success: {formatDateTime(s.last_success_at) ?? "Never"}</p>
                    {s.last_error_at && <p className="plain-text text-xs text-muted-foreground">Last error {formatDateTime(s.last_error_at)}: {s.last_error}</p>}
                  </li>
                ))}
              </ul>
            </>
          )}
        </Section>

        <Section title="Data location" id="s-data">
          <p className="text-sm">Your data is stored only on this computer, in <code className="rounded bg-muted px-1 font-mono text-xs">%LOCALAPPDATA%\DuuniScript</code> unless you changed <code className="rounded bg-muted px-1 font-mono text-xs">APP_DATA_DIR</code>.</p>
        </Section>

        <Section title="Not yet available" id="s-later">
          <ul className="divide-y text-sm">
            {["Pause all automation"].map((x) => (
              <li key={x} className="flex justify-between py-2"><span>{x}</span><span className="text-muted-foreground">Not available yet</span></li>
            ))}
          </ul>
        </Section>

        <DangerZone />
      </div>
    </>
  );
}

function DangerZone() {
  const qc = useQueryClient();
  const [counts, setCounts] = useState<{ facts: number; evidence: number; documents: number } | null>(null);
  const [typed, setTyped] = useState("");
  const [checking, setChecking] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = async () => {
    setChecking(true); setError(null);
    try {
      await api.deleteProfile(false);
      // Not expected: the backend always asks for confirmation first.
      setError("The backend did not ask for confirmation. Please reload and check your profile.");
    } catch (e) {
      if (isApiError(e) && e.code === "confirmation_required") {
        const d = e.details as { facts?: number; evidence?: number; documents?: number };
        setTyped("");
        setCounts({ facts: d.facts ?? 0, evidence: d.evidence ?? 0, documents: d.documents ?? 0 });
      } else setError(errorMessage(e));
    } finally {
      setChecking(false);
    }
  };
  const confirm = async () => {
    setDeleting(true);
    try {
      const r = await api.deleteProfile(true);
      setCounts(null);
      qc.invalidateQueries();
      toast.success(`Profile deleted: ${r.deleted_facts} facts, ${r.deleted_evidence} evidence items and ${r.deleted_documents} documents removed.`);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <section aria-labelledby="s-danger" className="rounded-lg border border-destructive/40 bg-card p-5">
      <h2 id="s-danger" className="text-xl font-medium">Danger zone</h2>
      <p className="mb-4 mt-1 text-sm text-muted-foreground">Permanently delete your profile, its facts and evidence, and all documents. This can't be undone.</p>
      <Button variant="destructive" onClick={start} disabled={checking}>{checking && <Loader2 aria-hidden className="size-4 animate-spin" />}Delete profile…</Button>
      {error && <p role="alert" className="mt-3 text-sm text-destructive">{error}</p>}
      <ConfirmDialog
        open={!!counts} onOpenChange={(o) => !o && setCounts(null)} title="Delete your profile?"
        description={counts && `This permanently deletes your profile, ${counts.facts} facts, ${counts.evidence} evidence items and ${counts.documents} documents including the stored files.`}
        confirmLabel="Delete everything" pending={deleting} confirmDisabled={typed !== "DELETE"} onConfirm={confirm}
      >
        <Field id="confirm-delete" label="Type DELETE to confirm">
          <Input id="confirm-delete" autoComplete="off" value={typed} onChange={(e) => setTyped(e.target.value)} />
        </Field>
      </ConfirmDialog>
    </section>
  );
}
