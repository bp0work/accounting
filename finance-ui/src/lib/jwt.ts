function base64UrlDecode(input: string): string {
  const padded = input.replace(/-/g, '+').replace(/_/g, '/');
  const pad = padded.length % 4 === 0 ? padded : padded + '='.repeat(4 - (padded.length % 4));
  return atob(pad);
}

/** JWT `sub` claim (typically username), or null if missing/invalid. */
export function decodeJwtSub(token: string): string | null {
  try {
    const parts = token.split('.');
    if (parts.length < 2) return null;
    const payload = JSON.parse(base64UrlDecode(parts[1])) as { sub?: unknown };
    if (typeof payload.sub === 'string' && payload.sub.trim()) return payload.sub.trim();
    return null;
  } catch {
    return null;
  }
}
