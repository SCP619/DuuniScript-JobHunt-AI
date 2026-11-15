import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { api, errorMessage } from "@/api";
import type { FeedRead, FeedSyncResult } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { ErrorState, LoadingState } from "@/components/states";
import { FeedSourceSwitch } from "./feed-source-switch";
import { formatDateTime, formatRelative } from "@/lib/format";
import { feedSyncSummary, nextCheckRelative } from "@/lib/job-feeds";

export function JobFeedsCard() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["feeds"], queryFn: api.getFeeds });
  const [outcome, setOutcome] = useState<{ text: string; error: boolean } | null>(null);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["feeds"] });
    qc.invalidateQueries({ queryKey: ["sources"] });
    qc.invalidateQueries({ queryKey: ["jobs"] });
    qc.invalidateQueries({ queryKey: ["job"] });
  };
  const done = (results: FeedSyncResult[]) => {
    const text = feedSyncSummary(results);
    const error = results.some((r) => r.error !== null);
    setOutcome({ text, error });
    if (error) toast.warning(text); else toast.success(text);
    refresh();
  };
  const fail = (e: unknown) => {
    const text = errorMessage(e);
    setOutcome({ text, error: true }); toast.error(text); refresh();
  };
  const sync = useMutation({ mutationFn: api.syncFeeds, onSuccess: done, onError: fail });
  const rowSync = useMutation({ mutationFn: api.syncFeed, onSuccess: (r) => done([r]), onError: fail });
  const busy = sync.isPending || rowSync.isPending;
  const s = status.data;
  return (
    <section aria-labelledby="s-feeds" className="space-y-4 border-y py-5">
      <h2 id="s-feeds" className="text-xl font-medium">Job feeds</h2>
      {status.isLoading ? <LoadingState className="py-2" /> : status.isError ? <ErrorState error={status.error} onRetry={() => status.refetch()} /> : s && <>
        <div className="space-y-1 text-sm">
          <p>DuuniScript reads these sites' own job feeds while it is running. Each site is read no more often than it asks.</p>
          <p className="text-muted-foreground">{s.check_interval_minutes === 0 ? "Automatic checks are off" : `Checks for new jobs every ${s.check_interval_minutes} minutes`}</p>
          {s.skip_unavailable && <p className="text-muted-foreground">Remote jobs limited to other countries are not added.</p>}
          {s.keywords.length > 0 && <p className="plain-text text-muted-foreground">Only jobs mentioning: {s.keywords.join(", ")}.</p>}
        </div>
        <Button disabled={busy} onClick={() => { setOutcome(null); sync.mutate(); }}>
          {sync.isPending ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <RefreshCw aria-hidden className="size-4" />}Check now
        </Button>
        {outcome && <p role={outcome.error ? "alert" : "status"} className={`plain-text text-sm ${outcome.error ? "border-l-2 border-warning bg-warning-soft p-3" : "text-muted-foreground"}`}>{outcome.text}</p>}
        <TooltipProvider>
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-sm">
              <caption className="sr-only">Job feeds</caption>
              <thead className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>{["Name", "Jobs", "Last checked", "Next check", "Enabled", ""].map((h) => <th key={h} scope="col" className="px-3 py-2 font-medium">{h || <span className="sr-only">Check feed</span>}</th>)}</tr>
              </thead>
              <tbody className="divide-y">
                {s.feeds.map((f) => <tr key={f.key} className="align-top">
                  <td className="px-3 py-3"><FeedName feed={f} />{f.last_error && <p role="alert" className="plain-text mt-2 border-l-2 border-warning bg-warning-soft p-2 text-xs">{f.last_error}</p>}</td>
                  <td className="px-3 py-3">{f.jobs}</td>
                  <td className="whitespace-nowrap px-3 py-3" title={formatDateTime(f.last_success_at) ?? undefined}>{formatRelative(f.last_success_at, new Date(now)) ?? "Never"}</td>
                  <td className="whitespace-nowrap px-3 py-3">{nextCheckRelative(f.next_allowed_at, now)}</td>
                  <td className="px-3 py-3"><FeedSourceSwitch sourceKey={f.key} name={f.name} enabled={f.enabled} /></td>
                  <td className="px-3 py-3"><FeedCheck feed={f} now={now} busy={busy} pending={rowSync.isPending && rowSync.variables === f.key} onCheck={() => rowSync.mutate(f.key)} /></td>
                </tr>)}
              </tbody>
            </table>
          </div>
          <ul className="divide-y md:hidden">
            {s.feeds.map((f) => <li key={f.key} className="space-y-3 py-4">
              <div className="flex items-start justify-between gap-3"><FeedName feed={f} /><FeedSourceSwitch sourceKey={f.key} name={f.name} enabled={f.enabled} /></div>
              <dl className="grid grid-cols-2 gap-1 text-sm"><dt className="text-muted-foreground">Jobs</dt><dd>{f.jobs}</dd><dt className="text-muted-foreground">Last checked</dt><dd>{formatRelative(f.last_success_at, new Date(now)) ?? "Never"}</dd><dt className="text-muted-foreground">Next check</dt><dd>{nextCheckRelative(f.next_allowed_at, now)}</dd></dl>
              {f.last_error && <p role="alert" className="plain-text border-l-2 border-warning bg-warning-soft p-2 text-sm">{f.last_error}</p>}
              <FeedCheck feed={f} now={now} busy={busy} pending={rowSync.isPending && rowSync.variables === f.key} onCheck={() => rowSync.mutate(f.key)} />
            </li>)}
          </ul>
        </TooltipProvider>
      </>}
    </section>
  );
}

function FeedName({ feed }: { feed: FeedRead }) {
  return <a className="font-medium underline" href={feed.terms_url} target="_blank" rel="noopener noreferrer">{feed.name}<span className="sr-only"> (opens in a new tab)</span></a>;
}

function FeedCheck({ feed, now, busy, pending, onCheck }: { feed: FeedRead; now: number; busy: boolean; pending: boolean; onCheck: () => void }) {
  const future = !!feed.next_allowed_at && new Date(feed.next_allowed_at).getTime() > now;
  const explanation = future ? `Next check allowed ${nextCheckRelative(feed.next_allowed_at, now)}` : !feed.enabled ? "This feed is turned off" : undefined;
  return <Tooltip><TooltipTrigger asChild><span tabIndex={explanation ? 0 : undefined} className="inline-flex" aria-label={explanation}>
    <Button variant="outline" size="sm" aria-label={`Check ${feed.name}`} disabled={busy || future || !feed.enabled} onClick={onCheck}>{pending ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <RefreshCw aria-hidden className="size-4" />}Check</Button>
  </span></TooltipTrigger>{explanation && <TooltipContent>{explanation}</TooltipContent>}</Tooltip>;
}