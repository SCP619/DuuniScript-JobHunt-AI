import { NotStated } from "@/components/states";
import { StatusBadge } from "@/components/status-badge";
import { formatDateOnly, formatDateTime, isPastDate } from "@/lib/format";
import { JOB_STATUS } from "@/lib/labels";
import type { JobStatus } from "@/api/types";
import { Hand } from "lucide-react";

export function ApplyYourselfTag({ value }: { value: boolean }) {
  return value ? <span className="inline-flex items-center gap-1 rounded-full border bg-secondary px-2 py-0.5 text-xs text-secondary-foreground"><Hand aria-hidden className="size-3" />Apply yourself</span> : null;
}

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const s = JOB_STATUS[status];
  return <StatusBadge tone={s.tone} label={s.label} />;
}

export function PublishedDate({ value }: { value: string | null }) {
  const f = formatDateOnly(value);
  return f ? <span>{f}</span> : <NotStated />;
}

/** Deadline: exact time only when the source stated one; past deadlines are muted. Never guessed. */
export function Deadline({ on, at, long = false }: { on: string | null; at?: string | null; long?: boolean }) {
  if (!on && !at) return <NotStated />;
  const dateOn = on ?? (at ? at.slice(0, 10) : null);
  const passed = isPastDate(dateOn);
  const text = at ? formatDateTime(at) : formatDateOnly(on);
  if (passed) {
    return (
      <span className="text-muted-foreground">
        Deadline passed{long && text ? ` (${text})` : ""}
      </span>
    );
  }
  return <span>{long ? `Deadline ${text}` : text}</span>;
}
