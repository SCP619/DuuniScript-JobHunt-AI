import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, ExternalLink, Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { ErrorState, LoadingState } from "@/components/states";
import { StatusBadge } from "@/components/status-badge";
import { api, errorMessage } from "@/api";
import { GMAIL_POLL_LIMIT_MS, integrationsPollInterval } from "@/lib/account";
import { syncSummary } from "@/lib/job-alerts";
import { formatRelative } from "@/lib/format";
import type { DeviceSignInRead, IntegrationProvider, ProviderStatus } from "@/api/types";

export const INTEGRATIONS_KEY = ["integrations"] as const;

export function ConnectedAccountsCard() {
  const [gmailPollUntil, setGmailPollUntil] = useState<number | null>(null);
  const q = useQuery({
    queryKey: INTEGRATIONS_KEY, queryFn: api.getIntegrations,
    refetchInterval: (query) => integrationsPollInterval(query.state.data, gmailPollUntil),
  });
  const connectGoogle = useMutation({
    mutationFn: api.connectGoogle,
    onSuccess: ({ url }) => { window.open(url, "_blank", "noopener"); setGmailPollUntil(Date.now() + GMAIL_POLL_LIMIT_MS); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const qc = useQueryClient();
  const connectMs = useMutation({
    mutationFn: api.connectMicrosoft,
    onSuccess: (r) => { qc.setQueryData(INTEGRATIONS_KEY, (old: typeof q.data) => (old ? { ...old, microsoft_sign_in: r } : old)); q.refetch(); },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <section aria-labelledby="s-accounts" className="rounded-lg border bg-card p-5">
      <h2 id="s-accounts" className="mb-1 text-xl font-medium">Connected accounts</h2>
      <p className="mb-4 text-sm text-muted-foreground">Optional. DuuniScript only reads job alert emails and never sends anything without your confirmation.</p>
      {q.isLoading ? <LoadingState className="py-2" /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : q.data && (
        <div className="divide-y">
          <ProviderRow provider="google" title="Gmail" description="Reads job alert emails and can put an approved application in your Gmail drafts." status={q.data.google}
            connect={<>
              <Button size="sm" onClick={() => connectGoogle.mutate()} disabled={connectGoogle.isPending}>Connect Gmail</Button>
              {gmailPollUntil !== null && Date.now() < gmailPollUntil && <p className="text-sm text-muted-foreground" aria-live="polite">Finish signing in to Google in the new tab. This page updates when you're done.</p>}
            </>} />
          <ProviderRow provider="microsoft" title="University mail (Microsoft 365)" description="For JobTeaser and other alerts that arrive in your UTU mailbox." status={q.data.microsoft}
            connect={<>
              {q.data.microsoft_sign_in.status !== "waiting" && <Button size="sm" onClick={() => connectMs.mutate()} disabled={connectMs.isPending}>Connect university mail</Button>}
              <DeviceCodePanel s={q.data.microsoft_sign_in} />
            </>} />
        </div>
      )}
    </section>
  );
}

function ProviderRow({ provider, title, description, status, connect }: { provider: IntegrationProvider; title: string; description: string; status: ProviderStatus; connect: React.ReactNode }) {
  const qc = useQueryClient();
  const [confirmOff, setConfirmOff] = useState(false);
  const refresh = () => qc.invalidateQueries({ queryKey: INTEGRATIONS_KEY });
  const sync = useMutation({
    mutationFn: () => api.syncIntegration(provider),
    onSuccess: (r) => { toast.success(syncSummary(r)); refresh(); qc.invalidateQueries({ queryKey: ["jobs"] }); },
    onError: (e) => { toast.error(errorMessage(e)); refresh(); },
  });
  const off = useMutation({
    mutationFn: () => api.disconnectIntegration(provider),
    onSuccess: () => { setConfirmOff(false); toast.success(`${title} disconnected`); refresh(); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <div className="space-y-3 py-4 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-medium">{title}</h3>
        <StatusBadge tone={status.connected ? "success" : "muted"} label={status.connected ? "Connected" : status.configured ? "Not connected" : "Not set up"} />
      </div>
      <p className="text-sm text-muted-foreground">{description}</p>
      {!status.configured ? (
        <p className="text-sm text-muted-foreground">Not set up on this computer — see the setup guide (docs/BACKEND_SETUP.md, section 15).</p>
      ) : !status.connected ? (
        <div className="space-y-3">{connect}</div>
      ) : (
        <div className="space-y-3 text-sm">
          <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-[max-content_1fr]">
            <dt className="text-muted-foreground">Account</dt><dd className="break-all">{status.account ?? "Not stated"}</dd>
            <dt className="text-muted-foreground">Last checked</dt><dd>{formatRelative(status.last_sync_at) ?? "Not checked yet"}</dd>
          </dl>
          {status.last_error && <p role="status" className="plain-text rounded-md border border-warning/40 bg-warning-soft p-3 text-warning">{status.last_error}</p>}
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => sync.mutate()} disabled={sync.isPending}>{sync.isPending ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <RefreshCw aria-hidden className="size-4" />}Check now</Button>
            <Button size="sm" variant="outline" onClick={() => setConfirmOff(true)}>Disconnect</Button>
          </div>
        </div>
      )}
      <ConfirmDialog open={confirmOff} onOpenChange={setConfirmOff} title={`Disconnect ${title}?`}
        description="DuuniScript will stop reading job alerts from this account. Jobs already added stay in your list."
        confirmLabel="Disconnect" pending={off.isPending} onConfirm={() => off.mutate()} />
    </div>
  );
}

export function DeviceCodePanel({ s }: { s: DeviceSignInRead }) {
  if (s.status === "failed") return <p role="alert" className="plain-text rounded-md border border-warning/40 bg-warning-soft p-3 text-sm text-warning">{s.message ?? "Signing in did not finish."}</p>;
  if (s.status !== "waiting" || !s.user_code) return null;
  const code = s.user_code;
  return (
    <div className="space-y-3 rounded-md border bg-secondary p-4" aria-live="polite">
      <p className="text-sm text-muted-foreground">Your code</p>
      <div className="flex flex-wrap items-center gap-3">
        <span className="font-mono text-3xl font-semibold tracking-widest" data-testid="device-code">{code}</span>
        <Button size="sm" variant="outline" onClick={() => navigator.clipboard.writeText(code).then(() => toast.success("Copied"), () => toast.error("Couldn't copy"))}><Copy aria-hidden className="size-4" />Copy code</Button>
      </div>
      {s.verification_uri && (
        <Button asChild size="sm"><a href={s.verification_uri} target="_blank" rel="noopener noreferrer">Open Microsoft sign-in<ExternalLink aria-hidden className="size-3.5" /><span className="sr-only">(opens in a new tab)</span></a></Button>
      )}
      <p className="text-sm">Type the code there and sign in with your university account. Your password and 2FA stay with Microsoft.</p>
      <p className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 aria-hidden className="size-3.5 animate-spin" />Waiting for you to finish signing in…</p>
    </div>
  );
}
