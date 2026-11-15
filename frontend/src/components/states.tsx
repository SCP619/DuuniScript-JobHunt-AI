import { useState, type ReactNode } from "react";
import { AlertCircle, Loader2, PlugZap, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, errorMessage, isOffline } from "@/api";
import { cn } from "@/lib/utils";

export function LoadingState({ label = "Loading…", className }: { label?: string; className?: string }) {
  return (
    <div role="status" aria-live="polite" className={cn("flex items-center gap-2 py-10 text-sm text-muted-foreground", className)}>
      <Loader2 aria-hidden className="size-4 animate-spin" />
      {label}
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed bg-card px-6 py-10 text-center">
      <h3 className="text-lg font-medium">{title}</h3>
      {children && <div className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">{children}</div>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

/** Error from the API, with a dedicated offline state that checks /health before retrying. */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => unknown }) {
  const [checking, setChecking] = useState(false);
  const offline = isOffline(error);
  const retry = async () => {
    setChecking(true);
    try {
      await api.health().catch(() => undefined);
      await onRetry?.();
    } finally {
      setChecking(false);
    }
  };
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-lg border bg-card p-5 sm:flex-row sm:items-center">
      {offline ? <PlugZap aria-hidden className="size-5 text-warning" /> : <AlertCircle aria-hidden className="size-5 text-destructive" />}
      <div className="flex-1">
        <p className="font-medium">{offline ? "Backend not reachable" : "This couldn't be loaded"}</p>
        <p className="text-sm text-muted-foreground">{errorMessage(error)}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={retry} disabled={checking}>
          {checking ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <RotateCw className="size-4" aria-hidden />}
          Retry
        </Button>
      )}
    </div>
  );
}

export function Muted({ children }: { children: ReactNode }) {
  return <span className="text-muted-foreground">{children}</span>;
}

export function NotStated() {
  return <span className="text-muted-foreground">Not stated</span>;
}
