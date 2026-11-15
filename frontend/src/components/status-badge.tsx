import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";
import type { Tone } from "@/lib/labels";

const pill = cva(
  "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium",
  {
    variants: {
      tone: {
        neutral: "border-border bg-secondary text-secondary-foreground",
        info: "border-transparent bg-info-soft text-info",
        success: "border-transparent bg-success-soft text-success",
        warning: "border-transparent bg-warning-soft text-warning",
        danger: "border-transparent bg-danger-soft text-destructive",
        muted: "border-border bg-background text-muted-foreground",
        primary: "border-transparent bg-accent text-accent-foreground",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

const dot: Record<Tone, string> = {
  neutral: "bg-muted-foreground", info: "bg-info", success: "bg-success", warning: "bg-warning",
  danger: "bg-destructive", muted: "bg-border", primary: "bg-primary",
};

/** Status always carries a text label; color is supplementary. */
export function StatusBadge({ tone = "neutral", label, className }: { tone?: Tone; label: string; className?: string }) {
  return (
    <span className={cn(pill({ tone }), className)}>
      <span aria-hidden className={cn("size-1.5 rounded-full", dot[tone])} />
      {label}
    </span>
  );
}
