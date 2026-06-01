/** Shared helpers for parsing confirmation and manual review extracted-field display. */

export function normalizeExtractedFields(raw: unknown): Record<string, string | null> {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
  const out: Record<string, string | null> = {};
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    out[key] = value == null ? null : String(value);
  }
  return out;
}

export function trimExtractedOptional(value: string | null | undefined): string | null {
  if (value == null) return null;
  const trimmed = String(value).trim();
  return trimmed || null;
}

export function hasExtractedGlAccountId(extracted: Record<string, string | null>): boolean {
  return trimExtractedOptional(extracted.gl_account_id) != null;
}
