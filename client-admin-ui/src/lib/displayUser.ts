import { apiFetch, getToken } from '$lib/api/client';
import {
  getCachedDisplayUser,
  setCachedDisplayUser,
  type CachedDisplayUser,
} from '$lib/api/displayUserCache';
import { decodeJwtPayload } from '$lib/jwt';

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function looksLikeUuid(value: string): boolean {
  return UUID_RE.test(value.trim());
}

export function profileDisplayLabel(profile: CachedDisplayUser | null): string | null {
  if (!profile) return null;
  const displayName = profile.display_name?.trim();
  if (displayName) return displayName;
  const username = profile.username?.trim();
  if (username) return username;
  return null;
}

export function labelFromAccessToken(token: string): string | null {
  const payload = decodeJwtPayload(token);
  if (!payload) return null;

  for (const key of ['username', 'name', 'preferred_username', 'email'] as const) {
    const value = payload[key];
    if (typeof value === 'string' && value.trim() && !looksLikeUuid(value)) {
      return value.trim();
    }
  }

  const role = payload.role;
  if (typeof role === 'string' && role.trim()) {
    return role.replace(/_/g, ' ');
  }

  const sub = payload.sub;
  if (typeof sub === 'string' && sub.trim() && !looksLikeUuid(sub)) {
    return sub.trim();
  }

  return null;
}

type MeResponse = {
  username: string;
  display_name: string;
  email: string;
};

async function fetchAuthMe(): Promise<CachedDisplayUser> {
  const me = await apiFetch<MeResponse>('/auth/me');
  return {
    username: me.username,
    display_name: me.display_name,
    email: me.email,
  };
}

export async function resolveNavDisplayName(): Promise<string> {
  const fromCache = profileDisplayLabel(getCachedDisplayUser());
  if (fromCache) return fromCache;

  const token = getToken();
  if (token) {
    const fromJwt = labelFromAccessToken(token);
    if (fromJwt) return fromJwt;
  }

  try {
    const profile = await fetchAuthMe();
    setCachedDisplayUser(profile);
    const label = profileDisplayLabel(profile);
    if (label) return label;
  } catch {
    /* ignore */
  }

  return 'User';
}
