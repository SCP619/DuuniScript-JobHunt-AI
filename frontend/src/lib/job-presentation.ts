import type { JobRead } from "@/api/types";

/** Display metadata only; never translates published job content. */
export function languageLabel(code: string | null): string | null {
  if (code === null) return null;
  const primary = code.split("-")[0]?.toLowerCase();
  switch (primary) {
    case "en": return "English";
    case "fi": return "Finnish";
    case "sv": return "Swedish";
    default: return code.toUpperCase();
  }
}

export function originalPostingUrl(job: Pick<JobRead, "canonical_url" | "listings">): string | null {
  return job.canonical_url ?? job.listings.find((listing) => listing.source_url !== null)?.source_url ?? null;
}