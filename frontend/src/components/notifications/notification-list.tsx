import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "@tanstack/react-router";
import { CalendarClock, MessageCircleQuestion, Send, Star, X } from "lucide-react";
import { toast } from "sonner";
import { api, errorMessage } from "@/api";
import { isInternalLink } from "@/lib/account";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { NotificationKind, NotificationRead } from "@/api/types";

const ICON: Record<NotificationKind, typeof Star> = { good_match: Star, deadline_soon: CalendarClock, ready_not_sent: Send, follow_up: MessageCircleQuestion };
const KIND_LABEL: Record<NotificationKind, string> = { good_match: "Good match", deadline_soon: "Deadline soon", ready_not_sent: "Ready, not sent", follow_up: "Follow up" };
export const NOTIFICATIONS_KEY = ["notifications"] as const;

export function NotificationList({ items, onNavigate }: { items: NotificationRead[]; onNavigate?: () => void }) {
  const qc = useQueryClient();
  const router = useRouter();
  const refresh = () => qc.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
  const read = useMutation({ mutationFn: api.readNotification, onSettled: refresh });
  const dismiss = useMutation({ mutationFn: api.dismissNotification, onSuccess: refresh, onError: (e) => toast.error(errorMessage(e)) });
  return (
    <ul className="divide-y">
      {items.map((n) => {
        const Icon = ICON[n.kind] ?? Star;
        return (
          <li key={n.id} className="flex items-start gap-2 py-2.5">
            <Icon aria-hidden className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
            <button type="button" className="min-w-0 flex-1 rounded text-left focus-visible:outline-2 focus-visible:outline-ring"
              onClick={() => { read.mutate(n.id); onNavigate?.(); if (isInternalLink(n.link)) router.navigate({ href: n.link }); }}>
              <span className="sr-only">{KIND_LABEL[n.kind]}: </span>
              <span className={cn("block text-sm", !n.read_at && "font-medium")}>{n.title}{!n.read_at && <span className="sr-only"> (unread)</span>}</span>
              <span className="plain-text block text-xs text-muted-foreground">{n.message}</span>
              <span className="block text-xs text-muted-foreground">{formatRelative(n.created_at)}</span>
            </button>
            <button type="button" aria-label={`Dismiss: ${n.title}`} className="rounded p-1 text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
              onClick={() => dismiss.mutate(n.id)}><X aria-hidden className="size-4" /></button>
          </li>
        );
      })}
    </ul>
  );
}
