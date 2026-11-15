import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, errorMessage } from "@/api";
import type { JobRead } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { ScreenshotReview } from "./screenshot-import";
export function PasteTextImport({ onSaved }: { onSaved: (job: JobRead) => void }) {
  const [text, setText] = useState("");
  const read = useMutation({ mutationFn: () => api.readJobText({ text }), retry: false });
  if (read.data) return <ScreenshotReview draft={read.data} onSaved={onSaved} />;
  return <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); read.mutate(); }}><Label htmlFor="paste-job-text">Posting text</Label><Textarea id="paste-job-text" rows={12} value={text} onChange={(e) => setText(e.target.value)} disabled={read.isPending} />{read.isError && <p role="alert" className="plain-text text-sm text-destructive">{errorMessage(read.error)}</p>}<div className="flex justify-end"><Button disabled={!text.trim() || read.isPending}>{read.isPending ? "Reading text…" : "Read text"}</Button></div></form>;
}
