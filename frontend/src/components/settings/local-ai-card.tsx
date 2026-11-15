import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { api, errorMessage } from "@/api";
import type { AiStatus } from "@/api/job-additions";
import { Button } from "@/components/ui/button";
import { ErrorState, LoadingState } from "@/components/states";

export function LocalAiStatus({ status: s }: { status: AiStatus }) {
  const writingReady = s.enabled && s.reachable;
  return <div className="space-y-2 text-sm">
    <p className={writingReady ? "plain-text" : "plain-text text-warning"}>Writing model: {s.model ?? "Not configured"} — {writingReady ? "ready" : s.message ?? (s.enabled ? "unavailable" : "Local AI is off")}</p>
    <p className={s.embeddings_reachable ? "plain-text" : "plain-text text-warning"}>Search model: {s.embedding_model ?? "Not configured"} — {s.embeddings_reachable ? "ready" : "unavailable"}</p>
    <p>Search index: {s.facts_indexed} facts, {s.jobs_indexed} jobs</p>
  </div>;
}

export function LocalAiCard() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["ai"], queryFn: api.getAi });
  const index = useMutation({ mutationFn: api.indexAi, retry: false, onSuccess: (r) => {
    if (r.available) toast.success(`Indexed ${r.facts} facts and ${r.jobs} jobs`);
    else toast.warning("The local search model is unavailable. The search index was not updated.");
    qc.invalidateQueries({ queryKey: ["ai"] });
    qc.invalidateQueries({ queryKey: ["jobMatch"] });
    qc.invalidateQueries({ queryKey: ["jobs"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
  }, onError: (e) => toast.error(errorMessage(e)) });
  return <section aria-labelledby="s-ai" className="space-y-4 border-y py-5">
    <h2 id="s-ai" className="text-xl font-medium">Local AI</h2>
    {q.isLoading ? <LoadingState className="py-2" /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : q.data && <>
      <LocalAiStatus status={q.data} />
      <Button variant="outline" disabled={index.isPending} onClick={() => index.mutate()}>{index.isPending ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <RefreshCw aria-hidden className="size-4" />}Update search index</Button>
    </>}
    {index.isPending && <p role="status" className="text-sm text-muted-foreground">Updating the search index… (the first run can take a minute)</p>}
    {index.isError && <p role="alert" className="plain-text text-sm text-destructive">{errorMessage(index.error)}</p>}
    <p className="text-sm text-muted-foreground">Runs only on this computer with Ollama. Nothing is sent to any online AI service. Only verified facts are searched.</p>
  </section>;
}