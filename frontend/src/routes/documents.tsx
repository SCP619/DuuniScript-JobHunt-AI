import { useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ArchiveRestore, Download, FileText, Loader2, MoreHorizontal, Pencil, RotateCw, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { PageHeader } from "@/components/app-shell";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Field, describedBy, selectClass, selectInline } from "@/components/field";
import { StatusBadge } from "@/components/status-badge";
import { api, errorMessage, fieldErrors, isApiError, type ApiError } from "@/api";
import { formatBytes, formatDate } from "@/lib/format";
import { DOCUMENT_CATEGORIES, DOCUMENT_CATEGORY, EXTRACTION_ERROR } from "@/lib/labels";
import { cn } from "@/lib/utils";
import { saveBlob } from "@/lib/applications";
import { FactSuggestionsDialog } from "@/components/documents/fact-suggestions-dialog";
import type { DocumentCategory, DocumentRead, DocumentUpdate } from "@/api/types";

export const Route = createFileRoute("/documents")({
  head: () => ({
    meta: [
      { title: "Documents — DuuniScript" },
      { name: "description", content: "Your CVs, certificates and other documents, stored on this computer." },
      { property: "og:title", content: "Documents — DuuniScript" },
      { property: "og:description", content: "Your CVs, certificates and other documents, stored on this computer." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: DocumentsPage,
});

function DocumentsPage() {
  const qc = useQueryClient();
  const [category, setCategory] = useState<DocumentCategory | "">("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [viewing, setViewing] = useState<DocumentRead | null>(null);
  const [editing, setEditing] = useState<DocumentRead | null>(null);
  const [deleting, setDeleting] = useState<DocumentRead | null>(null);
  const [inUse, setInUse] = useState<DocumentRead | null>(null);
  const [suggesting, setSuggesting] = useState<DocumentRead | null>(null);
  const params = { category: category || undefined, include_archived: includeArchived || undefined };
  const q = useQuery({ queryKey: ["documents", params], queryFn: () => api.listDocuments(params) });

  const refresh = () => qc.invalidateQueries({ queryKey: ["documents"] });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: DocumentUpdate }) => api.updateDocument(id, body),
    onSuccess: refresh,
  });
  const extract = useMutation({
    mutationFn: (id: string) => api.extractDocument(id),
    onSuccess: (d) => { refresh(); toast(d.extraction_status === "succeeded" ? "Text extracted" : "Extraction finished, but no text could be read"); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const del = useMutation({
    mutationFn: (id: string) => api.deleteDocument(id),
    onSuccess: () => { refresh(); toast.success("Document deleted"); setDeleting(null); },
    onError: (e) => {
      if (isApiError(e) && e.code === "document_in_use") { setInUse(deleting); setDeleting(null); }
      else toast.error(errorMessage(e));
    },
  });
  const archive = (d: DocumentRead, archived: boolean) =>
    update.mutateAsync({ id: d.id, body: { archived } }).then(
      () => toast.success(archived ? "Document archived" : "Document restored"),
      (e) => toast.error(errorMessage(e)),
    );

  return (
    <>
      <PageHeader title="Documents" description="Files you keep for your applications. Uploading a CV doesn't create profile facts by itself. You can review suggested facts from a CV and choose which to add." />
      <UploadZone onUploaded={refresh} />

      <div className="mb-4 mt-8 flex flex-wrap items-center gap-4">
        <h2 className="mr-auto text-xl font-medium">Your documents</h2>
        <label className="sr-only" htmlFor="doc-cat">Category</label>
        <select id="doc-cat" className={selectInline} value={category} onChange={(e) => setCategory(e.target.value as DocumentCategory | "")}>
          <option value="">All categories</option>
          {DOCUMENT_CATEGORIES.map((c) => <option key={c} value={c}>{DOCUMENT_CATEGORY[c]}</option>)}
        </select>
        <div className="flex items-center gap-2">
          <Switch id="doc-archived" checked={includeArchived} onCheckedChange={setIncludeArchived} />
          <Label htmlFor="doc-archived" className="font-normal">Show archived</Label>
        </div>
      </div>

      {q.isLoading ? <LoadingState label="Loading documents…" />
        : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} />
        : q.data!.items.length === 0 ? <EmptyState title="No documents yet">Upload a CV, certificate or other file above.</EmptyState>
        : (
          <ul className="divide-y rounded-lg border bg-card">
            {q.data!.items.map((d) => {
              const href = api.documentContentUrl(d.id);
              return (
                <li key={d.id} className={cn("flex flex-col gap-3 p-4 sm:flex-row sm:items-center", d.archived_at && "opacity-70")}>
                  <FileText aria-hidden className="hidden size-5 shrink-0 text-muted-foreground sm:block" />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">
                      {d.display_name}
                      {d.archived_at && <span className="ml-2 text-xs font-normal text-muted-foreground">(archived)</span>}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {DOCUMENT_CATEGORY[d.category]} · {d.file_extension.toUpperCase()} · {formatBytes(d.size_bytes)} · Uploaded {formatDate(d.created_at)}
                    </p>
                    <div className="mt-1.5"><ExtractionState doc={d} /></div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {d.extraction_status === "failed" && (
                      <Button size="sm" variant="outline" disabled={extract.isPending && extract.variables === d.id} onClick={() => extract.mutate(d.id)}>
                        {extract.isPending && extract.variables === d.id ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <RotateCw aria-hidden className="size-4" />}Try again
                      </Button>
                    )}
                    {d.extraction_status === "succeeded" && (
                      <>
                        <Button size="sm" variant="outline" onClick={() => setViewing(d)}>View text</Button>
                        <Button size="sm" variant="outline" onClick={() => setSuggesting(d)}>Suggest profile facts</Button>
                      </>
                    )}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button size="icon" variant="ghost" aria-label={`More actions for ${d.display_name}`}><MoreHorizontal className="size-4" /></Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        {href ? (
                          <DropdownMenuItem onSelect={() => api.downloadDocument(d.id, d.original_filename).then(saveBlob, (e) => toast.error(errorMessage(e)))}><Download aria-hidden className="size-4" />Download original</DropdownMenuItem>
                        ) : (
                          <DropdownMenuItem disabled><Download aria-hidden className="size-4" />Download (not available with sample data)</DropdownMenuItem>
                        )}
                        <DropdownMenuItem onSelect={() => setEditing(d)}><Pencil aria-hidden className="size-4" />Rename or change category</DropdownMenuItem>
                        {d.archived_at
                          ? <DropdownMenuItem onSelect={() => archive(d, false)}><ArchiveRestore aria-hidden className="size-4" />Restore from archive</DropdownMenuItem>
                          : <DropdownMenuItem onSelect={() => archive(d, true)}><Archive aria-hidden className="size-4" />Archive</DropdownMenuItem>}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem className="text-destructive" onSelect={() => setDeleting(d)}><Trash2 aria-hidden className="size-4" />Delete</DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </li>
              );
            })}
          </ul>
        )}

      <FactSuggestionsDialog doc={suggesting} onClose={() => setSuggesting(null)} />
      <TextDialog doc={viewing} onClose={() => setViewing(null)} />
      <EditDialog doc={editing} onClose={() => setEditing(null)} onSave={(body) => update.mutateAsync({ id: editing!.id, body })} />
      <ConfirmDialog
        open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)} title={`Delete “${deleting?.display_name ?? ""}”?`}
        description="Permanently deletes the original file and its extracted text." confirmLabel="Delete document"
        pending={del.isPending} onConfirm={() => deleting && del.mutate(deleting.id)}
      />
      <ConfirmDialog
        open={!!inUse} onOpenChange={(o) => !o && setInUse(null)} title="This document is in use"
        description="Profile evidence uses this document, so it can't be deleted. You can archive it instead: it stays linked to existing evidence but is hidden and can't be used as new evidence."
        confirmLabel="Archive instead" destructive={false} pending={update.isPending}
        onConfirm={() => inUse && archive(inUse, true).then(() => setInUse(null))}
      />
    </>
  );
}

export function ExtractionState({ doc }: { doc: DocumentRead }) {
  const image = ["png", "jpg", "jpeg"].includes(doc.file_extension.toLowerCase());
  const state = (() => {
    switch (doc.extraction_status) {
      case "succeeded": return <StatusBadge tone="success" label={`Text extracted (${(doc.extracted_char_count ?? 0).toLocaleString("fi-FI")} characters)`} />;
      case "pending": return <StatusBadge tone="info" label="Extracting…" />;
      case "no_text": return <StatusBadge tone="warning" label={image ? "No text was found in this image." : "No text found. This may be a scanned document; scanning (OCR) isn't supported yet."} className="whitespace-normal" />;
      case "failed": return <StatusBadge tone="danger" label={doc.extraction_error === "ocr_unavailable" ? EXTRACTION_ERROR.ocr_unavailable! : `Text extraction failed: ${EXTRACTION_ERROR[doc.extraction_error ?? ""] ?? "The file couldn't be read"}`} className="whitespace-normal" />;
    }
  })();
  return <div className="flex flex-wrap gap-1.5">{doc.extraction_method === "ocr" && <StatusBadge tone="info" label="Read from an image" />}{state}</div>;
}

const UPLOAD_ERRORS = ["unsupported_file_type", "file_too_large", "file_content_mismatch", "unsafe_archive", "empty_file", "unsupported_encoding", "duplicate_document"];

function UploadZone({ onUploaded }: { onUploaded: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState<DocumentCategory>("cv");
  const [name, setName] = useState("");
  const [drag, setDrag] = useState(false);
  const upload = useMutation({
    mutationFn: api.uploadDocument,
    onSuccess: () => { toast.success("Document uploaded"); setFile(null); setName(""); if (inputRef.current) inputRef.current.value = ""; onUploaded(); },
  });
  const err = upload.error as ApiError | null;
  const fe = fieldErrors(err);

  return (
    <section aria-labelledby="up-h" className="rounded-lg border bg-card p-5">
      <h2 id="up-h" className="mb-4 text-xl font-medium">Upload a document</h2>
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) { setFile(f); upload.reset(); } }}
        className={cn("flex flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed px-4 py-8 text-center transition-colors", drag ? "border-primary bg-accent" : "border-border")}
      >
        <Upload aria-hidden className="size-6 text-muted-foreground" />
        <p className="text-sm">{file ? <span className="font-medium">{file.name} ({formatBytes(file.size)})</span> : "Drag a file here, or"}</p>
        <Button type="button" variant="outline" size="sm" onClick={() => inputRef.current?.click()}>{file ? "Choose another file" : "Choose a file"}</Button>
        <input ref={inputRef} id="doc-file" type="file" className="sr-only" accept=".pdf,.docx,.txt,.md,.html,.htm,.png,.jpg,.jpeg,text/html,application/pdf,text/plain,text/markdown,image/png,image/jpeg,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          onChange={(e) => { setFile(e.target.files?.[0] ?? null); upload.reset(); }} aria-label="Choose a file to upload" />
        <p className="text-xs text-muted-foreground">PDF, Word (.docx), text, Markdown, a saved web page (.html), or a photo or scan (.png, .jpg) · up to 20 MB</p>
      </div>
      <form className="mt-4 grid gap-4 sm:grid-cols-[200px_1fr_auto] sm:items-end"
        onSubmit={(e) => { e.preventDefault(); if (file) upload.mutate({ file, category, display_name: name.trim() || null }); }}>
        <Field id="up-cat" label="Category" error={fe.category}>
          <select id="up-cat" className={selectClass} value={category} onChange={(e) => setCategory(e.target.value as DocumentCategory)}>
            {DOCUMENT_CATEGORIES.map((c) => <option key={c} value={c}>{DOCUMENT_CATEGORY[c]}</option>)}
          </select>
        </Field>
        <Field id="up-name" label="Display name (optional)" error={fe.display_name}>
          <Input id="up-name" value={name} maxLength={200} onChange={(e) => setName(e.target.value)} {...describedBy("up-name", fe.display_name)} />
        </Field>
        <Button type="submit" disabled={!file || upload.isPending}>{upload.isPending && <Loader2 aria-hidden className="size-4 animate-spin" />}Upload</Button>
      </form>
      <div aria-live="polite">
        {upload.isPending && <p className="mt-3 text-sm text-muted-foreground">Uploading and reading the file…</p>}
        {err && !Object.keys(fe).length && (
          <p role="alert" className="mt-3 text-sm text-destructive">
            {errorMessage(err)}
            {err.code === "duplicate_document" && " It's already in your list below."}
            {!UPLOAD_ERRORS.includes(err.code) && ""}
          </p>
        )}
      </div>
    </section>
  );
}

