import type { ReactNode } from "react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { buttonVariants } from "@/components/ui/button";

export function ConfirmDialog({
  open, onOpenChange, title, description, confirmLabel, onConfirm, pending, destructive = true, children, confirmDisabled,
}: {
  open: boolean; onOpenChange: (o: boolean) => void; title: string; description: ReactNode; confirmLabel: string;
  onConfirm: () => void; pending?: boolean; destructive?: boolean; children?: ReactNode; confirmDisabled?: boolean;
}) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription asChild><div>{description}</div></AlertDialogDescription>
        </AlertDialogHeader>
        {children}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            className={buttonVariants({ variant: destructive ? "destructive" : "default" })}
            disabled={pending || confirmDisabled}
            onClick={(e) => {
              e.preventDefault();
              onConfirm();
            }}
          >
            {pending ? "Working…" : confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
