import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Field, describedBy, selectClass } from "@/components/field";
import { ErrorState, LoadingState } from "@/components/states";
import { StatusBadge } from "@/components/status-badge";
import { FactForm, factToForm, type FactFormValues } from "./fact-form";
import { api, errorMessage, fieldErrors, isApiError } from "@/api";
import { formatDate, formatDateOnly } from "@/lib/format";
import { EVIDENCE_TYPE, EVIDENCE_TYPE_ALL, FACT_CATEGORY, VERIFICATION } from "@/lib/labels";
import type { EvidenceCreate, FactRead, FactUpdate } from "@/api/types";

const n = (s: string) => (s.trim() === "" ? null : s);

export function dateRange(f: Pick<FactRead, "valid_from" | "valid_until">) {
  const a = formatDateOnly(f.valid_from), b = formatDateOnly(f.valid_until);
  if (!a && !b) return null;
  return `${a ?? "…"} – ${b ?? "…"}`;
}

export function FactPanel({ fact, onClose }: { fact: FactRead | null; onClose: () => void }) {
  return (
    <Sheet open={!!fact} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        {fact && <FactPanelBody key={fact.id} factId={fact.id} initial={fact} onClose={onClose} />}
      </SheetContent>
    </Sheet>
  );
}

function FactPanelBody({ factId, initial, onClose }: { factId: string; initial: FactRead; onClose: () => void }) {
  const qc = useQueryClient();
  const factQ = useQuery({ queryKey: ["fact", factId], queryFn: () => api.getFact(factId), initialData: initial });
  const fact = factQ.data;
  const [editing, setEditing] = useState(false);
  const [confirmEdit, setConfirmEdit] = useState<null | ((ok: boolean) => void)>(null);
  const [deleting, setDeleting] = useState(false);

  const applyFact = (f: FactRead) => {
    qc.setQueryData(["fact", factId], f);
    qc.invalidateQueries({ queryKey: ["facts"] });
  };
  const update = useMutation({ mutationFn: (b: FactUpdate) => api.updateFact(factId, b), onSuccess: applyFact });
  const del = useMutation({
    mutationFn: () => api.deleteFact(factId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["facts"] }); toast.success("Fact deleted"); setDeleting(false); onClose(); },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const v = VERIFICATION[fact.verification_status];

  const saveEdit = async (vals: FactFormValues) => {
    const body: FactUpdate = {};
    if (vals.category !== fact.category) body.category = vals.category;
    if (vals.subject !== fact.subject) body.subject = vals.subject;
    if (vals.value_text !== fact.value_text) body.value_text = vals.value_text;
    if (vals.valid_from !== (fact.valid_from ?? "")) body.valid_from = n(vals.valid_from);
    if (vals.valid_until !== (fact.valid_until ?? "")) body.valid_until = n(vals.valid_until);
    if (Object.keys(body).length) {
      await update.mutateAsync(body);
      toast.success("Saved");
    }
    setEditing(false);
  };

  return (
    <>
      <SheetHeader className="space-y-2 text-left">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">{FACT_CATEGORY[fact.category]}</p>
        <SheetTitle className="font-display text-2xl font-medium">{fact.subject}</SheetTitle>
        <SheetDescription asChild>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge tone={v.tone} label={v.label} />
            {fact.verified_at && fact.verification_status === "verified" && <span className="text-xs">on {formatDate(fact.verified_at)}</span>}
          </div>
        </SheetDescription>
      </SheetHeader>

      <div className="mt-6 space-y-6 px-4 pb-6">
        {editing ? (
          <FactForm
            idPrefix="edit-fact" initial={factToForm(fact)} submitLabel="Save changes" onCancel={() => setEditing(false)}
            onSubmit={saveEdit}
            beforeSubmit={() => fact.verification_status === "verified"
              ? new Promise<boolean>((resolve) => setConfirmEdit(() => resolve))
              : Promise.resolve(true)}
          />
        ) : (
          <>
            <p className="plain-text text-sm leading-relaxed">{fact.value_text}</p>
            {dateRange(fact) && <p className="text-sm text-muted-foreground">Valid {dateRange(fact)}</p>}
            <div className="flex flex-wrap gap-2">
              {fact.verification_status !== "verified" && (
                <Button size="sm" disabled={update.isPending} onClick={() =>
                  update.mutateAsync({ verification_status: "verified" }).then(() => toast.success("Fact confirmed"), (e) => toast.error(errorMessage(e)))}>
                  {update.isPending ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <Check aria-hidden className="size-4" />}Confirm this fact
                </Button>
              )}
              <Button size="sm" variant="outline" onClick={() => setEditing(true)}><Pencil aria-hidden className="size-4" />Edit</Button>
              <Button size="sm" variant="ghost" className="text-destructive" onClick={() => setDeleting(true)}><Trash2 aria-hidden className="size-4" />Delete</Button>
            </div>
            {fact.verification_status === "verified" && (
              <p className="text-xs text-muted-foreground">Editing will mark this fact as not yet confirmed.</p>
            )}
          </>
        )}

        <EvidenceSection factId={factId} onAdded={() => qc.invalidateQueries({ queryKey: ["fact", factId] })} />
      </div>

      <ConfirmDialog
        open={!!confirmEdit} onOpenChange={(o) => { if (!o) { confirmEdit?.(false); setConfirmEdit(null); } }}
        title="Save changes?" description="Editing will mark this fact as not yet confirmed. You can confirm it again afterwards."
        confirmLabel="Save changes" destructive={false}
        onConfirm={() => { confirmEdit?.(true); setConfirmEdit(null); }}
      />
      <ConfirmDialog
        open={deleting} onOpenChange={setDeleting} title="Delete this fact?"
        description="This permanently deletes the fact and all of its evidence." confirmLabel="Delete fact"
        pending={del.isPending} onConfirm={() => del.mutate()}
      />
    </>
  );
}

