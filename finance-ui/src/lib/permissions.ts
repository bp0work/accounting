import { getToken } from '$lib/api/client';

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.');
    if (parts.length < 2) return null;
    const padded = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const pad = padded.length % 4 === 0 ? padded : padded + '='.repeat(4 - (padded.length % 4));
    return JSON.parse(atob(pad)) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** Permission codes from the current access token (`permissions` JWT claim). */
export function getSessionPermissions(): string[] {
  const token = getToken();
  if (!token) return [];
  const payload = decodeJwtPayload(token);
  const raw = payload?.permissions;
  if (!Array.isArray(raw)) return [];
  return raw.filter((p): p is string => typeof p === 'string');
}

export function hasPermission(code: string): boolean {
  return getSessionPermissions().includes(code);
}
