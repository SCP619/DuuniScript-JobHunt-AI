import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ErrorState, LoadingState } from "@/components/states";
import { api, errorMessage } from "@/api";
import { FACT_CATEGORIES, FACT_CATEGORY } from "@/lib/labels";
import { buildFactImport, toRows, type SuggestionRow } from "@/lib/applications";
import type { DocumentRead, FactCategory } from "@/api/types";

const ORDER: FactCategory[] = ["contact", "summary", "work_experience", "education", "project", "skill", "language", "certification", "publication", "achievement"];
const ordered = [...ORDER, ...FACT_CATEGORIES.filter((c) => !ORDER.includes(c))];

export function FactSuggestionsDialog({ doc, onClose }: { doc: DocumentRead | null; onClose: () => void }) {
  return (
    <Dialog open={!!doc} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Suggested profile facts</DialogTitle>
          <DialogDescription>
            These were read from your CV by simple rules and can be wrong or incomplete. Check each one. Saved facts start as unverified; only verified facts are used in your CVs and cover letters.
          </DialogDescription>
        </DialogHeader>
        {doc && <SuggestionsBody key={doc.id} docId={doc.id} onClose={onClose} />}
      </DialogContent>
    </Dialog>
  );
}

export function SuggestionsBody({ docId, onClose }: { docId: string; onClose: () => void }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["factSuggestions", docId], queryFn: () => api.getFactSuggestions(docId), gcTime: 0 });
  const [rows, setRows] = useState<SuggestionRow[]>([]);
  const [done, setDone] = useState<string | null>(null);
  useEffect(() => { if (q.data) setRows(toRows(q.data.items)); }, [q.data]);
  const set = (key: string, patch: Partial<SuggestionRow>) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const checked = rows.filter((r) => r.checked).length;

  const save = useMutation({
    mutationFn: () => api.importFacts(buildFactImport(docId, rows)),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["facts"] });
      const msg = `${r.created} fact${r.created === 1 ? "" : "s"} added (${r.skipped_existing} were already in your profile)`;
      toast.success(msg); setDone(msg);
    },
  });

  if (q.isLoading) return <LoadingState label="Reading suggestions…" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (done) return (
    <div className="space-y-4" aria-live="polite">
      <p className="text-sm">{done}</p>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>Close</Button>
        <Button asChild><Link to="/profile" search={{ status: "unverified" }} onClick={onClose}>Review and verify them</Link></Button>
      </DialogFooter>
    </div>
  );
  if (rows.length === 0) return <p className="text-sm text-muted-foreground">No facts could be read from this document.</p>;

  return (
    <div className="space-y-6">
      {ordered.map((c) => {
        const group = rows.filter((r) => r.category === c);
        if (!group.length) return null;
        return (
          <section key={c} aria-labelledby={`sg-${c}`} className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <h3 id={`sg-${c}`} className="mr-auto text-xs font-semibold uppercase tracking-wide text-muted-foreground">{FACT_CATEGORY[c]}</h3>
              <Button size="sm" variant="ghost" onClick={() => group.forEach((r) => set(r.key, { checked: true }))}>Select all<span className="sr-only"> in {FACT_CATEGORY[c]}</span></Button>
              <Button size="sm" variant="ghost" onClick={() => group.forEach((r) => set(r.key, { checked: false }))}>Select none<span className="sr-only"> in {FACT_CATEGORY[c]}</span></Button>
            </div>
            <ul className="space-y-3">
              {group.map((r) => (
                <li key={r.key} className="flex gap-3 rounded-md border p-3">
                  <Checkbox id={`sg-cb-${r.key}`} checked={r.checked} onCheckedChange={(v) => set(r.key, { checked: v === true })} aria-label={`Add “${r.subject}”`} className="mt-2" />
                  <div className="min-w-0 flex-1 space-y-2">
                    {r.already_in_profile && <p className="text-xs font-medium text-muted-foreground">Already in your profile</p>}
                    <label className="sr-only" htmlFor={`sg-s-${r.key}`}>Subject</label>
                    <Input id={`sg-s-${r.key}`} value={r.subject} onChange={(e) => set(r.key, { subject: e.target.value })} />
                    <label className="sr-only" htmlFor={`sg-v-${r.key}`}>Details</label>
                    <Textarea id={`sg-v-${r.key}`} rows={2} value={r.value_text} onChange={(e) => set(r.key, { value_text: e.target.value })} />
                    <div className="flex flex-wrap gap-3 text-xs">
                      <label className="flex items-center gap-2">From<Input type="date" className="h-8 w-auto" value={r.valid_from ?? ""} onChange={(e) => set(r.key, { valid_from: e.target.value || null })} /></label>
                      <label className="flex items-center gap-2">Until<Input type="date" className="h-8 w-auto" value={r.valid_until ?? ""} onChange={(e) => set(r.key, { valid_until: e.target.value || null })} /></label>
                    </div>
                    {r.excerpt && (
                      <Collapsible>
                        <CollapsibleTrigger className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:underline"><ChevronDown aria-hidden className="size-3" />From the CV</CollapsibleTrigger>
                        <CollapsibleContent><p className="plain-text mt-1 rounded bg-muted/40 p-2 font-mono text-xs">{r.excerpt}</p></CollapsibleContent>
                      </Collapsible>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
      <div aria-live="polite">{save.isError && <p role="alert" className="text-sm text-destructive">{errorMessage(save.error)}</p>}</div>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button disabled={checked === 0 || save.isPending} onClick={() => save.mutate()}>
          {save.isPending && <Loader2 aria-hidden className="size-4 animate-spin" />}Add {checked} fact{checked === 1 ? "" : "s"}
        </Button>
      </DialogFooter>
    </div>
  );
}
