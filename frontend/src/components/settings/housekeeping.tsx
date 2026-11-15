import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Brush } from "lucide-react";
import { toast } from "sonner";
import { api, errorMessage } from "@/api";
import { Button } from "@/components/ui/button";
export function Housekeeping() {
  const qc = useQueryClient();
  const tidy = useMutation({ mutationFn: api.housekeepingJobs, retry: false, onSuccess: (r) => { toast.success(`${r.expired} expired, ${r.archived} archived`); for (const key of ["jobs", "job", "dashboard"]) qc.invalidateQueries({ queryKey: [key] }); }, onError: (e) => toast.error(errorMessage(e)) });
  return <div className="flex items-center justify-between gap-3 border-y py-4"><h2 className="font-medium">Job housekeeping</h2><Button variant="outline" size="sm" disabled={tidy.isPending} onClick={() => tidy.mutate()}><Brush aria-hidden className="size-4" />Tidy up now</Button></div>;
}
