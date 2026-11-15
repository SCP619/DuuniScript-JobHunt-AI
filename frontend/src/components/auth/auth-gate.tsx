import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/states";
import { api, errorMessage } from "@/api";
import { onAuthRequired, setToken } from "@/api/auth-token";
import type { AuthStatus } from "@/api/types";

export const AUTH_KEY = ["auth"] as const;

/** Shows the Sign in page instead of the current page when needed; the route stays the same. */
export function AuthGate({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: AUTH_KEY, queryFn: api.authStatus });
  useEffect(() => onAuthRequired(() => {
    qc.setQueryData<AuthStatus>(AUTH_KEY, { password_set: true, signed_in: false });
  }), [qc]);

  if (status.isPending) return <LoadingState label="Opening DuuniScript…" />;
  const s = status.data;
  if (s && s.password_set && !s.signed_in) return <SignInPage />;
  return <>{children}</>;
}

export function SignInPage() {
  const qc = useQueryClient();
  const [pw, setPw] = useState("");
  const login = useMutation({
    mutationFn: () => api.login(pw),
    onSuccess: (t) => {
      setToken(t.token);
      qc.setQueryData<AuthStatus>(AUTH_KEY, { password_set: true, signed_in: true });
      // Everything that failed while signed out is loaded again for the same page.
      qc.invalidateQueries();
    },
  });
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background px-4">
      <form className="w-full max-w-sm space-y-5 rounded-lg border bg-card p-6" onSubmit={(e) => { e.preventDefault(); login.mutate(); }}>
        <div>
          <p className="font-display text-xl font-semibold">DuuniScript</p>
          <h1 className="mt-4 text-2xl font-medium">Sign in</h1>
          <p className="mt-1 text-sm text-muted-foreground">Enter the passphrase you created for DuuniScript on this computer.</p>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="signin-pw">Passphrase</Label>
          <Input id="signin-pw" type="password" autoComplete="current-password" autoFocus value={pw}
            onChange={(e) => setPw(e.target.value)} aria-describedby={login.error ? "signin-err" : undefined} />
        </div>
        <div aria-live="polite">{login.error && <p id="signin-err" role="alert" className="text-sm text-destructive">{errorMessage(login.error)}</p>}</div>
        <Button type="submit" className="w-full" disabled={!pw || login.isPending}>{login.isPending && <Loader2 aria-hidden className="size-4 animate-spin" />}Sign in</Button>
      </form>
    </div>
  );
}
