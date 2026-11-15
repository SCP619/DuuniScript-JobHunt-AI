import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClass } from "@/components/field";
import { api, errorMessage } from "@/api";
import { OUTCOMES, buildOutcome } from "@/lib/account";
import { todayHelsinki } from "@/lib/format";
import type { ApplicationOutcome, ApplicationRead } from "@/api/types";

export function OutcomeControl({ app, onChanged }: { app: ApplicationRead; onChanged: () => void }) {
  const [outcome, setOutcome] = useState<ApplicationOutcome | "">(app.outcome ?? "");
  const [on, setOn] = useState(app.outcome_on ?? todayHelsinki());
  const save = useMutation({
    mutationFn: (clear: boolean) => api.setOutcome(app.id, clear ? { outcome: null } : buildOutcome(outcome, on)),
    onSuccess: (_r, clear) => { if (clear) { setOutcome(""); setOn(todayHelsinki()); } toast.success("Saved"); onChanged(); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <form className="mb-6 flex flex-wrap items-end gap-3 rounded-lg border bg-card p-4" onSubmit={(e) => { e.preventDefault(); save.mutate(false); }}>
      <div className="space-y-1.5">
        <Label htmlFor="outcome">What happened?</Label>
        <select id="outcome" className={selectClass} value={outcome} onChange={(e) => setOutcome(e.target.value as ApplicationOutcome | "")}>
          <option value="">Choose…</option>
          {OUTCOMES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="outcome-on">Date</Label>
        <Input id="outcome-on" type="date" value={on} onChange={(e) => setOn(e.target.value)} className="w-auto" />
      </div>
      <Button type="submit" size="sm" disabled={!outcome || save.isPending}>Save</Button>
      {app.outcome && <Button type="button" size="sm" variant="ghost" disabled={save.isPending} onClick={() => save.mutate(true)}>Clear</Button>}
    </form>
  );
}
