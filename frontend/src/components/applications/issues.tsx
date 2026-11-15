import { groupIssues } from "@/lib/applications";
import type { DraftIssue } from "@/api/types";
import { cn } from "@/lib/utils";

const GROUPS = [
  { key: "error", title: "Must fix before approving", cls: "border-destructive/40 bg-danger-soft", dot: "bg-destructive", tag: "Error" },
  { key: "warning", title: "Not backed by a verified fact — check these", cls: "border-warning/40 bg-warning-soft", dot: "bg-warning", tag: "Warning" },
  { key: "info", title: "From the job posting", cls: "border-border bg-secondary", dot: "bg-muted-foreground", tag: "Note" },
] as const;

export function IssueList({ issues }: { issues: DraftIssue[] }) {
  return (
    <ul className="space-y-2">
      {issues.map((i, n) => (
        <li key={n} className="text-sm">
          <span className="plain-text">{i.message}</span>
          {i.excerpt && <code className="plain-text ml-1 inline-block rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{i.excerpt}</code>}
        </li>
      ))}
    </ul>
  );
}

export function ChecksPanel({ issues, title = "Checks", id = "checks-h" }: { issues: DraftIssue[] | undefined; title?: string; id?: string }) {
  const g = groupIssues(issues);
  const any = g.error.length + g.warning.length + g.info.length > 0;
  return (
    <section aria-labelledby={id} aria-live="polite" className="space-y-3 rounded-lg border bg-card p-4">
      <h3 id={id} className="font-medium">{title}</h3>
      {!any && <p className="text-sm text-muted-foreground">No problems found.</p>}
      {GROUPS.map((grp) => g[grp.key].length > 0 && (
        <div key={grp.key} className={cn("rounded-md border p-3", grp.cls)}>
          <p className="mb-2 flex items-center gap-2 text-sm font-medium">
            <span aria-hidden className={cn("size-2 rounded-full", grp.dot)} />{grp.title}
            <span className="sr-only">({grp.tag})</span>
          </p>
          <IssueList issues={g[grp.key]} />
        </div>
      ))}
    </section>
  );
}
