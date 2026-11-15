export const TIME_ZONE = "Europe/Helsinki";

/** "YYYY-MM-DD" → "d.M.yyyy". Returns null for null/invalid. */
export function formatDateOnly(v: string | null | undefined): string | null {
  if (!v) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(v);
  if (!m) return null;
  return `${Number(m[3])}.${Number(m[2])}.${m[1]}`;
}

const dateFmt = new Intl.DateTimeFormat("fi-FI", { timeZone: TIME_ZONE, day: "numeric", month: "numeric", year: "numeric" });
const timeFmt = new Intl.DateTimeFormat("fi-FI", { timeZone: TIME_ZONE, hour: "2-digit", minute: "2-digit", hour12: false });

/** ISO timestamp → "d.M.yyyy" in Helsinki time. */
export function formatDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return dateFmt.format(d);
}

/** ISO timestamp → "d.M.yyyy at HH.mm" in Helsinki time. */
export function formatDateTime(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return `${dateFmt.format(d)} at ${timeFmt.format(d)}`;
}

/** Today's date in Helsinki as YYYY-MM-DD. */
export function todayHelsinki(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TIME_ZONE, year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}

export function isPastDate(dateOn: string | null, now = new Date()) {
  return !!dateOn && dateOn < todayHelsinki(now);
}

export function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

/** Local date + time inputs → ISO string with the browser's UTC offset. */
export function localDateTimeToIso(date: string, time: string): string {
  const d = new Date(`${date}T${time || "00:00"}:00`);
  const off = -d.getTimezoneOffset();
  const sign = off >= 0 ? "+" : "-";
  const pad = (n: number) => String(Math.floor(Math.abs(n))).padStart(2, "0");
  return `${date}T${time || "00:00"}:00${sign}${pad(off / 60)}:${pad(off % 60)}`;
}

/** ISO → local { date, time } strings for date/time inputs. */
export function isoToLocalInputs(iso: string | null): { date: string; time: string } {
  if (!iso) return { date: "", time: "" };
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return { date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`, time: `${pad(d.getHours())}:${pad(d.getMinutes())}` };
}

/** Calendar-day distance in Helsinki, for upcoming deadline labels. */
export function formatDayRelative(dateOn: string | null | undefined, now = new Date()): string | null {
  if (!dateOn || !/^\d{4}-\d{2}-\d{2}/.test(dateOn)) return null;
  const today = todayHelsinki(now);
  const days = Math.round((Date.parse(`${dateOn.slice(0, 10)}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / 86400000);
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  if (days > 1) return `in ${days} days`;
  if (days === -1) return "yesterday";
  return `${-days} days ago`;
}

/** ISO timestamp → "just now", "5 minutes ago", "3 hours ago", "2 days ago"; older than a week → date. */
export function formatRelative(iso: string | null | undefined, now = new Date()): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const mins = Math.round((now.getTime() - d.getTime()) / 60000);
  const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"} ago`;
  if (mins < 1) return "just now";
  if (mins < 60) return plural(mins, "minute");
  const hours = Math.round(mins / 60);
  if (hours < 24) return plural(hours, "hour");
  const days = Math.round(hours / 24);
  if (days <= 7) return plural(days, "day");
  return formatDate(iso);
}