function EvidenceSection({ factId, onAdded }: { factId: string; onAdded: () => void }) {
  const qc = useQueryClient();
  const evQ = useQuery({ queryKey: ["evidence", factId], queryFn: () => api.listEvidence(factId) });
  const docsQ = useQuery({ queryKey: ["documents", { include_archived: true }], queryFn: () => api.listDocuments({ include_archived: true, limit: 200 }) });
  const docName = (id: string | null) => docsQ.data?.items.find((d) => d.id === id)?.display_name ?? "Document";
  const activeDocs = docsQ.data?.items.filter((d) => !d.archived_at) ?? [];

  const [type, setType] = useState<"document" | "url" | "user_input">("document");
  const [docId, setDocId] = useState("");
  const [ref, setRef] = useState("");
  const [excerpt, setExcerpt] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [added, setAdded] = useState(false);

  const add = useMutation({
    mutationFn: (b: EvidenceCreate) => api.createEvidence(factId, b),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["evidence", factId] });
      qc.invalidateQueries({ queryKey: ["facts"] });
      onAdded();
      setDocId(""); setRef(""); setExcerpt(""); setAdded(true);
      toast.success("Evidence added");
    },
    onError: (e) => {
      const fe = fieldErrors(e);
      if (isApiError(e) && (e.code === "document_archived" || e.code === "document_not_found")) fe.document_id = e.message;
      setErrors(fe);
      setFormError(Object.keys(fe).length ? null : errorMessage(e));
    },
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({}); setFormError(null); setAdded(false);
    if (type === "document") add.mutate({ source_type: "document", document_id: docId || null, excerpt: n(excerpt) });
    else add.mutate({ source_type: type, source_reference: n(ref), excerpt: n(excerpt) });
  };

  return (
    <section aria-labelledby="ev-h" className="space-y-4 border-t pt-6">
      <h3 id="ev-h" className="text-lg font-medium">Evidence</h3>
      {evQ.isLoading ? <LoadingState label="Loading evidence…" className="py-2" />
        : evQ.isError ? <ErrorState error={evQ.error} onRetry={() => evQ.refetch()} />
        : evQ.data!.length === 0 ? <p className="text-sm text-muted-foreground">Evidence needed. Add a document, link or note that supports this fact.</p>
        : (
          <ul className="space-y-2">
            {evQ.data!.map((ev) => (
              <li key={ev.id} className="rounded-md border p-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{EVIDENCE_TYPE_ALL[ev.source_type]}</span>
                  <span className="text-xs text-muted-foreground">{formatDate(ev.created_at)}</span>
                </div>
                {ev.source_type === "document" && <p className="mt-1"><Link to="/documents" className="underline">{docName(ev.document_id)}</Link></p>}
                {ev.source_reference && <p className="plain-text mt-1 break-all text-muted-foreground">{ev.source_reference}</p>}
                {ev.excerpt && <blockquote className="plain-text mt-2 border-l-2 pl-3 text-muted-foreground">{ev.excerpt}</blockquote>}
              </li>
            ))}
          </ul>
        )}

      <form onSubmit={submit} className="space-y-3 rounded-md bg-muted/40 p-4" noValidate>
        <p className="text-sm font-medium">Add evidence</p>
        <Field id="ev-type" label="Type">
          <select id="ev-type" className={selectClass} value={type} onChange={(e) => { setType(e.target.value as typeof type); setErrors({}); }}>
            {Object.entries(EVIDENCE_TYPE).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </Field>
        {type === "document" && (
          <Field id="ev-doc" label="Document" required error={errors.document_id} hint={activeDocs.length === 0 ? "No documents yet. Upload one on the Documents page." : undefined}>
            <select id="ev-doc" className={selectClass} value={docId} onChange={(e) => setDocId(e.target.value)} {...describedBy("ev-doc", errors.document_id)}>
              <option value="">Choose a document</option>
              {activeDocs.map((d) => <option key={d.id} value={d.id}>{d.display_name}</option>)}
            </select>
          </Field>
        )}
        {type === "url" && (
          <Field id="ev-ref" label="Web address" required error={errors.source_reference}>
            <Input id="ev-ref" type="url" placeholder="https://" value={ref} onChange={(e) => setRef(e.target.value)} {...describedBy("ev-ref", errors.source_reference)} />
          </Field>
        )}
        {type === "user_input" && (
          <Field id="ev-ref" label="Note" error={errors.source_reference}>
            <Input id="ev-ref" value={ref} onChange={(e) => setRef(e.target.value)} {...describedBy("ev-ref", errors.source_reference)} />
          </Field>
        )}
        <Field id="ev-excerpt" label="Excerpt (optional)" error={errors.excerpt} hint="Up to 2000 characters.">
          <Textarea id="ev-excerpt" rows={3} maxLength={2000} value={excerpt} onChange={(e) => setExcerpt(e.target.value)} {...describedBy("ev-excerpt", errors.excerpt, true)} />
        </Field>
        <div aria-live="polite">
          {formError && <p role="alert" className="text-sm text-destructive">{formError}</p>}
          {added && <p className="text-sm text-success">Evidence added. Confirm the fact when you're satisfied.</p>}
        </div>
        <Button type="submit" size="sm" disabled={add.isPending}>{add.isPending && <Loader2 aria-hidden className="size-4 animate-spin" />}Add evidence</Button>
      </form>
    </section>
  );
}
