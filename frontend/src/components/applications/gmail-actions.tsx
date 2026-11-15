import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ExternalLink, Loader2, Mail } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api, errorMessage } from "@/api";
import { buildSendEmail, defaultRecipient } from "@/lib/account";
import type { PackageRead } from "@/api/types";

/** Shown only when Gmail is connected. Drafts are never sent; sending needs the explicit dialog. */
export function GmailActions({ appId, pkg, onSent }: { appId: string; pkg: PackageRead; onSent: () => void }) {
  const integ = useQuery({ queryKey: ["integrations"], queryFn: api.getIntegrations });
  const [sendOpen, setSendOpen] = useState(false);
  const draft = useMutation({
    mutationFn: () => api.createGmailDraft(appId),
    onSuccess: (r) => toast.success("Draft created in Gmail", { description: <a href={r.open_url} target="_blank" rel="noopener noreferrer" className="underline">Open Gmail drafts<span className="sr-only"> (opens in a new tab)</span></a> }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const g = integ.data?.google;
  if (!g?.connected) return null;
  return (
    <div className="space-y-2 rounded-md border p-3">
      <p className="text-sm font-medium">Gmail ({g.account})</p>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={() => draft.mutate()} disabled={draft.isPending}>{draft.isPending ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <Mail aria-hidden className="size-4" />}Put in Gmail drafts</Button>
        <Button size="sm" variant="outline" onClick={() => setSendOpen(true)} disabled={!pkg.package_hash}><ExternalLink aria-hidden className="size-4" />Send from Gmail…</Button>
      </div>
      <p className="text-xs text-muted-foreground">Putting it in your drafts sends nothing.</p>
      {sendOpen && <SendEmailDialog appId={appId} pkg={pkg} account={g.account ?? "your Gmail account"} onOpenChange={setSendOpen} onSent={() => { setSendOpen(false); onSent(); }} />}
    </div>
  );
}

export function SendEmailDialog({ appId, pkg, account, onOpenChange, onSent }: { appId: string; pkg: PackageRead; account: string; onOpenChange: (o: boolean) => void; onSent: () => void }) {
  const [to, setTo] = useState(defaultRecipient(pkg.contact_emails));
  const [checked, setChecked] = useState(false);
  // Mutations never retry: a failed send must not be repeated automatically.
  const send = useMutation({
    mutationFn: () => api.sendEmail(appId, buildSendEmail(pkg.package_hash ?? "", to)),
    retry: false,
    onSuccess: () => { toast.success("Email sent from Gmail. Recorded as sent."); onSent(); },
  });
  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Send from Gmail</DialogTitle>
          <DialogDescription>This sends the email now from {account}. It cannot be undone.</DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); send.mutate(); }}>
          <div className="space-y-1.5">
            <Label htmlFor="send-to">Recipient</Label>
            <Input id="send-to" type="email" required value={to} onChange={(e) => setTo(e.target.value)} autoComplete="off" />
          </div>
          <div className="text-sm">
            <p className="font-medium">Attachments</p>
            <ul className="text-muted-foreground">{pkg.files.map((f) => <li key={f.filename}>{f.filename}</li>)}</ul>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="send-check" checked={checked} onCheckedChange={(v) => setChecked(v === true)} />
            <Label htmlFor="send-check" className="font-normal">I checked the recipient and the documents</Label>
          </div>
          <div aria-live="polite">{send.error && <p role="alert" className="text-sm text-destructive">{errorMessage(send.error)}</p>}</div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={!checked || !to.trim() || send.isPending || send.isError}>{send.isPending && <Loader2 aria-hidden className="size-4 animate-spin" />}Send email</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
