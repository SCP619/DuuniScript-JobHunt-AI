import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Copy, Download, ExternalLink, Loader2, Mail } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ErrorState, LoadingState } from "@/components/states";
import { api, errorMessage, isApiError } from "@/api";
import { SUBMISSION_METHOD, buildSubmission, saveBlob } from "@/lib/applications";
import { GmailActions } from "./gmail-actions";
import type { PackageRead, SubmissionMethod } from "@/api/types";

export function SendPanel({ appId, onChanged }: { appId: string; onChanged: () => void }) {
  const q = useQuery({ queryKey: ["package", appId], queryFn: () => api.getPackage(appId) });
  const [recording, setRecording] = useState(false);
  const dl = useMutation({ mutationFn: (w: "zip" | "eml") => (w === "zip" ? api.downloadPackageZip(appId) : api.downloadEmailDraft(appId)), onSuccess: saveBlob, onError: (e) => toast.error(errorMessage(e)) });
  if (q.isLoading) return <LoadingState label="Loading the package…" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const p = q.data!;
  return (
    <section aria-labelledby="send-h" className="space-y-4 rounded-lg border border-primary/30 bg-card p-5">
      <div>
        <h2 id="send-h" className="text-xl font-medium">Ready to send</h2>
        <p className="text-sm text-muted-foreground">DuuniScript does not send anything. Send the application yourself, then record it here.</p>
      </div>
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[max-content_1fr]">
        <dt className="text-muted-foreground">Employer</dt><dd>{p.employer}</dd>
        <dt className="text-muted-foreground">Role</dt><dd>{p.role}</dd>
        <dt className="text-muted-foreground">Where to apply</dt>
        <dd>{p.destination ? <a href={p.destination} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 underline">Open the application page<ExternalLink aria-hidden className="size-3.5" /><span className="sr-only">(opens in a new tab)</span></a> : <span className="text-muted-foreground">Not stated</span>}</dd>
        <dt className="text-muted-foreground">Email in the posting</dt><dd className="break-all">{p.contact_emails.length ? p.contact_emails.join(", ") : <span className="text-muted-foreground">None stated</span>}</dd>
        <dt className="text-muted-foreground">Files</dt>
        <dd><ul>{p.files.map((f) => <li key={f.filename}>{f.filename} <span className="font-mono text-xs text-muted-foreground">{f.sha256.slice(0, 10)}</span></li>)}</ul></dd>
      </dl>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={() => dl.mutate("zip")}><Download aria-hidden className="size-4" />Download all files (.zip)</Button>
        <Button size="sm" variant="outline" onClick={() => dl.mutate("eml")}><Mail aria-hidden className="size-4" />Email draft (.eml)</Button>
        {p.cover_letter_text && <Button size="sm" variant="outline" onClick={() => navigator.clipboard.writeText(p.cover_letter_text!).then(() => toast.success("Copied"), () => toast.error("Couldn't copy"))}><Copy aria-hidden className="size-4" />Copy cover letter text</Button>}
      </div>
      <p className="text-xs text-muted-foreground">The email draft opens in Outlook or another mail program as an unsent draft with the files attached. Check it and send it from there.</p>
      <GmailActions appId={appId} pkg={p} onSent={onChanged} />
      <Button onClick={() => setRecording(true)} disabled={!p.package_hash}>I have sent it</Button>
      <RecordSentDialog open={recording} onOpenChange={setRecording} pkg={p} appId={appId}
        onDone={() => { setRecording(false); onChanged(); }} onChangedPackage={() => { setRecording(false); q.refetch(); onChanged(); }} />
    </section>
  );
}

export function RecordSentDialog({ open, onOpenChange, pkg, appId, onDone, onChangedPackage }: {
  open: boolean; onOpenChange: (o: boolean) => void; pkg: PackageRead; appId: string; onDone: () => void; onChangedPackage: () => void;
}) {
  const [method, setMethod] = useState<SubmissionMethod>("web_form");
  const [ref, setRef] = useState("");
  const [same, setSame] = useState(false);
  const rec = useMutation({
    mutationFn: () => api.recordSubmission(appId, buildSubmission(pkg.package_hash ?? "", method, ref)),
    onSuccess: () => { toast.success("Recorded as sent"); onDone(); },
    onError: (e) => {
      if (isApiError(e) && e.code === "package_changed") { toast.error("The documents changed after you reviewed them. Review them again."); onChangedPackage(); }
    },
  });
  const err = rec.error;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Record as sent</DialogTitle>
          <DialogDescription>Only record this after you have sent the application yourself.</DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); rec.mutate(); }}>
          <fieldset>
            <legend className="mb-2 text-sm font-medium">How did you send it?</legend>
            <RadioGroup value={method} onValueChange={(v) => setMethod(v as SubmissionMethod)}>
              {(Object.keys(SUBMISSION_METHOD) as SubmissionMethod[]).map((m) => (
                <div key={m} className="flex items-center gap-2"><RadioGroupItem id={`m-${m}`} value={m} /><Label htmlFor={`m-${m}`} className="font-normal">{SUBMISSION_METHOD[m]}</Label></div>
              ))}
            </RadioGroup>
          </fieldset>
          <div className="space-y-1.5">
            <Label htmlFor="conf-ref">Confirmation number or reference (optional)</Label>
            <Input id="conf-ref" value={ref} onChange={(e) => setRef(e.target.value)} />
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="same-files" checked={same} onCheckedChange={(v) => setSame(v === true)} />
            <Label htmlFor="same-files" className="font-normal">I sent exactly these files</Label>
          </div>
          <div aria-live="polite">{err && !(isApiError(err) && err.code === "package_changed") && <p role="alert" className="text-sm text-destructive">{errorMessage(err)}</p>}</div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={!same || rec.isPending}>{rec.isPending && <Loader2 aria-hidden className="size-4 animate-spin" />}Record as sent</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