function TextDialog({ doc, onClose }: { doc: DocumentRead | null; onClose: () => void }) {
  const q = useQuery({ queryKey: ["docText", doc?.id], queryFn: () => api.getDocumentText(doc!.id), enabled: !!doc });
  return (
    <Dialog open={!!doc} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{doc?.display_name}</DialogTitle>
          <DialogDescription>Extracted text (may contain errors)</DialogDescription>
        </DialogHeader>
        {q.isLoading ? <LoadingState /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} />
          : q.data?.text ? (
            <>
            {doc?.extraction_method === "ocr" && <p className="mb-3 border-l-2 border-warning bg-warning-soft p-3 text-sm">This text was recognised from an image. Check names, dates and numbers carefully.</p>}
            <div tabIndex={0} role="region" aria-label="Extracted text (may contain errors)" className="plain-text max-h-[60vh] overflow-y-auto rounded-md border bg-muted/30 p-4 font-mono text-xs leading-relaxed">
              {q.data.text}
            </div>
            </>
          ) : <p className="text-sm text-muted-foreground">No text is available for this document.</p>}
      </DialogContent>
    </Dialog>
  );
}

function EditDialog({ doc, onClose, onSave }: { doc: DocumentRead | null; onClose: () => void; onSave: (b: DocumentUpdate) => Promise<unknown> }) {
  return (
    <Dialog open={!!doc} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit document</DialogTitle>
          <DialogDescription>Change the name or category.</DialogDescription>
        </DialogHeader>
        {doc && <EditForm key={doc.id} doc={doc} onClose={onClose} onSave={onSave} />}
      </DialogContent>
    </Dialog>
  );
}

