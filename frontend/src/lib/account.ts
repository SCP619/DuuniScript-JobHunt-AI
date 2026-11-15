// Browser-safe presentation helpers for sign-in, connected accounts, notifications, outcomes and Gmail.
// Rules (who may send, what is valid) stay in the API; these only shape what the user entered.
import type {
  ApplicationOutcome, IntegrationsStatus, OutcomeUpdate, SendEmailRequest, TemplateRead,
} from "@/api/types";
import type { Tone } from "./labels";

export const MIN_PASSPHRASE = 10;

/** Form check only (the API enforces the real rule): returns an English message or null. */
export function passphraseProblem(a: string, b: string): string | null {
  if (a.length < MIN_PASSPHRASE) return `Use at least ${MIN_PASSPHRASE} characters.`;
  if (a !== b) return "The two passphrases don't match.";
  return null;
}

export const POLL_MS = 3000;
export const GMAIL_POLL_LIMIT_MS = 5 * 60 * 1000;

/**
 * Poll interval for GET /integrations: every 3 s while the Gmail consent window is open (up to
 * 5 minutes, until connected) or while the Microsoft device sign-in is waiting; otherwise off.
 */
export function integrationsPollInterval(data: IntegrationsStatus | undefined, gmailPollUntil: number | null, now = Date.now()): number | false {
  if (!data) return false;
  if (data.microsoft_sign_in.status === "waiting") return POLL_MS;
  if (gmailPollUntil !== null && now < gmailPollUntil && !data.google.connected) return POLL_MS;
  return false;
}

export const OUTCOMES: { value: ApplicationOutcome; label: string; tone: Tone }[] = [
  { value: "no_response", label: "No response yet", tone: "muted" },
  { value: "interview", label: "Interview", tone: "info" },
  { value: "rejected", label: "Rejected", tone: "neutral" },
  { value: "offer", label: "Offer", tone: "success" },
  { value: "accepted", label: "Accepted", tone: "success" },
  { value: "declined", label: "Declined", tone: "neutral" },
];
export const outcomeInfo = (o: string | null | undefined) => OUTCOMES.find((x) => x.value === o) ?? (o ? { value: o, label: o.replace(/_/g, " "), tone: "neutral" as Tone } : null);

export function buildOutcome(outcome: ApplicationOutcome | "", on: string): OutcomeUpdate {
  return outcome ? { outcome, outcome_on: on || null } : { outcome: null };
}

/** Prefill only when the posting lists exactly one address. */
export function defaultRecipient(contactEmails: string[]): string {
  return contactEmails.length === 1 ? contactEmails[0]! : "";
}

export function buildSendEmail(packageHash: string, to: string): SendEmailRequest {
  return { confirm: true, package_hash: packageHash, to: to.trim() };
}

export const RECOMMENDED_TEMPLATE = "utu_rekry";
export const RECOMMENDED_NOTE = "Recommended by UTU career services";

/** Recommended template first; the rest keep the API's order. */
export function sortTemplates(items: TemplateRead[]): TemplateRead[] {
  return [...items.filter((t) => t.key === RECOMMENDED_TEMPLATE), ...items.filter((t) => t.key !== RECOMMENDED_TEMPLATE)];
}

/** Only follow in-app links from notifications. */
export const isInternalLink = (link: string) => link.startsWith("/") && !link.startsWith("//");
