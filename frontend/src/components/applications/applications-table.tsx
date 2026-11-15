import { outcomeInfo } from "@/lib/account";
import { Link } from "@tanstack/react-router";
import { StatusBadge } from "@/components/status-badge";
import { APPLICATION_STATUS } from "@/lib/applications";
import { formatDate, formatRelative } from "@/lib/format";
import type { ApplicationSummary } from "@/api/types";

export function ApplicationsTable({ items, caption }: { items: ApplicationSummary[]; caption: string }) {
  return (
    <div className="overflow-x-auto rounded-lg border bg-card">
      <table className="w-full text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="border-b bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-2.5 font-medium">Role</th>
            <th scope="col" className="hidden px-4 py-2.5 font-medium sm:table-cell">Company</th>
            <th scope="col" className="px-4 py-2.5 font-medium">Status</th>
            <th scope="col" className="hidden px-4 py-2.5 font-medium md:table-cell">Updated</th>
            <th scope="col" className="hidden px-4 py-2.5 font-medium md:table-cell">Sent</th>
            <th scope="col" className="px-4 py-2.5 font-medium">Outcome</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {items.map((a) => {
            const s = APPLICATION_STATUS[a.status];
            return (
              <tr key={a.id} className="hover:bg-muted/30">
                <td className="px-4 py-3">
                  <Link to="/applications/$id" params={{ id: a.id }} className="font-medium hover:underline">{a.job.title}</Link>
                  <div className="text-xs text-muted-foreground sm:hidden">{a.job.company}</div>
                </td>
                <td className="hidden px-4 py-3 sm:table-cell">{a.job.company}</td>
                <td className="px-4 py-3"><StatusBadge tone={s.tone} label={s.label} /></td>
                <td className="hidden whitespace-nowrap px-4 py-3 md:table-cell">{formatRelative(a.updated_at)}</td>
                <td className="hidden whitespace-nowrap px-4 py-3 md:table-cell">{formatDate(a.submitted_at) ?? <span className="text-muted-foreground">—</span>}</td>
                <td className="px-4 py-3">{(() => { const o = outcomeInfo(a.outcome); return o ? <StatusBadge tone={o.tone} label={o.label} /> : <span className="text-muted-foreground"><span aria-hidden>—</span><span className="sr-only">None recorded</span></span>; })()}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
