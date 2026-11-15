import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api";
import type { OutcomeGroup } from "@/api/job-additions";
import { PageHeader } from "@/components/app-shell";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { formatDateOnly } from "@/lib/format";
export const Route = createFileRoute("/stats")({
  head: () => ({ meta: [{ title: "Statistics — DuuniScript" }, { name: "description", content: "Your recorded application outcomes, response rates and weekly activity." }, { property: "og:title", content: "Statistics — DuuniScript" }, { property: "og:description", content: "Your recorded application outcomes, response rates and weekly activity." }, { property: "og:type", content: "website" }, { name: "twitter:card", content: "summary" }] }),
  component: Statistics,
});
const rate = (n: number | null) => (n == null ? "—" : `${(n * 100).toFixed(1)}%`);
function Statistics() {
  const q = useQuery({ queryKey: ["stats"], queryFn: api.getOutcomeStats });
  const sources = useQuery({ queryKey: ["sources"], queryFn: api.listSources });
  const s = q.data;
  return <><PageHeader title="Statistics" />{q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : !s ? <LoadingState /> : !s.sent ? <EmptyState title="No recorded outcomes yet">Statistics appear after you record sent applications and their outcomes.</EmptyState> : <div className="space-y-8">
    <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[["Sent", s.sent], ["Responses", s.responses], ["Interviews", s.interviews], ["Offers", s.offers], ["Response rate", rate(s.response_rate)], ["Interview rate", rate(s.interview_rate)], ["Median days to reply", s.median_days_to_reply ?? "Not stated"]].map(([label, value]) => <div key={label} className="rounded-md border bg-card p-4"><dt className="text-sm text-muted-foreground">{label}</dt><dd className="mt-2 text-2xl font-medium">{value}</dd></div>)}</dl>
    <section className="space-y-4"><h2 className="text-xl font-medium">Sent per week</h2><div role="img" aria-label="Sent applications per week" className="space-y-3">{s.sent_per_week.map((w) => <div key={w.week} className="grid grid-cols-[110px_1fr_40px] items-center gap-3 text-sm"><span>{formatDateOnly(w.week)}</span><meter className="stats-bar h-6 w-full" min={0} max={Math.max(1, ...s.sent_per_week.map((v) => v.sent))} value={w.sent} aria-label={`Week ${formatDateOnly(w.week)}: ${w.sent} sent`} /><span>{w.sent}</span></div>)}</div></section>
    {sources.isError && <ErrorState error={sources.error} onRetry={() => sources.refetch()} />}
    <StatsTable title="By source" rows={s.by_source} name={(key) => sources.data?.find((v) => v.key === key)?.name ?? key} />
    <StatsTable title="By role word" rows={s.by_role} name={(key) => key} />
  </div>}</>;
}
function StatsTable({ title, rows, name }: { title: string; rows: OutcomeGroup[]; name: (key: string) => string }) {
  return <section className="space-y-3"><h2 className="text-xl font-medium">{title}</h2><div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="sr-only">{title}</caption><thead className="border-b text-muted-foreground"><tr>{[title === "By source" ? "Source" : "Role word", "Sent", "Responses", "Interviews", "Offers", "Response rate"].map((v) => <th key={v} className="whitespace-nowrap px-3 py-2 font-medium">{v}</th>)}</tr></thead><tbody className="divide-y">{rows.map((row) => <tr key={row.key}><td className="plain-text px-3 py-3">{name(row.key)}</td>{[row.sent, row.responses, row.interviews, row.offers, rate(row.response_rate)].map((v, i) => <td key={i} className="px-3 py-3">{v}</td>)}</tr>)}</tbody></table></div></section>;
}
