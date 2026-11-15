import { Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Copy, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/api";
import type { JobRead } from "@/api/types";
import { JOB_STATUS } from "@/lib/labels";
import { cn } from "@/lib/utils";

/** Shown when the backend flagged this job as possibly the same as another one. */
export function DuplicateBanner({ job }: { job: JobRead }) {
  const otherId = job.possible_duplicate_of;
  const qc = useQueryClient();
  const navigate = useNavigate();
  const other = useQuery({ queryKey: ["job", otherId], queryFn: () => api.getJob(otherId!), enabled: !!otherId });

  const merge = useMutation({
    mutationFn: () => api.mergeJob(job.id, otherId!),
    onSuccess: (kept) => {
      qc.removeQueries({ queryKey: ["job", job.id] });
      qc.setQueryData(["job", kept.id], kept);
      qc.invalidateQueries({ queryKey: ["jobs"] });
      toast.success("Merged. Its listings, details and notes are now on this job.");
      navigate({ to: "/jobs/$id", params: { id: kept.id } });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const dismiss = useMutation({
    mutationFn: () => api.updateJob(job.id, { possible_duplicate_of: null }),
    onSuccess: (updated) => {
      qc.setQueryData(["job", job.id], updated);
      qc.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (!otherId) return null;
  const o = other.data;
  const applied = o?.status === "applied";
  const busy = merge.isPending || dismiss.isPending;

  return (
    <section role="region" aria-label="Possible duplicate"
      className={cn("mb-6 space-y-3 rounded-lg border p-4 text-sm", applied ? "border-warning/50 bg-warning-soft" : "bg-muted/40")}>
      <div className="flex gap-3">
        {applied ? <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0 text-warning" /> : <Copy aria-hidden className="mt-0.5 size-4 shrink-0 text-muted-foreground" />}
        <div className="space-y-1">
          {applied && <p className="font-medium">You have already applied to a job that looks like this one.</p>}
          {other.isLoading ? <p className="text-muted-foreground">Looking up the similar job…</p>
            : other.isError ? <p>This looks like another job already in your list. <span className="text-muted-foreground">({errorMessage(other.error)})</span></p>
            : o && (
              <p>
                This looks like a job already in your list:{" "}
                <Link to="/jobs/$id" params={{ id: o.id }} className="font-medium underline">{o.title} — {o.company}</Link>{" "}
                ({JOB_STATUS[o.status].label}).
              </p>
            )}
        </div>
      </div>
      <div className="flex flex-wrap gap-2 pl-7">
        <Button size="sm" disabled={busy} onClick={() => merge.mutate()}>
          {merge.isPending && <Loader2 aria-hidden className="size-4 animate-spin" />}Same job — merge
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => dismiss.mutate()}>
          {dismiss.isPending && <Loader2 aria-hidden className="size-4 animate-spin" />}Not the same
        </Button>
      </div>
    </section>
  );
}
