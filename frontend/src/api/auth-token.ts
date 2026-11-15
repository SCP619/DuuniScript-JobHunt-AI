// Sign-in token: kept in memory and sessionStorage (never localStorage), so it ends with the browser session.
const KEY = "duuniscript-token";
let token: string | null = null;
let loaded = false;
const listeners = new Set<() => void>();

function storage(): Storage | null {
  try { return typeof window === "undefined" ? null : window.sessionStorage; } catch { return null; }
}

export function getToken(): string | null {
  if (!loaded) { loaded = true; token = storage()?.getItem(KEY) ?? null; }
  return token;
}

export function setToken(t: string | null) {
  token = t; loaded = true;
  const s = storage();
  if (t) s?.setItem(KEY, t); else s?.removeItem(KEY);
}

/** Called by the HTTP layer when the backend answers 401 auth_required. */
export function signalAuthRequired() {
  setToken(null);
  listeners.forEach((l) => l());
}

export function onAuthRequired(l: () => void) {
  listeners.add(l);
  return () => { listeners.delete(l); };
}
