import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { selectClass } from "@/components/field";
import { api, errorMessage, isApiError } from "@/api";
import { buildApplicationCreate, type PrepareChoice } from "@/lib/applications";
import { cn } from "@/lib/utils";
import { RECOMMENDED_NOTE, RECOMMENDED_TEMPLATE, sortTemplates } from "@/lib/account";
import type { DraftKind, DraftSource, TemplateRead } from "@/api/types";

/** "Prepare application" or, when an open application exists, "Open application". */
export function PrepareApplicationButton({ jobId }: { jobId: string }) {
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ["applications", { job_id: jobId }], queryFn: () => api.listApplications({ job_id: jobId }) });
  const existing = q.data?.items.find((a) => a.status === "draft" || a.status === "ready");
  if (existing) return <Button asChild size="sm"><Link to="/applications/$id" params={{ id: existing.id }}><FileText aria-hidden className="size-4" />Open application</Link></Button>;
  return (
    <>
      <Button size="sm" onClick={() => setOpen(true)} disabled={q.isLoading}><FileText aria-hidden className="size-4" />Prepare application</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Prepare application</DialogTitle>
            <DialogDescription>DuuniScript prepares drafts for you to check. Nothing is sent.</DialogDescription>
          </DialogHeader>
          {open && <PrepareForm jobId={jobId} onCancel={() => setOpen(false)} />}
        </DialogContent>
      </Dialog>
    </>
  );
}

export function PrepareForm({ jobId, onCancel }: { jobId: string; onCancel: () => void }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const templates = useQuery({ queryKey: ["templates"], queryFn: api.listTemplates });
  const profiles = useQuery({ queryKey: ["cvProfiles"], queryFn: api.listCvProfiles });
  const cvs = useQuery({ queryKey: ["documents", { category: "cv" }], queryFn: () => api.listDocuments({ category: "cv" }) });
  const [c, setC] = useState<PrepareChoice>({ cvSource: "generated", cvTemplate: "", cvDocumentId: "", includeLetter: true, letterTemplate: "", cvProfile: "auto" });
  const create = useMutation({
    mutationFn: () => api.createApplication(buildApplicationCreate(jobId, c)),
    onSuccess: (a) => { qc.invalidateQueries({ queryKey: ["applications"] }); navigate({ to: "/applications/$id", params: { id: a.id } }); },
    onError: (e) => {
      if (isApiError(e) && e.code === "application_exists" && typeof e.details["application_id"] === "string")
        navigate({ to: "/applications/$id", params: { id: e.details["application_id"] } });
    },
  });
  const err = create.error;
  const of = (kind: DraftKind) => sortTemplates(templates.data?.filter((t) => t.kind === kind) ?? []);
  const activeCvs = cvs.data?.items.filter((d) => !d.archived_at) ?? [];
  const canCreate = c.cvSource === "generated" || !!c.cvDocumentId;

  return (
    <form className="space-y-6" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
      <div className="space-y-1.5"><Label htmlFor="prepare-cv-profile">CV profile</Label><select id="prepare-cv-profile" className={selectClass} value={c.cvProfile} onChange={(e) => setC((s) => ({ ...s, cvProfile: e.target.value }))}><option value="auto">Pick automatically</option><option value="none">None</option>{profiles.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select>{profiles.isError && <p role="alert" className="plain-text text-sm text-destructive">{errorMessage(profiles.error)}</p>}</div>
      <fieldset className="space-y-3">
        <legend className="mb-2 font-medium">CV</legend>
        <RadioGroup value={c.cvSource} onValueChange={(v) => setC((s) => ({ ...s, cvSource: v as DraftSource }))}>
          <div className="flex items-center gap-2"><RadioGroupItem id="cv-gen" value="generated" /><Label htmlFor="cv-gen" className="font-normal">Build from my verified facts</Label></div>
          <div className="flex items-center gap-2"><RadioGroupItem id="cv-up" value="uploaded" /><Label htmlFor="cv-up" className="font-normal">Use one of my uploaded CVs as it is</Label></div>
        </RadioGroup>
        {c.cvSource === "generated"
          ? <TemplateCards name="CV template" items={of("cv")} value={c.cvTemplate} onChange={(k) => setC((s) => ({ ...s, cvTemplate: k }))} />
          : (
            <div className="space-y-1.5">
              <Label htmlFor="cv-doc">Uploaded CV</Label>
              <select id="cv-doc" className={selectClass} value={c.cvDocumentId} onChange={(e) => setC((s) => ({ ...s, cvDocumentId: e.target.value }))}>
                <option value="">Choose a CV</option>
                {activeCvs.map((d) => <option key={d.id} value={d.id}>{d.display_name}</option>)}
              </select>
              {cvs.isSuccess && activeCvs.length === 0 && <p className="text-xs text-muted-foreground">No uploaded CVs yet. Add one on the Documents page.</p>}
            </div>
          )}
      </fieldset>
      <fieldset className="space-y-3">
        <legend className="sr-only">Cover letter</legend>
        <div className="flex items-center gap-2">
          <Switch id="inc-letter" checked={c.includeLetter} onCheckedChange={(v) => setC((s) => ({ ...s, includeLetter: v }))} />
          <Label htmlFor="inc-letter">Include a cover letter</Label>
        </div>
        {c.includeLetter && <TemplateCards name="Cover letter template" items={of("cover_letter")} value={c.letterTemplate} onChange={(k) => setC((s) => ({ ...s, letterTemplate: k }))} />}
      </fieldset>
      <div aria-live="polite">
        {err && !(isApiError(err) && err.code === "application_exists") && (
          <p role="alert" className="text-sm text-destructive">
            {errorMessage(err)}
            {isApiError(err) && err.code === "no_verified_facts" && <> <Link to="/profile" className="underline">Go to your profile</Link></>}
          </p>
        )}
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>
        <Button type="submit" disabled={!canCreate || create.isPending}>{create.isPending && <Loader2 aria-hidden className="size-4 animate-spin" />}Create drafts</Button>
      </DialogFooter>
    </form>
  );
}

function TemplateCards({ name, items, value, onChange }: { name: string; items: TemplateRead[]; value: string; onChange: (k: string) => void }) {
  return (
    <RadioGroup aria-label={name} value={value} onValueChange={onChange} className="grid gap-2 sm:grid-cols-2">
      <Label htmlFor={`tpl-auto-${name}`} className={cn("flex cursor-pointer items-start gap-3 rounded-md border p-3 font-normal", value === "" && "border-primary bg-accent")}><RadioGroupItem id={`tpl-auto-${name}`} value="" className="mt-0.5" /><span><span className="block font-medium">Pick automatically</span><span className="text-xs text-muted-foreground">UTU Rekry, or UTU Rekry (suomeksi) for Finnish postings</span></span></Label>
      {items.map((t) => (
        <Label key={t.key} htmlFor={`tpl-${t.kind}-${t.key}`} className={cn("flex cursor-pointer items-start gap-3 rounded-md border p-3 font-normal", value === t.key && "border-primary bg-accent")}>
          <RadioGroupItem id={`tpl-${t.kind}-${t.key}`} value={t.key} className="mt-0.5" />
          <span><span className="block font-medium">{t.name}</span>{t.key === RECOMMENDED_TEMPLATE && <span className="mt-0.5 block text-xs font-medium text-primary">{RECOMMENDED_NOTE}</span>}<span className="block text-xs text-muted-foreground">{t.description}</span></span>
        </Label>
      ))}
    </RadioGroup>
  );
}
