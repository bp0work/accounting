import { apiFetch, getSessionUser, setSessionUser, type StoredSessionUser } from '$lib/api/client';
import { decodeJwtPayload } from '$lib/jwt';

export type ProfileForDisplay = {
  username: string;
  display_name: string;
  email?: string;
};

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function looksLikeUuid(value: string): boolean {
  return UUID_RE.test(value.trim());
}

/** Prefer display_name, then username; ignore empty strings. */
export function profileDisplayLabel(profile: ProfileForDisplay | StoredSessionUser | null): string | null {
  if (!profile) return null;
  const displayName = profile.display_name?.trim();
  if (displayName) return displayName;
  const username = profile.username?.trim();
  if (username) return username;
  return null;
}

/** JWT carries `sub` (user UUID), `role`, and `permissions` only — see `app/core/jwt.py`. */
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
  id: string;
  username: string;
  display_name: string;
  email: string;
  role_name?: string | null;
  two_factor_enabled?: boolean;
};

async function fetchAuthMe(): Promise<ProfileForDisplay> {
  const me = await apiFetch<MeResponse>('/auth/me');
  return {
    username: me.username,
    display_name: me.display_name,
    email: me.email,
  };
}

function cacheFromMe(me: MeResponse): void {
  const existing = getSessionUser();
  setSessionUser({
    id: me.id,
    username: me.username,
    display_name: me.display_name,
    email: me.email,
    role_name: me.role_name ?? existing?.role_name ?? null,
    two_factor_enabled: me.two_factor_enabled ?? existing?.two_factor_enabled ?? false,
  });
}

/** Resolve nav label: session cache → JWT role → GET /auth/me → "User". */
export async function resolveNavDisplayName(getToken: () => string | null): Promise<string> {
  const fromSession = profileDisplayLabel(getSessionUser());
  if (fromSession) return fromSession;

  const token = getToken();
  if (token) {
    const fromJwt = labelFromAccessToken(token);
    if (fromJwt) return fromJwt;
  }

  try {
    const me = await fetchAuthMe();
    cacheFromMe(me);
    const label = profileDisplayLabel(me);
    if (label) return label;
  } catch {
    /* ignore — show fallback */
  }

  return 'User';
}
