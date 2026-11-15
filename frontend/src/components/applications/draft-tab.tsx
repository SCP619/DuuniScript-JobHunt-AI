import { useEffect, useState } from "react";
import { useBlocker } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ChevronDown, Download, Loader2, Pencil, RotateCw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { selectClass, selectInline } from "@/components/field";
import { DraftPreview } from "./draft-preview";
import { ChecksPanel } from "./issues";
import { ApproveControl } from "./approve-control";
import { api, errorMessage } from "@/api";
import { formatRelative } from "@/lib/format";
import { saveBlob } from "@/lib/applications";
import { RECOMMENDED_TEMPLATE, sortTemplates } from "@/lib/account";
import { PolishControl } from "./polish";
import type { ApplicationRead, DraftKind, DraftRead, ExportFormat, TemplateRead } from "@/api/types";

const FORMATS: [ExportFormat, string][] = [["pdf", "PDF"], ["docx", "Word"], ["md", "Markdown"], ["txt", "Text"]];

export function DraftTab({ app, kind, templates, locked, onChanged }: {
  app: ApplicationRead; kind: DraftKind; templates: TemplateRead[]; locked: boolean; onChanged: () => void;
}) {
  const draft = app[kind];
  if (!draft) return <p className="text-sm text-muted-foreground">No draft yet.</p>;
  return <DraftBody key={`${draft.id}-${draft.version}-${draft.status}`} app={app} draft={draft} kind={kind} templates={templates} locked={locked} onChanged={onChanged} />;
}

