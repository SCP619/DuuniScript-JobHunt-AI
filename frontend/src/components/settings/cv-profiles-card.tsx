import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, errorMessage } from "@/api";
import type { CvProfileInput, CvProfileRead } from "@/api/job-additions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field, selectClass } from "@/components/field";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { ErrorState, LoadingState } from "@/components/states";
export function CvProfilesCard() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["cvProfiles"], queryFn: api.listCvProfiles });
  const [edit, setEdit] = useState<CvProfileRead | "new" | null>(null);
  const [remove, setRemove] = useState<CvProfileRead | null>(null);
  const refresh = () => { qc.invalidateQueries({ queryKey: ["cvProfiles"] }); };
  const del = useMutation({ mutationFn: (id: string) => api.deleteCvProfile(id), onSuccess: () => { setRemove(null); refresh(); toast.success("CV profile deleted"); }, onError: (e) => toast.error(errorMessage(e)) });
  return <section aria-labelledby="cv-profiles-h" className="space-y-4 border-y py-5">
    <div className="flex items-center justify-between gap-3"><h2 id="cv-profiles-h" className="text-xl font-medium">CV profiles</h2><Button size="sm" variant="outline" onClick={() => setEdit("new")}><Plus aria-hidden className="size-4" />Add profile</Button></div>
    {q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : !q.data ? <LoadingState /> : <ul className="divide-y">{q.data.map((p) => <li key={p.id} className="flex items-center gap-3 py-3"><div className="min-w-0 flex-1"><p className="plain-text font-medium">{p.name}</p><p className="plain-text text-xs text-muted-foreground">{p.focus}</p>{p.summary && <p className="plain-text mt-1 text-sm">{p.summary}</p>}</div><Button size="icon" variant="ghost" title="Edit profile" aria-label={`Edit ${p.name}`} onClick={() => setEdit(p)}><Pencil aria-hidden className="size-4" /></Button><Button size="icon" variant="ghost" title="Delete profile" aria-label={`Delete ${p.name}`} onClick={() => setRemove(p)}><Trash2 aria-hidden className="size-4" /></Button></li>)}</ul>}
    {q.data?.length === 0 && <p className="text-sm text-muted-foreground">No CV profiles yet.</p>}
    {edit && <ProfileForm key={edit === "new" ? "new" : edit.id} profile={edit === "new" ? null : edit} onCancel={() => setEdit(null)} onSaved={() => { setEdit(null); refresh(); }} />}
    <ConfirmDialog open={!!remove} onOpenChange={(v) => { if (!v) setRemove(null); }} title="Delete CV profile?" description="The profile will be removed. Your existing applications stay unchanged." confirmLabel="Delete profile" pending={del.isPending} onConfirm={() => { if (remove) del.mutate(remove.id); }} />
  </section>;
}
function ProfileForm({ profile, onCancel, onSaved }: { profile: CvProfileRead | null; onCancel: () => void; onSaved: () => void }) {
  const [name, setName] = useState(profile?.name ?? ""); const [focus, setFocus] = useState(profile?.focus ?? ""); const [summary, setSummary] = useState(profile?.summary ?? ""); const [template, setTemplate] = useState(profile?.cv_template ?? "");
  const templates = useQuery({ queryKey: ["templates"], queryFn: api.listTemplates });
  const save = useMutation({ mutationFn: () => { const body: CvProfileInput = { name, focus: focus.split(",").map((v) => v.trim()).filter(Boolean).join(", "), summary: summary || null, cv_template: template || null }; return profile ? api.updateCvProfile(profile.id, body) : api.createCvProfile(body); }, onSuccess: () => { toast.success("CV profile saved"); onSaved(); }, onError: (e) => toast.error(errorMessage(e)) });
  return <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
    <Field id="cvp-name" label="Name"><Input id="cvp-name" value={name} onChange={(e) => setName(e.target.value)} required /></Field>
    <Field id="cvp-focus" label="Focus (comma-separated words)"><Input id="cvp-focus" value={focus} onChange={(e) => setFocus(e.target.value)} /><p className="mt-1 text-xs text-muted-foreground">Facts mentioning these come first</p></Field>
    <div className="sm:col-span-2"><Field id="cvp-summary" label="Summary (optional)"><Textarea id="cvp-summary" value={summary} onChange={(e) => setSummary(e.target.value)} /></Field></div>
    <Field id="cvp-template" label="CV template (optional)"><select id="cvp-template" className={selectClass} value={template} onChange={(e) => setTemplate(e.target.value)}><option value="">Pick automatically</option>{templates.data?.filter((t) => t.kind === "cv").map((t) => <option key={t.key} value={t.key}>{t.name}</option>)}</select></Field>
    {templates.isError && <ErrorState error={templates.error} onRetry={() => templates.refetch()} />}
    <div className="flex items-end justify-end gap-2"><Button type="button" variant="outline" onClick={onCancel}>Cancel</Button><Button disabled={!name.trim() || save.isPending}>Save profile</Button></div>
  </form>;
}
