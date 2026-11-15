import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, ImagePlus, Loader2, X } from "lucide-react";
import { api, errorMessage, fieldErrors } from "@/api";
import type { JobCreate, JobRead } from "@/api/types";
import type { ScreenshotDraftRead } from "@/api/job-additions";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { JobFields, deadlineAtProblem, emptyJobForm, formToCreate, type JobFormValues } from "./job-fields";

export function screenshotFieldsToForm(fields: JobCreate): JobFormValues {
  const form = emptyJobForm();
  const keys = ["title", "company", "url", "application_url", "location", "description", "employment_type", "work_mode", "salary_text", "language", "published_on", "deadline_on"] as const;
  for (const key of keys) form[key] = fields[key] ?? "";
  return form;
}

export function ScreenshotReview({ draft, onSaved }: { draft: ScreenshotDraftRead; onSaved: (job: JobRead) => void }) {
  const [form, setForm] = useState(() => screenshotFieldsToForm(draft.fields));
  const [keepScreenshots, setKeepScreenshots] = useState(true);
  const [applyManually, setApplyManually] = useState(true);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const save = useMutation({ mutationFn: api.createJob, retry: false, onSuccess: onSaved, onError: (e) => setErrors(fieldErrors(e)) });
  return <form className="space-y-4" noValidate onSubmit={(e) => {
    e.preventDefault();
    const problem = deadlineAtProblem(form);
    if (problem) { setErrors({ deadline_at: problem }); return; }
    setErrors({});
    save.mutate({ ...formToCreate(form), added_from: draft.fields.added_from, apply_manually: applyManually, ...(keepScreenshots && draft.screenshot_draft_id ? { screenshot_draft_id: draft.screenshot_draft_id } : {}) });
  }}>
    {draft.warnings.length > 0 && <div className="border-l-2 border-warning bg-warning-soft p-3 text-sm" role="note">
      <h3 className="font-medium">Check these</h3>
      <ul className="mt-1 list-disc space-y-1 pl-5">{draft.warnings.map((warning, i) => <li className="plain-text" key={i}>{warning}</li>)}</ul>
    </div>}
    {draft.method === "text_only" && <p className="text-sm text-warning">Local AI is off: only the text was read. Fill in the title and employer.</p>}
    <JobFields idPrefix="screenshot-job" mode="create" values={form} errors={errors} onChange={(k, v) => setForm((f) => ({ ...f, [k]: v }))} />
    <label className="flex items-start gap-2 text-sm"><Checkbox checked={applyManually} onCheckedChange={(v) => setApplyManually(v === true)} />Apply yourself — I will apply on the site myself</label>
    {draft.screenshot_draft_id && <label className="flex items-start gap-2 text-sm"><Checkbox checked={keepScreenshots} onCheckedChange={(v) => setKeepScreenshots(v === true)} />Keep the screenshots with the job</label>}
    <details className="border-y py-3 text-sm">
      <summary className="cursor-pointer font-medium">{draft.fields.added_from === "text" ? "Pasted posting text" : "Text read from the screenshots"}</summary>
      <pre className="plain-text mt-3 max-h-64 overflow-y-auto font-mono text-xs">{draft.text}</pre>
    </details>
    {save.isError && <p role="alert" className="plain-text text-sm text-destructive">{errorMessage(save.error)}</p>}
    <div className="flex justify-end"><Button type="submit" disabled={save.isPending}>{save.isPending && <Loader2 aria-hidden className="size-4 animate-spin" />}Save</Button></div>
  </form>;
}

export function ScreenshotImport({ onSaved }: { onSaved: (job: JobRead) => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const read = useMutation({ mutationFn: api.readJobScreenshots, retry: false });
  useEffect(() => {
    const urls = files.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
    return () => urls.forEach((url) => URL.revokeObjectURL(url));
  }, [files]);
  const add = (incoming: File[]) => {
    if (files.length + incoming.length > 10) { setError("Choose up to 10 screenshots of one posting."); return; }
    if (incoming.some((f) => !["image/png", "image/jpeg"].includes(f.type))) { setError("Choose PNG or JPEG screenshots."); return; }
    setError(null); setFiles((prev) => [...prev, ...incoming]);
  };
  const move = (index: number, direction: number) => setFiles((prev) => {
    const next = [...prev]; const file = next[index]; const other = next[index + direction];
    if (file && other) { next[index] = other; next[index + direction] = file; }
    return next;
  });
  if (read.data) return <ScreenshotReview draft={read.data} onSaved={onSaved} />;
  return <div className="space-y-4">
    <p className="text-sm text-muted-foreground">Take screenshots of the whole posting, top to bottom. Text is read on this computer.</p>
    <div className="rounded-md border border-dashed p-5 text-center focus-visible:outline-2 focus-visible:outline-ring" tabIndex={0} aria-label="Screenshot drop zone" onPaste={(e) => { const images = Array.from(e.clipboardData.items).filter((item) => item.kind === "file" && item.type.startsWith("image/")).map((item) => item.getAsFile()).filter((file): file is File => file !== null); if (images.length && !read.isPending) { e.preventDefault(); add(images); } }} onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); if (!read.isPending) add(Array.from(e.dataTransfer.files)); }}>
      <input ref={input} type="file" accept="image/png,image/jpeg" multiple aria-label="Screenshot files" className="sr-only" disabled={read.isPending} onChange={(e) => { add(Array.from(e.target.files ?? [])); e.target.value = ""; }} />
      <Button variant="outline" disabled={read.isPending} onClick={() => input.current?.click()}><ImagePlus aria-hidden className="size-4" />Choose screenshots</Button>
      <p className="mt-2 text-xs text-muted-foreground">Drop PNG or JPEG images here · {files.length}/10 · One posting</p>
    </div>
    <ol className="space-y-2">{files.map((file, i) => <li key={`${file.name}-${i}`} className="flex items-center gap-2 rounded-md border p-2">
      {previews[i] && <img src={previews[i]} alt={`Screenshot ${i + 1}`} className="h-16 w-12 shrink-0 object-contain" />}
      <span className="min-w-0 flex-1 break-all text-sm">{i + 1}. {file.name}</span>
      <div className="flex shrink-0 gap-1">
        <Button size="icon" variant="ghost" title="Move up" aria-label={`Move screenshot ${i + 1} up`} disabled={i === 0 || read.isPending} onClick={() => move(i, -1)}><ArrowUp aria-hidden className="size-4" /></Button>
        <Button size="icon" variant="ghost" title="Move down" aria-label={`Move screenshot ${i + 1} down`} disabled={i === files.length - 1 || read.isPending} onClick={() => move(i, 1)}><ArrowDown aria-hidden className="size-4" /></Button>
        <Button size="icon" variant="ghost" title="Remove" aria-label={`Remove screenshot ${i + 1}`} disabled={read.isPending} onClick={() => setFiles((prev) => prev.filter((_, n) => n !== i))}><X aria-hidden className="size-4" /></Button>
      </div>
    </li>)}</ol>
    {(error || read.isError) && <p role="alert" className="plain-text text-sm text-destructive">{error ?? errorMessage(read.error)}</p>}
    {read.isPending && <p role="status" className="text-sm text-muted-foreground">Reading the screenshots… (the first one can take a minute while the local AI starts)</p>}
    <div className="flex justify-end"><Button disabled={!files.length || read.isPending} onClick={() => read.mutate(files)}>{read.isPending && <Loader2 aria-hidden className="size-4 animate-spin" />}Read screenshots</Button></div>
  </div>;
}