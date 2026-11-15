import type { FeedRead } from "@/api/types";
import { feedAttribution } from "@/lib/job-feeds";

export function FeedAttribution({ sourceKey, feeds }: { sourceKey: string; feeds: FeedRead[] }) {
  const attribution = feedAttribution(sourceKey, feeds);
  return attribution ? <p className="plain-text text-xs text-muted-foreground">{attribution}</p> : null;
}