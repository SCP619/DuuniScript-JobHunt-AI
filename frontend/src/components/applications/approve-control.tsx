import { useState } from "react";
import { Check, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { IssueList } from "./issues";
import { errorMessage, isApiError } from "@/api";
import { groupIssues } from "@/lib/applications";
import type { DraftIssue } from "@/api/types";

/** Approve button. Disabled while the API reports errors; warnings need an explicit checkbox. */
export function ApproveControl({ issues, onApprove, label }: { issues: DraftIssue[] | undefined; onApprove: (acknowledgeWarnings: boolean) => Promise<unknown>; label: string }) {
  const g = groupIssues(issues);
  const [open, setOpen] = useState(false);
  const [ack, setAck] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<{ message: string; issues: DraftIssue[] } | null>(null);

  const run = async (acknowledge: boolean) => {
    setPending(true); setError(null);
    try { await onApprove(acknowledge); setOpen(false); }
    catch (e) {
      const list = isApiError(e) && (e.code === "draft_has_errors" || e.code === "warnings_not_acknowledged")
        ? ((e.details["issues"] as DraftIssue[] | undefined) ?? []) : [];
      setError({ message: errorMessage(e), issues: list }); setOpen(false);
    } finally { setPending(false); }
  };

  const blocked = g.error.length > 0;
  const button = (
    <Button size="sm" disabled={blocked || pending} aria-describedby={blocked ? "approve-blocked" : undefined}
      onClick={() => (g.warning.length ? (setAck(false), setOpen(true)) : run(false))}>
      {pending ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <Check aria-hidden className="size-4" />}{label}
    </Button>
  );
  return (
    <div className="space-y-2">
      {blocked ? (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild><span tabIndex={0} className="inline-flex">{button}</span></TooltipTrigger>
            <TooltipContent>Fix the problems marked in red first</TooltipContent>
          </Tooltip>
          <span id="approve-blocked" className="sr-only">Fix the problems marked in red first</span>
        </TooltipProvider>
      ) : button}
      <div aria-live="polite">
        {error && (
          <div role="alert" className="rounded-md border border-destructive/40 p-3 text-sm">
            <p className="mb-1 text-destructive">{error.message}</p>
            {error.issues.length > 0 && <IssueList issues={error.issues} />}
          </div>
        )}
      </div>
      <ConfirmDialog open={open} onOpenChange={setOpen} title="Check these statements" destructive={false}
        description="These statements are not backed by a verified fact."
        confirmLabel={label} confirmDisabled={!ack} pending={pending} onConfirm={() => run(true)}>
        <IssueList issues={g.warning} />
        <div className="flex items-center gap-2">
          <Checkbox id="ack-warnings" checked={ack} onCheckedChange={(v) => setAck(v === true)} />
          <Label htmlFor="ack-warnings" className="font-normal">I checked these statements and they are true</Label>
        </div>
      </ConfirmDialog>
    </div>
  );
}