function DraftBody({ app, draft, kind, templates, locked, onChanged }: {
  app: ApplicationRead; draft: DraftRead; kind: DraftKind; templates: TemplateRead[]; locked: boolean; onChanged: () => void;
}) {
  const label = kind === "cv" ? "CV" : "cover letter";
  const mine = sortTemplates(templates.filter((t) => t.kind === kind));
  const tplName = mine.find((t) => t.key === draft.template)?.name ?? draft.template ?? "Template";
  const approved = draft.status === "approved";
  const [text, setText] = useState(draft.content ?? "");
  const [unlocked, setUnlocked] = useState(!approved);
  const [tpl, setTpl] = useState(draft.template ?? mine[0]?.key ?? "");
  const [rebuildOpen, setRebuildOpen] = useState(false);
  const [uploadPick, setUploadPick] = useState("");
  const dirty = draft.source === "generated" && text !== (draft.content ?? "");
  const editable = !locked && unlocked;

  useBlocker({ shouldBlockFn: () => dirty && !window.confirm("You have unsaved changes. Leave without saving?"), enableBeforeUnload: () => dirty });

  const done = (msg: string) => () => { toast.success(msg); onChanged(); };
  const save = useMutation({ mutationFn: () => api.saveDraft(app.id, kind, { source: "generated", content: text }), onSuccess: done("Saved"), onError: (e) => toast.error(errorMessage(e)) });
  const useUpload = useMutation({ mutationFn: (document_id: string) => api.saveDraft(app.id, kind, { source: "uploaded", document_id }), onSuccess: done("Saved"), onError: (e) => toast.error(errorMessage(e)) });
  const rebuild = useMutation({ mutationFn: () => api.regenerateDraft(app.id, kind, { template: tpl || null }), onSuccess: () => { setRebuildOpen(false); done("New version created")(); }, onError: (e) => toast.error(errorMessage(e)) });
  const exp = useMutation({ mutationFn: (f: ExportFormat) => api.exportDraft(app.id, kind, f), onSuccess: saveBlob, onError: (e) => toast.error(errorMessage(e)) });
  const cvs = useQuery({ queryKey: ["documents", { category: "cv" }], queryFn: () => api.listDocuments({ category: "cv" }), enabled: kind === "cv" && !locked });
  const facts = useQuery({ queryKey: ["facts", { verification_status: "verified", limit: 200 }], queryFn: () => api.listFacts({ verification_status: "verified", limit: 200 }), enabled: draft.evidence_fact_ids.length > 0 });
  const used = facts.data?.items.filter((f) => draft.evidence_fact_ids.includes(f.id)) ?? [];

  useEffect(() => { setText(draft.content ?? ""); }, [draft.content]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <p className="mr-auto text-sm text-muted-foreground">
          Version {draft.version} · {draft.source === "uploaded" ? `Uploaded file: ${draft.document_name ?? "CV"}` : tplName} · {approved ? `Approved ${formatRelative(draft.approved_at) ?? ""}` : "Draft"}
        </p>
        <DropdownMenu>
          <DropdownMenuTrigger asChild><Button size="sm" variant="outline"><Download aria-hidden className="size-4" />Download<ChevronDown aria-hidden className="size-3.5" /></Button></DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {FORMATS.map(([f, l]) => <DropdownMenuItem key={f} onSelect={() => exp.mutate(f)}>{l}</DropdownMenuItem>)}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {draft.source === "uploaded" ? (
        <div className="rounded-lg border bg-card p-4 text-sm">
          <p className="font-medium">{draft.document_name ?? "Uploaded CV"}</p>
          {(() => { const href = draft.document_id ? api.documentContentUrl(draft.document_id) : null; return href ? <button type="button" className="underline" onClick={() => api.downloadDocument(draft.document_id!, draft.document_name ?? "cv").then(saveBlob, (e) => toast.error(errorMessage(e)))}>Download the file</button> : <p className="text-muted-foreground">Download is not available with sample data.</p>; })()}
          <p className="mt-2 text-muted-foreground">This file is sent exactly as it is.</p>
        </div>
      ) : (
        <>
          {approved && !locked && (
            <div className="flex flex-wrap items-center gap-3 rounded-md border bg-secondary p-3 text-sm">
              <span className="mr-auto">{unlocked ? `Editing creates version ${draft.version + 1}; you will need to approve it again.` : "This version is approved and read-only."}</span>
              {!unlocked && <Button size="sm" variant="outline" onClick={() => setUnlocked(true)}><Pencil aria-hidden className="size-4" />Edit</Button>}
            </div>
          )}
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor={`ed-${kind}`}>Text</Label>
              <textarea id={`ed-${kind}`} value={text} readOnly={!editable} onChange={(e) => setText(e.target.value)} rows={22}
                className="w-full rounded-md border border-input bg-card p-3 font-mono text-xs leading-relaxed focus-visible:outline-2 focus-visible:outline-ring read-only:bg-muted/30" />
              <p className="text-xs text-muted-foreground"><code># Name</code> · <code>## Section</code> · <code>### Entry</code> · <code>*dates*</code> · <code>- bullet</code> · other lines are paragraphs</p>
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium" id={`pv-${kind}`}>Preview</p>
              <div aria-labelledby={`pv-${kind}`} role="region" className="min-h-40 rounded-md border bg-card p-5"><DraftPreview content={text} /></div>
            </div>
          </div>
          {!locked && (
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>{save.isPending && <Loader2 aria-hidden className="size-4 animate-spin" />}Save</Button>
              <label className="sr-only" htmlFor={`tpl-${kind}`}>Template</label>
              <select id={`tpl-${kind}`} className={selectInline} value={tpl} onChange={(e) => setTpl(e.target.value)}>
                {mine.map((t) => <option key={t.key} value={t.key}>{t.key === RECOMMENDED_TEMPLATE ? `${t.name} (recommended)` : t.name}</option>)}
              </select>
              <Button size="sm" variant="outline" onClick={() => setRebuildOpen(true)}><RotateCw aria-hidden className="size-4" />Rebuild from my facts</Button>
            </div>
          )}
          {editable && <PolishControl appId={app.id} kind={kind} current={text} onUse={setText} />}
        </>
      )}

      {kind === "cv" && !locked && (
        <div className="flex flex-wrap items-end gap-2 text-sm">
          <div className="space-y-1.5">
            <Label htmlFor="use-upload">{draft.source === "uploaded" ? "Use a different uploaded CV" : "Use an uploaded CV instead"}</Label>
            <select id="use-upload" className={selectClass} value={uploadPick} onChange={(e) => setUploadPick(e.target.value)}>
              <option value="">Choose a CV</option>
              {cvs.data?.items.filter((d) => !d.archived_at).map((d) => <option key={d.id} value={d.id}>{d.display_name}</option>)}
            </select>
          </div>
          <Button size="sm" variant="outline" disabled={!uploadPick || useUpload.isPending} onClick={() => useUpload.mutate(uploadPick)}>Use this file</Button>
          {draft.source === "uploaded" && <Button size="sm" variant="ghost" onClick={() => setRebuildOpen(true)}>Build from my facts instead</Button>}
        </div>
      )}

      <ChecksPanel issues={draft.issues} />
      {!locked && !approved && <ApproveControl label={`Approve ${label}`} issues={draft.issues} onApprove={async (ack) => { await api.approveDraft(app.id, kind, { acknowledge_warnings: ack }); toast.success("Approved"); onChanged(); }} />}

      {draft.evidence_fact_ids.length > 0 && (
        <Collapsible>
          <CollapsibleTrigger className="inline-flex items-center gap-1 text-sm font-medium hover:underline"><ChevronDown aria-hidden className="size-4" />Built from {draft.evidence_fact_ids.length} verified fact{draft.evidence_fact_ids.length === 1 ? "" : "s"}</CollapsibleTrigger>
          <CollapsibleContent>
            <ul className="mt-2 space-y-1 text-sm">
              {used.map((f) => <li key={f.id}><span className="font-medium">{f.subject}</span> <span className="text-muted-foreground">— {f.value_text}</span></li>)}
              {facts.isSuccess && used.length < draft.evidence_fact_ids.length && <li className="text-muted-foreground">Some facts are no longer verified or were removed.</li>}
            </ul>
          </CollapsibleContent>
        </Collapsible>
      )}

      <ConfirmDialog open={rebuildOpen} onOpenChange={setRebuildOpen} title="Rebuild from your facts?" destructive={false}
        description="This creates a new version from your verified facts. Your edits stay in the older version."
        confirmLabel="Rebuild" pending={rebuild.isPending} onConfirm={() => rebuild.mutate()} />
    </div>
  );
}
