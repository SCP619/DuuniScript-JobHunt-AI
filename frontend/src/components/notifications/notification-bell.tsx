import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { api } from "@/api";
import { NOTIFICATIONS_KEY, NotificationList } from "./notification-list";

export function NotificationBell({ path }: { path: string }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: NOTIFICATIONS_KEY, queryFn: api.listNotifications, refetchInterval: 60_000 });
  useEffect(() => { qc.invalidateQueries({ queryKey: NOTIFICATIONS_KEY }); }, [path, qc]);
  const readAll = useMutation({ mutationFn: api.readAllNotifications, onSettled: () => qc.invalidateQueries({ queryKey: NOTIFICATIONS_KEY }) });
  const unread = q.data?.unread ?? 0;
  const items = q.data?.items ?? [];
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}>
          <Bell aria-hidden className="size-5" />
          {unread > 0 && <span aria-hidden className="absolute -right-0.5 -top-0.5 min-w-4 rounded-full bg-primary px-1 text-[10px] font-semibold leading-4 text-primary-foreground">{unread > 99 ? "99+" : unread}</span>}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <p className="border-b px-4 py-2.5 text-sm font-medium">Notifications</p>
        <div className="max-h-96 overflow-y-auto px-4">
          {q.isError ? <p className="py-4 text-sm text-muted-foreground">Couldn't load notifications.</p>
            : items.length === 0 ? <p className="py-4 text-sm text-muted-foreground">Nothing needs your attention.</p>
            : <NotificationList items={items} onNavigate={() => setOpen(false)} />}
        </div>
        <div className="border-t px-4 py-2">
          <Button variant="ghost" size="sm" className="w-full" disabled={unread === 0 || readAll.isPending} onClick={() => readAll.mutate()}>Mark all as read</Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
