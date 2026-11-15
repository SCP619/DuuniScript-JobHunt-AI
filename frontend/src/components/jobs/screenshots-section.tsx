import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, errorMessage } from "@/api";
import type { JobAttachmentRead } from "@/api/job-additions";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ErrorState } from "@/components/states";
export function ScreenshotsSection({ jobId }: { jobId: string }) {
  const q = useQuery({ queryKey: ["jobAttachments", jobId], queryFn: () => api.listJobAttachments(jobId) });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data?.length) return null;
  return <section className="space-y-3 border-y py-5"><h2 className="text-xl font-medium">Screenshots</h2><div className="flex flex-wrap gap-3">{q.data.map((a, i) => <Screenshot key={a.id} jobId={jobId} attachment={a} index={i} />)}</div></section>;
}
function Screenshot({ jobId, attachment, index }: { jobId: string; attachment: JobAttachmentRead; index: number }) {
  const [url, setUrl] = useState<string | null>(null); const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ["jobAttachment", jobId, attachment.id], queryFn: () => api.downloadJobAttachment(jobId, attachment.id) });
  useEffect(() => { if (!q.data) return; const objectUrl = URL.createObjectURL(q.data.blob); setUrl(objectUrl); return () => URL.revokeObjectURL(objectUrl); }, [q.data]);
  if (q.isError) return <p role="alert" className="plain-text text-sm text-destructive">{errorMessage(q.error)}</p>;
  return <><Button variant="outline" className="h-36 w-28 p-2" aria-label={`Open screenshot ${index + 1}`} disabled={!url} onClick={() => setOpen(true)}>{url ? <img className="h-full w-full object-contain" src={url} alt={`Screenshot ${index + 1}`} /> : "Loading…"}</Button><Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-h-[90vh] overflow-auto sm:max-w-5xl"><DialogHeader><DialogTitle className="plain-text break-all">{attachment.filename}</DialogTitle></DialogHeader>{url && <img src={url} alt={`Full screenshot ${index + 1}`} className="h-auto w-full object-contain" />}</DialogContent></Dialog></>;
}
