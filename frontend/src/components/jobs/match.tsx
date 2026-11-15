import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { TriangleAlert } from "lucide-react";
import { api } from "@/api";
import { ErrorState, LoadingState } from "@/components/states";
import { Progress } from "@/components/ui/progress";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { JobMatchRead } from "@/api/job-additions";

export function MatchBadge({ score, hasBlockers = false, className }: { score: number | null; hasBlockers?: boolean; className?: string }) {
  if (score === null) return null;
  const tone = score >= 70 ? "border-success/30 bg-success-soft text-success" : score >= 40 ? "border-warning/30 bg-warning-soft text-warning" : "bg-muted text-muted-foreground";
  return (
    <span className={cn("inline-flex items-center gap-1", className)}>
      <span className={cn("inline-flex rounded-full border px-2 py-0.5 text-xs font-medium tabular-nums", tone)} aria-label={`Match ${score} out of 100`}>
        <span aria-hidden>{score}</span>
      </span>
      {hasBlockers && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span tabIndex={0} className="inline-flex text-warning" aria-label="Something may rule this job out — open it to see why">
                <TriangleAlert aria-hidden className="size-3.5" />
              </span>
            </TooltipTrigger>
            <TooltipContent>Something may rule this job out — open it to see why</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </span>
  );
}

export function JobMatchCard({ jobId }: { jobId: string }) {
  const q = useQuery({ queryKey: ["jobMatch", jobId], queryFn: () => api.getJobMatch(jobId) });
  if (q.isLoading) return <LoadingState label="Loading match…" className="py-4" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  return q.data ? <MatchDetails match={q.data} /> : null;
}

export function MatchDetails({ match }: { match: JobMatchRead }) {
  return (
    <section aria-labelledby="match-h" className="rounded-lg border bg-card p-5">
      <h2 id="match-h" className="text-xl font-medium">How well this matches</h2>
      {match.score === null ? (
        <p className="mt-3 text-sm text-muted-foreground">
          Verify some profile facts to see how well this job matches. <Link to="/profile" className="text-primary underline">Open your profile</Link>
        </p>
      ) : (
        <>
          {match.blockers.length > 0 && (
            <ul className="mt-3 space-y-2" aria-label="Possible blockers">
              {match.blockers.map((b) => <li key={b.code} className="plain-text border-l-2 border-warning bg-warning-soft p-3 text-sm">{b.message}</li>)}
            </ul>
          )}
          <p className="mt-3 font-display text-4xl font-medium tabular-nums">{match.score} <span className="text-xl text-muted-foreground">/ 100</span></p>
          <div className="mt-4 space-y-3">
            <MatchPart label="Skills" value={match.parts.skills} max={60} />
            <MatchPart label="Role" value={match.parts.role} max={25} />
            <MatchPart label="Wording" value={match.parts.wording} max={15} />
            {match.parts.semantic != null && <MatchPart label="Meaning (closeness to your facts)" value={match.parts.semantic} max={20} />}
            {match.parts.learned !== 0 && match.parts.learned != null && <div className="flex items-center justify-between gap-3 text-xs"><span>Learned from your decisions</span><span className="tabular-nums text-muted-foreground">{match.parts.learned > 0 ? `+${match.parts.learned}` : `−${Math.abs(match.parts.learned)}`}</span></div>}
          </div>
          {match.reasons.length > 0 && <ul className="mt-4 list-disc space-y-1 pl-5 text-sm">{match.reasons.map((r) => <li key={r} className="plain-text">{r}</li>)}</ul>}
          {match.matched_skills.length > 0 && <ChipList values={match.matched_skills} />}
          {match.missing_terms.length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-medium">In the posting, not in your verified facts</h3>
              <ChipList values={match.missing_terms} outlined />
            </div>
          )}
          <p className="mt-4 text-xs text-muted-foreground">Computed from your verified facts only. A ranking aid, not a judgement — you decide.</p>
        </>
      )}
    </section>
  );
}

function MatchPart({ label, value, max }: { label: string; value: number; max: number }) {
  const percentage = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_minmax(40px,1fr)_auto] items-center gap-3 text-xs">
      <span>{label}</span>
      <Progress value={percentage} className="h-1.5 bg-muted" aria-label={`${label}: ${value} out of ${max}`} />
      <span className="tabular-nums text-muted-foreground">{value}/{max}</span>
    </div>
  );
}

function ChipList({ values, outlined = false }: { values: string[]; outlined?: boolean }) {
  return <ul className="mt-3 flex flex-wrap gap-2">{values.map((v) => <li key={v} className={cn("plain-text rounded-full px-2.5 py-1 text-xs", outlined ? "border bg-background" : "bg-secondary text-secondary-foreground")}>{v}</li>)}</ul>;
}