function EditForm({ doc, onClose, onSave }: { doc: DocumentRead; onClose: () => void; onSave: (b: DocumentUpdate) => Promise<unknown> }) {
  const [name, setName] = useState(doc.display_name);
  const [cat, setCat] = useState<DocumentCategory>(doc.category);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  return (
    <form className="space-y-4" noValidate onSubmit={async (e) => {
      e.preventDefault();
      const body: DocumentUpdate = {};
      if (name !== doc.display_name) body.display_name = name;
      if (cat !== doc.category) body.category = cat;
      if (!Object.keys(body).length) return onClose();
      setPending(true); setErrors({}); setFormError(null);
      try { await onSave(body); toast.success("Saved"); onClose(); }
      catch (err) { const fe = fieldErrors(err); setErrors(fe); if (!Object.keys(fe).length) setFormError(errorMessage(err)); }
      finally { setPending(false); }
    }}>
      <Field id="ed-name" label="Display name" required error={errors.display_name}>
        <Input id="ed-name" value={name} maxLength={200} onChange={(e) => setName(e.target.value)} {...describedBy("ed-name", errors.display_name)} />
      </Field>
      <Field id="ed-cat" label="Category" error={errors.category}>
        <select id="ed-cat" className={selectClass} value={cat} onChange={(e) => setCat(e.target.value as DocumentCategory)}>
          {DOCUMENT_CATEGORIES.map((c) => <option key={c} value={c}>{DOCUMENT_CATEGORY[c]}</option>)}
        </select>
      </Field>
      {formError && <p role="alert" className="text-sm text-destructive">{formError}</p>}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
        <Button type="submit" disabled={pending}>{pending && <Loader2 aria-hidden className="size-4 animate-spin" />}Save</Button>
      </div>
    </form>
  );
}
