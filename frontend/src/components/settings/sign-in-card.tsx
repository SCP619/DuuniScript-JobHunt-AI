import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorState, LoadingState } from "@/components/states";
import { AUTH_KEY } from "@/components/auth/auth-gate";
import { api, errorMessage } from "@/api";
import { setToken } from "@/api/auth-token";
import { passphraseProblem } from "@/lib/account";
import type { AuthStatus } from "@/api/types";

function Pw({ id, label, value, onChange, auto }: { id: string; label: string; value: string; onChange: (v: string) => void; auto: string }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type="password" autoComplete={auto} value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

export function SignInCard() {
  const status = useQuery({ queryKey: AUTH_KEY, queryFn: api.authStatus });
  return (
    <section aria-labelledby="s-signin" className="rounded-lg border bg-card p-5">
      <h2 id="s-signin" className="mb-1 text-xl font-medium">Sign-in</h2>
      <p className="mb-4 text-sm text-muted-foreground">This protects DuuniScript only. It does not sign you in to other websites — use your browser's password manager for those.</p>
      {status.isLoading ? <LoadingState className="py-2" /> : status.isError ? <ErrorState error={status.error} onRetry={() => status.refetch()} />
        : status.data?.password_set ? <ChangeForm /> : <CreateForm />}
    </section>
  );
}

function CreateForm() {
  const qc = useQueryClient();
  const [a, setA] = useState(""); const [b, setB] = useState("");
  const [tried, setTried] = useState(false);
  const problem = passphraseProblem(a, b);
  const m = useMutation({
    mutationFn: () => api.setupPassword(a),
    onSuccess: (t) => { setToken(t.token); qc.setQueryData<AuthStatus>(AUTH_KEY, { password_set: true, signed_in: true }); toast.success("Passphrase created"); },
  });
  return (
    <form className="max-w-sm space-y-3" onSubmit={(e) => { e.preventDefault(); setTried(true); if (!problem) m.mutate(); }}>
      <p className="text-sm">No passphrase yet. Anyone using this computer can open DuuniScript.</p>
      <Pw id="pw-new" label="New passphrase (at least 10 characters)" value={a} onChange={setA} auto="new-password" />
      <Pw id="pw-new2" label="Type it again" value={b} onChange={setB} auto="new-password" />
      <div aria-live="polite">
        {tried && problem && <p role="alert" className="text-sm text-destructive">{problem}</p>}
        {m.error && <p role="alert" className="text-sm text-destructive">{errorMessage(m.error)}</p>}
      </div>
      <Button type="submit" disabled={m.isPending}>{m.isPending && <Loader2 aria-hidden className="size-4 animate-spin" />}Create passphrase</Button>
    </form>
  );
}

function ChangeForm() {
  const qc = useQueryClient();
  const [cur, setCur] = useState(""); const [a, setA] = useState(""); const [b, setB] = useState("");
  const [tried, setTried] = useState(false);
  const problem = passphraseProblem(a, b);
  const change = useMutation({
    mutationFn: () => api.changePassword({ current_password: cur, new_password: a }),
    onSuccess: () => { setCur(""); setA(""); setB(""); setTried(false); toast.success("Passphrase changed"); },
  });
  const signOut = useMutation({
    mutationFn: api.logout,
    onSettled: () => { setToken(null); qc.setQueryData<AuthStatus>(AUTH_KEY, { password_set: true, signed_in: false }); },
  });
  return (
    <div className="space-y-5">
      <form className="max-w-sm space-y-3" onSubmit={(e) => { e.preventDefault(); setTried(true); if (!problem && cur) change.mutate(); }}>
        <p className="text-sm font-medium">Change passphrase</p>
        <Pw id="pw-cur" label="Current passphrase" value={cur} onChange={setCur} auto="current-password" />
        <Pw id="pw-chg" label="New passphrase (at least 10 characters)" value={a} onChange={setA} auto="new-password" />
        <Pw id="pw-chg2" label="Type the new one again" value={b} onChange={setB} auto="new-password" />
        <div aria-live="polite">
          {tried && !cur && <p role="alert" className="text-sm text-destructive">Enter your current passphrase.</p>}
          {tried && problem && <p role="alert" className="text-sm text-destructive">{problem}</p>}
          {change.error && <p role="alert" className="text-sm text-destructive">{errorMessage(change.error)}</p>}
        </div>
        <Button type="submit" disabled={change.isPending}>{change.isPending && <Loader2 aria-hidden className="size-4 animate-spin" />}Change passphrase</Button>
      </form>
      <div className="border-t pt-4">
        <Button variant="outline" onClick={() => signOut.mutate()} disabled={signOut.isPending}>Sign out</Button>
      </div>
    </div>
  );
}
