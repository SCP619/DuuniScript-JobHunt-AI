import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Download, Loader2, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, errorMessage } from "@/api";
import type { BackupRead } from "@/api/types";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { formatBytes, formatDateTime, formatRelative } from "@/lib/format";
import { saveBlob } from "@/lib/applications";

const RESTORE_COMMAND = String.raw`.venv\Scripts\python.exe scripts\restore_backup.py <path to backup zip>`;

export function BackupsCard() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["backups"], queryFn: api.getBackups });
  const [deleting, setDeleting] = useState<BackupRead | null>(null);
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["backups"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
  };
  const create = useMutation({
    mutationFn: api.createBackup,
    onSuccess: () => { toast.success("Backup made"); refresh(); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const download = useMutation({
    mutationFn: api.downloadBackup,
    onSuccess: saveBlob,
    onError: (e) => toast.error(errorMessage(e)),
  });
  const del = useMutation({
    mutationFn: (name: string) => api.deleteBackup(name, true),
    onSuccess: () => { toast.success("Backup deleted"); setDeleting(null); refresh(); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const s = q.data;

  return (
    <section aria-labelledby="s-backups" className="rounded-lg border bg-card p-5">
      <h2 id="s-backups" className="mb-4 text-xl font-medium">Backups</h2>
      {q.isLoading ? <LoadingState className="py-2" /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : s && (
        <div className="space-y-4">
          <div className="space-y-1 text-sm">
            <p>{s.interval_hours === 0 ? "Automatic backups are off." : `DuuniScript makes a backup every ${s.interval_hours} hours while it is running and keeps the newest ${s.keep}.`}</p>
            <p className="text-muted-foreground">Backups contain your personal data. Keep copies only on this computer or an encrypted drive.</p>
          </div>
          <Button onClick={() => create.mutate()} disabled={create.isPending}>
            {create.isPending ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <Plus aria-hidden className="size-4" />}Back up now
          </Button>
          {s.backups.length === 0 ? <p className="text-sm text-muted-foreground">No backups yet.</p> : (
            <div className="overflow-x-auto rounded-md border">
              <table className="w-full text-sm">
                <caption className="sr-only">Backups stored on this computer</caption>
                <thead className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>{["Date", "Size", "Download", "Delete"].map((h) => <th key={h} scope="col" className="px-3 py-2 font-medium">{h}</th>)}</tr>
                </thead>
                <tbody className="divide-y">
                  {s.backups.map((b) => (
                    <tr key={b.name}>
                      <td className="px-3 py-3"><span className="whitespace-nowrap">{formatDateTime(b.created_at)}</span><span className="block text-xs text-muted-foreground">{formatRelative(b.created_at)}</span></td>
                      <td className="whitespace-nowrap px-3 py-3">{formatBytes(b.size_bytes)}</td>
                      <td className="px-3 py-3"><Button variant="outline" size="sm" aria-label={`Download ${b.name}`} disabled={download.isPending} onClick={() => download.mutate(b.name)}><Download aria-hidden className="size-4" />Download</Button></td>
                      <td className="px-3 py-3"><Button variant="ghost" size="sm" aria-label={`Delete ${b.name}`} onClick={() => setDeleting(b)}><Trash2 aria-hidden className="size-4" />Delete</Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <Collapsible>
            <CollapsibleTrigger className="text-sm font-medium underline">How to restore</CollapsibleTrigger>
            <CollapsibleContent className="mt-3 space-y-3 text-sm">
              <p>Close DuuniScript, then run in PowerShell from the DuuniScript folder:</p>
              <div className="flex items-start gap-2">
                <pre tabIndex={0} className="min-w-0 flex-1 overflow-x-auto rounded-md bg-muted p-3 text-xs"><code>{RESTORE_COMMAND}</code></pre>
                <Button variant="outline" size="sm" onClick={async () => {
                  try { await navigator.clipboard.writeText(RESTORE_COMMAND); toast.success("Restore command copied"); }
                  catch { toast.error("Could not copy the command. Select and copy it yourself."); }
                }}><Copy aria-hidden className="size-4" />Copy</Button>
              </div>
              <p className="text-muted-foreground">Your current data is moved aside first, never deleted.</p>
            </CollapsibleContent>
          </Collapsible>
        </div>
      )}
      <ConfirmDialog
        open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)} title="Delete this backup?"
        description="This cannot be undone." confirmLabel="Delete backup" pending={del.isPending}
        onConfirm={() => deleting && del.mutate(deleting.name)}
      />
    </section>
  );
}
