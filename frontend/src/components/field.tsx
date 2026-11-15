import type { ReactNode } from "react";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export function Field({
  id, label, error, hint, required, children, className,
}: { id: string; label: string; error?: string; hint?: ReactNode; required?: boolean; children: ReactNode; className?: string }) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={id}>
        {label}
        {required && <span className="text-muted-foreground"> (required)</span>}
      </Label>
      {children}
      {hint && !error && <p id={`${id}-hint`} className="text-xs text-muted-foreground">{hint}</p>}
      {error && (
        <p id={`${id}-error`} role="alert" className="text-xs font-medium text-destructive">{error}</p>
      )}
    </div>
  );
}

/** aria props to connect an input to its Field hint/error. */
export function describedBy(id: string, error?: string, hasHint?: boolean) {
  return {
    "aria-invalid": error ? true : undefined,
    "aria-describedby": error ? `${id}-error` : hasHint ? `${id}-hint` : undefined,
  } as const;
}

export const selectBase =
  "flex h-9 rounded-md border border-input bg-card px-3 py-1 text-sm shadow-xs focus-visible:outline-2 focus-visible:outline-ring disabled:opacity-50";
export const selectClass = `${selectBase} w-full`;
export const selectInline = `${selectBase} w-auto`;
