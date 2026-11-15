import { Link } from "@tanstack/react-router";
import { MatchBadge } from "@/components/jobs/match";
import { ApplyYourselfTag } from "@/components/jobs/job-bits";
import { EmptyState } from "@/components/states";
import { formatDayRelative, formatRelative } from "@/lib/format";
import type { DashboardJob, DashboardSummary } from "@/api/types";

export function DashboardJobSection({ title, jobs, empty, deadlines = false }: { title: string; jobs: DashboardJob[]; empty: string; deadlines?: boolean }) {
  const id = deadlines ? "deadlines-h" : "best-matches-h";
  return (
    <section aria-labelledby={id}>
      <h2 id={id} className="mb-3 text-xl font-medium">{title}</h2>
      {jobs.length === 0 ? <EmptyState title={empty} /> : (
        <ul className="divide-y rounded-lg border bg-card">
          {jobs.map((j) => (
            <li key={j.id} className="flex items-start justify-between gap-3 p-4">
              <div className="min-w-0">
                <Link to="/jobs/$id" params={{ id: j.id }} className="font-medium hover:underline">{j.title}</Link>
                <p className="text-sm text-muted-foreground">{j.company}{j.location ? ` · ${j.location}` : ""}</p>
                <ApplyYourselfTag value={j.apply_manually} />
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1 text-sm">
                <MatchBadge score={j.match_score} />
                {deadlines && <span className="whitespace-nowrap text-muted-foreground">{formatDayRelative(j.deadline_on) ?? "Not stated"}</span>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function DashboardStatusStrip({ status, now = new Date() }: { status: DashboardSummary["status"]; now?: Date }) {
  const backupAge = status.last_backup_at ? now.getTime() - new Date(status.last_backup_at).getTime() : null;
  const backupWarning = !status.automatic_backups || (backupAge !== null && backupAge > 3 * 86400000);
  return (
    <section aria-label="Source and backup status" className="flex flex-wrap gap-x-6 gap-y-2 rounded-lg border bg-card px-4 py-3 text-sm">
      <span className="text-muted-foreground">Last checked {formatRelative(status.last_source_check_at, now) ?? "Not checked yet"}</span>
      {status.sources_failing.length > 0 && (
        <p className="border-l-2 border-warning bg-warning-soft px-2 py-1">
          Could not check: {status.sources_failing.join(", ")}. <Link to="/settings" className="underline">Open Settings</Link>
        </p>
      )}
      {status.sources_turned_off.length > 0 && <span className="text-muted-foreground">Turned off: {status.sources_turned_off.join(", ")}</span>}
      <p className={backupWarning ? "border-l-2 border-warning bg-warning-soft px-2 py-1" : "text-muted-foreground"}>
        {status.last_backup_at ? `Last backup ${formatRelative(status.last_backup_at, now)}` : "No backup made yet"}. <Link to="/settings" hash="s-backups" className="underline">Backups</Link>
      </p>
    </section>
  );
}
