import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/api";
import { ChecksPanel } from "./issues";
import type { AiWriteResult } from "@/api/job-additions";
import type { DraftKind, PolishResult } from "@/api/types";

/**
 * Local AI wording suggestion. "Use this text" only puts it in the editor;
 * nothing is saved until the user presses Save, and it still needs approval.
 */
export function PolishControl({ appId, kind, current, onUse }: { appId: string; kind: DraftKind; current: string; onUse: (text: string) => void }) {
  const ai = useQuery({ queryKey: ["ai"], queryFn: api.getAi });
  const [result, setResult] = useState<(PolishResult & { fact_ids?: string[] }) | null>(null);
  const polish = useMutation({ mutationFn: () => api.polishDraft(appId, kind), onSuccess: setResult, onError: (e) => toast.error(errorMessage(e)) });
  const write = useMutation({ mutationFn: () => api.aiWriteLetter(appId), retry: false, onSuccess: (r: AiWriteResult) => setResult(r), onError: (e) => toast.error(errorMessage(e)) });
  const facts = useQuery({ queryKey: ["aiWriteFacts", result?.fact_ids], queryFn: () => Promise.all((result?.fact_ids ?? []).map((id) => api.getFact(id))), enabled: !!result?.fact_ids?.length });
  if (!ai.data) return null;
  if (!ai.data.reachable) return <p className="text-xs text-muted-foreground" title={ai.data.message ?? undefined}>Local AI is off{ai.data.message && <span className="sr-only">: {ai.data.message}</span>}</p>;
  return (
    <div className="space-y-3">
      {!result && <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={() => polish.mutate()} disabled={polish.isPending || write.isPending}>
          {polish.isPending ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <Sparkles aria-hidden className="size-4" />}Suggest wording
        </Button>
        {kind === "cover_letter" && <Button size="sm" variant="outline" disabled={write.isPending || polish.isPending} onClick={() => write.mutate()}><Sparkles aria-hidden className="size-4" />{write.isPending ? "Writing fit paragraphs…" : "Write fit paragraphs with AI"}</Button>}
      </div>}
      {kind === "cover_letter" && <p className="text-xs text-muted-foreground">The AI states only what your facts support. Your own motivation sentence stays yours to write.</p>}
      {result && (
        <section aria-labelledby={`pol-${kind}`} className="space-y-3 rounded-lg border bg-card p-4">
          <h3 id={`pol-${kind}`} className="font-medium">Suggested wording{ai.data.model && <span className="ml-2 text-xs font-normal text-muted-foreground">from {ai.data.model} on this computer</span>}</h3>
          <p className="text-sm text-muted-foreground">Compare it with your text. Using it only changes the editor; save and approve as usual.</p>
          <div className="grid gap-4 lg:grid-cols-2">
            <div><p className="mb-1 text-sm font-medium">Current text</p><div className="plain-text max-h-96 overflow-y-auto rounded-md border bg-muted/30 p-3 font-mono text-xs">{current}</div></div>
            <div><p className="mb-1 text-sm font-medium">Suggestion</p><div className="plain-text max-h-96 overflow-y-auto rounded-md border p-3 font-mono text-xs">{result.suggestion}</div></div>
          </div>
          {result.fact_ids && <div className="text-sm"><h4 className="font-medium">Based on these verified facts</h4><ul className="mt-2 list-disc pl-5">{facts.data?.map((f) => <li className="plain-text" key={f.id}>{f.subject} — {f.value_text}</li>)}</ul>{facts.isLoading && <p>Loading facts…</p>}{facts.isError && <p role="alert" className="plain-text text-destructive">{errorMessage(facts.error)}</p>}{!result.fact_ids.length && <p className="text-muted-foreground">No facts listed.</p>}</div>}
          <ChecksPanel issues={result.issues} title="Checks for the suggestion" id={`pol-checks-${kind}`} />
          <div className="flex gap-2">
            <Button size="sm" onClick={() => { onUse(result.suggestion); setResult(null); }}>Use this text</Button>
            <Button size="sm" variant="outline" onClick={() => setResult(null)}>Discard</Button>
          </div>
        </section>
      )}
    </div>
  );
}
