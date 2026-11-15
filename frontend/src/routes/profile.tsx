import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { cn } from "@/lib/utils";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Loader2, Plus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { PageHeader } from "@/components/app-shell";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Field, describedBy, selectClass, selectInline } from "@/components/field";
import { StatusBadge } from "@/components/status-badge";
import { FactForm, factToForm } from "@/components/profile/fact-form";
import { FactPanel, dateRange } from "@/components/profile/fact-panel";
import { api, errorMessage, fieldErrors, isApiError } from "@/api";
import { FACT_CATEGORIES, FACT_CATEGORY, VERIFICATION } from "@/lib/labels";
import type { FactCategory, FactRead, ProfileRead, VerificationStatus } from "@/api/types";

export const Route = createFileRoute("/profile")({
  head: () => ({
    meta: [
      { title: "Profile & evidence — DuuniScript" },
      { name: "description", content: "Your profile, the facts you claim, and the evidence behind them." },
      { property: "og:title", content: "Profile & evidence — DuuniScript" },
      { property: "og:description", content: "Your profile, the facts you claim, and the evidence behind them." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  validateSearch: (s: Record<string, unknown>): { status?: "unverified" | "verified" } =>
    s.status === "unverified" || s.status === "verified" ? { status: s.status } : {},
  component: ProfilePage,
});

function ProfilePage() {
  const q = useQuery({ queryKey: ["profile"], queryFn: api.getProfile });
  const missing = isApiError(q.error) && q.error.code === "profile_not_found";

  return (
    <>
      <PageHeader title="Profile & evidence" description="Facts about you that DuuniScript may use later. Only facts you confirm count as confirmed." />
      {q.isLoading ? <LoadingState label="Loading profile…" />
        : missing ? (
          <section className="rounded-lg border bg-card p-6">
            <h2 className="text-xl font-medium">Set up your profile</h2>
            <p className="mb-5 mt-1 text-sm text-muted-foreground">Start with your name. Everything stays on this computer.</p>
            <ProfileForm profile={null} />
          </section>
        )
        : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} />
        : (
          <div className="space-y-8">
            <section className="rounded-lg border bg-card p-6" aria-labelledby="pf-h">
              <h2 id="pf-h" className="mb-5 text-xl font-medium">Your details</h2>
              <ProfileForm profile={q.data!} />
            </section>
            <FactsSection />
          </div>
        )}
    </>
  );
}

function ProfileForm({ profile }: { profile: ProfileRead | null }) {
  const qc = useQueryClient();
  const [v, setV] = useState({
    display_name: profile?.display_name ?? "", email: profile?.email ?? "", phone: profile?.phone ?? "",
    location: profile?.location ?? "", professional_summary: profile?.professional_summary ?? "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const n = (s: string) => (s.trim() === "" ? null : s);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPending(true); setErrors({}); setFormError(null);
    try {
      // Always send every field; null clears.
      const saved = await api.putProfile({
        display_name: v.display_name, email: n(v.email), phone: n(v.phone), location: n(v.location), professional_summary: n(v.professional_summary),
      });
      qc.setQueryData(["profile"], saved);
      qc.invalidateQueries({ queryKey: ["facts"] });
      toast.success(profile ? "Saved" : "Profile created");
    } catch (err) {
      const fe = fieldErrors(err);
      setErrors(fe);
      if (!Object.keys(fe).length) setFormError(errorMessage(err));
    } finally {
      setPending(false);
    }
  };
  const input = (k: keyof typeof v, label: string, type = "text", required = false) => (
    <Field id={`p-${k}`} label={label} required={required} error={errors[k]}>
      <Input id={`p-${k}`} type={type} value={v[k]} maxLength={k === "display_name" ? 200 : undefined}
        onChange={(e) => setV((s) => ({ ...s, [k]: e.target.value }))} {...describedBy(`p-${k}`, errors[k])} />
    </Field>
  );
  return (
    <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2" noValidate>
      {input("display_name", "Name", "text", true)}
      {input("email", "Email", "email")}
      {input("phone", "Phone", "tel")}
      {input("location", "Location")}
      <Field id="p-summary" label="Professional summary" error={errors.professional_summary} className="sm:col-span-2">
        <Textarea id="p-summary" rows={4} value={v.professional_summary} onChange={(e) => setV((s) => ({ ...s, professional_summary: e.target.value }))} />
      </Field>
      {formError && <p role="alert" className="text-sm text-destructive sm:col-span-2">{formError}</p>}
      <div className="sm:col-span-2">
        <Button type="submit" disabled={pending}>{pending && <Loader2 aria-hidden className="size-4 animate-spin" />}{profile ? "Save details" : "Create profile"}</Button>
      </div>
    </form>
  );
}

function FactsSection() {
  const qc = useQueryClient();
  const [category, setCategory] = useState<FactCategory | "">("");
  const { status: urlStatus } = Route.useSearch();
  const navigate = useNavigate({ from: "/profile" });
  const status: VerificationStatus | "" = urlStatus ?? "";
  const setStatus = (v: "unverified" | "verified" | "") => navigate({ search: v ? { status: v } : {}, replace: true });
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [verifyOpen, setVerifyOpen] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const toggle = (id: string, on: boolean) => setPicked((p) => { const n = new Set(p); if (on) n.add(id); else n.delete(id); return n; });
  const verify = async () => {
    setVerifying(true);
    try {
      const r = await api.verifyFacts([...picked]);
      toast.success(`${r.verified} fact${r.verified === 1 ? "" : "s"} verified`);
      setPicked(new Set()); setVerifyOpen(false);
      qc.invalidateQueries({ queryKey: ["facts"] });
    } catch (e) { toast.error(errorMessage(e)); } finally { setVerifying(false); }
  };
  const [adding, setAdding] = useState(false);
  const [selected, setSelected] = useState<FactRead | null>(null);
  const params = { category: category || undefined, verification_status: status || undefined, limit: 200 };
  const q = useQuery({ queryKey: ["facts", params], queryFn: () => api.listFacts(params) });
  const noProfile = isApiError(q.error) && q.error.code === "profile_not_found";

  const grouped = FACT_CATEGORIES.map((c) => ({ c, items: q.data?.items.filter((f) => f.category === c) ?? [] })).filter((g) => g.items.length);

  return (
    <section aria-labelledby="facts-h">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 id="facts-h" className="text-xl font-medium">Facts</h2>
          <p className="text-sm text-muted-foreground">Claims about your education, work and skills. New facts start as not yet confirmed.</p>
        </div>
        <Button onClick={() => setAdding(true)} disabled={noProfile}><Plus aria-hidden className="size-4" />Add fact</Button>
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        <label className="sr-only" htmlFor="fact-cat">Category</label>
        <select id="fact-cat" className={selectInline} value={category} onChange={(e) => setCategory(e.target.value as FactCategory | "")}>
          <option value="">All categories</option>
          {FACT_CATEGORIES.map((c) => <option key={c} value={c}>{FACT_CATEGORY[c]}</option>)}
        </select>
        <div role="group" aria-label="Verification" className="flex gap-1">
          {([["", "All"], ["unverified", "Unverified"], ["verified", "Verified"]] as const).map(([k, l]) => (
            <Button key={l} size="sm" variant={status === k ? "default" : "outline"} aria-pressed={status === k} onClick={() => setStatus(k)}>{l}</Button>
          ))}
        </div>
        {picked.size > 0 && (
          <Button size="sm" className="ml-auto" onClick={() => setVerifyOpen(true)}>Verify selected ({picked.size})</Button>
        )}
      </div>

      {q.isLoading ? <LoadingState label="Loading facts…" />
        : noProfile ? <EmptyState title="Create your profile first">Facts belong to your profile.</EmptyState>
        : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} />
        : grouped.length === 0 ? (
          <EmptyState title={category || status ? "No facts match these filters" : "No facts yet"}>
            {category || status ? "Try another filter." : "Add facts yourself, or use Suggest profile facts on a CV in Documents."}
          </EmptyState>
        ) : (
          <div className="space-y-6">
            {grouped.map(({ c, items }) => (
              <div key={c}>
                <h3 className="mb-2 font-sans text-xs font-semibold uppercase tracking-wide text-muted-foreground">{FACT_CATEGORY[c]}</h3>
                <ul className="divide-y rounded-lg border bg-card">
                  {items.map((f) => {
                    const v = VERIFICATION[f.verification_status];
                    return (
                      <li key={f.id} className="flex items-start">
                        <div className={cn("pl-4 pt-4", f.verification_status !== "unverified" && "invisible")}>
                          <Checkbox checked={picked.has(f.id)} disabled={f.verification_status !== "unverified"} onCheckedChange={(v) => toggle(f.id, v === true)} aria-label={`Select “${f.subject}” to verify`} />
                        </div>
                        <button type="button" onClick={() => setSelected(f)} className="flex min-w-0 flex-1 items-start gap-4 px-4 py-3 text-left hover:bg-muted/30 focus-visible:bg-muted/30">
                          <div className="min-w-0 flex-1">
                            <p className="font-medium">{f.subject}</p>
                            <p className="truncate text-sm text-muted-foreground">{f.value_text}</p>
                            <p className="mt-1 flex flex-wrap gap-x-3 text-xs text-muted-foreground">
                              {dateRange(f) && <span>{dateRange(f)}</span>}
                              <span>{f.evidence_count === 0 ? "Evidence needed" : `${f.evidence_count} evidence item${f.evidence_count === 1 ? "" : "s"}`}</span>
                            </p>
                          </div>
                          <StatusBadge tone={v.tone} label={v.label} />
                          <ChevronRight aria-hidden className="mt-1 size-4 shrink-0 text-muted-foreground" />
                          <span className="sr-only">Open details</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>
        )}

      <Dialog open={adding} onOpenChange={setAdding}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Add a fact</DialogTitle>
            <DialogDescription>New facts start as not yet confirmed. You can add evidence and confirm it afterwards.</DialogDescription>
          </DialogHeader>
          {adding && (
            <FactForm idPrefix="new-fact" initial={factToForm(undefined, category || "skill")} submitLabel="Add fact" onCancel={() => setAdding(false)}
              onSubmit={async (v) => {
                const f = await api.createFact({ category: v.category, subject: v.subject, value_text: v.value_text, valid_from: v.valid_from || null, valid_until: v.valid_until || null });
                qc.invalidateQueries({ queryKey: ["facts"] });
                toast.success("Fact added");
                setAdding(false);
                setSelected(f);
              }} />
          )}
        </DialogContent>
      </Dialog>

      <ConfirmDialog open={verifyOpen} onOpenChange={setVerifyOpen} title={`Verify ${picked.size} fact${picked.size === 1 ? "" : "s"}?`}
        description="Only verify facts you have checked are true. Verified facts are used in your CVs and cover letters."
        confirmLabel="Verify" destructive={false} pending={verifying} onConfirm={verify} />
      <FactPanel fact={selected} onClose={() => setSelected(null)} />
    </section>
  );
}
