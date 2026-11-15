import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Pencil } from "lucide-react";
import { toast } from "sonner";
import { api, errorMessage } from "@/api";
import type { FormAnswerRead } from "@/api/job-additions";
import { formAnswerKey, copyAllAnswers } from "@/lib/applications";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ErrorState, LoadingState } from "@/components/states";
const sources = { facts: "From your verified facts", profile: "From your profile", saved: "Your saved answer", job: "From the job posting", none: "Your answer needed" };
const shared = new Set(["availability", "salary", "notice_period", "references", "relocation"]);
async function copy(text: string) { try { await navigator.clipboard.writeText(text); toast.success("Copied"); } catch { toast.error("Could not copy. Select the text and copy it manually."); } }
export function FormAnswers({ appId }: { appId: string }) {
  const q = useQuery({ queryKey: ["formAnswers", appId], queryFn: () => api.getFormAnswers(appId) });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <LoadingState label="Loading form answers…" />;
  return <div className="space-y-4"><div className="flex justify-end"><Button variant="outline" size="sm" disabled={!q.data.length} onClick={() => copy(copyAllAnswers(q.data ?? []))}><Copy aria-hidden className="size-4" />Copy all</Button></div>
    {!q.data.length && <p className="text-sm text-muted-foreground">No form questions available.</p>}
    {q.data.map((item) => <AnswerCard key={`${item.key}-${item.answer}-${item.needs_input}`} appId={appId} item={item} />)}
  </div>;
}
function AnswerCard({ appId, item }: { appId: string; item: FormAnswerRead }) {
  const qc = useQueryClient();
  const [answer, setAnswer] = useState(item.answer ?? "");
  const [editing, setEditing] = useState(item.needs_input);
  const save = useMutation({ mutationFn: () => api.saveFormAnswer(formAnswerKey(item.key, appId), { answer }), retry: false,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["formAnswers"] }); setEditing(false); toast.success("Answer saved"); }, onError: (e) => toast.error(errorMessage(e)) });
  return <section className="space-y-3 rounded-md border bg-card p-4" aria-labelledby={`answer-${item.key}`}>
    <div className="flex items-start justify-between gap-3"><h3 id={`answer-${item.key}`} className="plain-text font-medium">{item.question}</h3><Button variant="ghost" size="sm" disabled={!item.answer} onClick={() => copy(item.answer)}><Copy aria-hidden className="size-4" />Copy</Button></div>
    <p className="text-xs text-muted-foreground">{sources[item.source]}</p>
    {item.answer && <p className="plain-text text-sm">{item.answer}</p>}
    {shared.has(item.key) && <p className="text-xs text-muted-foreground">This saved answer is reused for all applications.</p>}
    {editing ? <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}><Textarea aria-label={item.question} placeholder={item.hint ?? undefined} value={answer} onChange={(e) => setAnswer(e.target.value)} rows={3} /><Button size="sm" disabled={save.isPending || !answer.trim()}>Save</Button></form>
      : <Button size="sm" variant="ghost" onClick={() => setEditing(true)}><Pencil aria-hidden className="size-4" />Edit answer</Button>}
  </section>;
}
