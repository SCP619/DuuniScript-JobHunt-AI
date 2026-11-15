import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Field, describedBy } from "@/components/field";
import { JobFields, deadlineAtProblem, emptyJobForm, formToCreate, type JobFormValues } from "./job-fields";
import { api, fieldErrors, isApiError, errorMessage, type ApiError } from "@/api";
import type { JobRead } from "@/api/types";
import { PasteTextImport } from "./paste-text-import";
import { ScreenshotImport } from "./screenshot-import";

type Action = "manual" | "retry" | "later" | "duplicate" | "disable" | "none";

export function importAction(e: unknown): Action {
  if (!isApiError(e)) return "none";
  const reason = e.details.reason as string | undefined;
  switch (e.code) {
    case "duplicate_job": return "duplicate";
    case "no_structured_job_data": return "manual";
    case "url_import_disabled":
    case "source_disabled": return "disable";
    case "fetch_failed":
      if (e.status === 502) return "later";
      if (e.status === 504 || reason === "timeout") return "retry";
      if (reason === "robots_disallowed") return "manual";
      return "none";
    default: return "none";
  }
}

export function AddJobDialog() {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<"link" | "manual" | "screenshots" | "text">("link");
  const [url, setUrl] = useState("");
  const [form, setForm] = useState<JobFormValues>(emptyJobForm());
  const [manualErrors, setManualErrors] = useState<Record<string, string>>({});
  const [manualError, setManualError] = useState<unknown>(null);
  const navigate = useNavigate();
  const qc = useQueryClient();

  const done = (job: JobRead, message = "Job added") => {
    qc.invalidateQueries({ queryKey: ["jobs"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
    qc.invalidateQueries({ queryKey: ["sources"] });
    qc.invalidateQueries({ queryKey: ["job", job.id] });
    toast.success(message);
    setOpen(false);
    navigate({ to: "/jobs/$id", params: { id: job.id } });
  };

  const importMut = useMutation({ mutationFn: (u: string) => api.importJob({ url: u }),
    onSuccess: (r) => done(r.job, r.created ? "Job added" : "This job was already in your list. Added the new listing to it."),
  });
  const createMut = useMutation({
    mutationFn: api.createJob,
    onSuccess: (job) => done(job),
    onError: (e) => { setManualErrors(fieldErrors(e)); setManualError(e); },
  });

  const reset = () => {
    setTab("link"); setUrl(""); setForm(emptyJobForm()); setManualErrors({}); setManualError(null);
    importMut.reset(); createMut.reset();
  };
  const toManual = () => {
    setForm({ ...emptyJobForm(url) });
    setTab("manual");
  };

  const importErr = importMut.error as ApiError | null;
  const action = importAction(importErr);
  const urlFieldError = importErr?.code === "invalid_url" ? importErr.message : fieldErrors(importErr).url;

  const submitManual = (e: React.FormEvent) => {
    e.preventDefault();
    const p = deadlineAtProblem(form);
    if (p) { setManualErrors({ deadline_at: p }); return; }
    setManualErrors({}); setManualError(null);
    createMut.mutate(formToCreate(form));
  };

  const dupId = (e: unknown) => (isApiError(e) && e.code === "duplicate_job" ? (e.details.job_id as string | undefined) : undefined);
  const importDuplicateId = dupId(importErr);
  const manualDuplicateId = dupId(manualError);

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) reset(); }}>
      <DialogTrigger asChild>
        <Button><Plus aria-hidden className="size-4" />Add job</Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Add a job</DialogTitle>
          <DialogDescription>Add a posting from a link, screenshots, or type in the details yourself.</DialogDescription>
        </DialogHeader>
        <Tabs value={tab} onValueChange={(v) => setTab(v as "link" | "manual" | "screenshots" | "text")}>
          <TabsList className="grid h-auto w-full grid-cols-2 sm:grid-cols-4">
            <TabsTrigger value="link">From link</TabsTrigger>
            <TabsTrigger value="text">Paste text</TabsTrigger>
            <TabsTrigger value="manual">Enter manually</TabsTrigger>
            <TabsTrigger value="screenshots" className="whitespace-normal text-center">From screenshots</TabsTrigger>
          </TabsList>

          <TabsContent value="link" className="pt-4">
            <form
              className="space-y-4"
              onSubmit={(e) => { e.preventDefault(); if (url.trim()) importMut.mutate(url.trim()); }}
            >
              <p className="text-sm text-muted-foreground">
                DuuniScript opens this page once and reads the job details the site publishes for search engines. It does not log in or bypass any site rules.
              </p>
              <Field id="import-url" label="Job posting link" error={urlFieldError}>
                <Input id="import-url" type="url" inputMode="url" placeholder="https://" value={url}
                  onChange={(e) => setUrl(e.target.value)} disabled={importMut.isPending} {...describedBy("import-url", urlFieldError)} />
              </Field>

              <div aria-live="polite">
                {importMut.isPending && (
                  <p className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 aria-hidden className="size-4 animate-spin" />Reading the job page…
                  </p>
                )}
                {importErr && importErr.code !== "invalid_url" && (
                  <div role="alert" className="space-y-3 rounded-md border bg-muted/50 p-3 text-sm">
                    <p className="font-medium">{action === "duplicate" ? "Already in your list" : errorMessage(importErr)}</p>
                    {action === "duplicate" && (
                      <p className="text-muted-foreground">{errorMessage(importErr)}</p>
                    )}
                    {action === "later" && <p className="text-muted-foreground">Try again later or add manually.</p>}
                    <div className="flex flex-wrap gap-2">
                       {action === "duplicate" && importDuplicateId && (
                        <Button asChild variant="outline" size="sm">
                          <Link to="/jobs/$id" params={{ id: importDuplicateId }} onClick={() => setOpen(false)}>Open the job</Link>
                        </Button>
                      )}
                      {(action === "manual" || action === "later") && (
                        <Button type="button" variant="outline" size="sm" onClick={toManual}>Add manually instead</Button>
                      )}
                      {action === "retry" && (
                        <Button type="button" variant="outline" size="sm" onClick={() => importMut.mutate(url.trim())}>Retry</Button>
                      )}
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-end">
                <Button type="submit" disabled={importMut.isPending || !url.trim() || action === "disable"}>
                  {importMut.isPending && <Loader2 aria-hidden className="size-4 animate-spin" />}
                  Add from link
                </Button>
              </div>
            </form>
          </TabsContent>

          <TabsContent value="text" className="pt-4"><PasteTextImport onSaved={(job) => done(job)} /></TabsContent>
          <TabsContent value="screenshots" className="pt-4"><ScreenshotImport onSaved={(job) => done(job)} /></TabsContent>
          <TabsContent value="manual" className="pt-4">
            <form className="space-y-4" onSubmit={submitManual} noValidate>
              <JobFields idPrefix="new-job" mode="create" values={form} errors={manualErrors}
                onChange={(k, v) => setForm((f) => ({ ...f, [k]: v }))} />
              <div aria-live="polite">
                {!!manualError && Object.keys(manualErrors).length === 0 && (
                  <div role="alert" className="space-y-2 rounded-md border bg-muted/50 p-3 text-sm">
                    <p className="font-medium">{dupId(manualError) ? "Already in your list" : errorMessage(manualError)}</p>
                    {manualDuplicateId && (
                      <Button asChild variant="outline" size="sm">
                        <Link to="/jobs/$id" params={{ id: manualDuplicateId }} onClick={() => setOpen(false)}>Open the job</Link>
                      </Button>
                    )}
                  </div>
                )}
              </div>
              <div className="flex justify-end">
                <Button type="submit" disabled={createMut.isPending}>
                  {createMut.isPending && <Loader2 aria-hidden className="size-4 animate-spin" />}
                  Add job
                </Button>
              </div>
            </form>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
