const ACCESS_TOKEN_KEY = 'finance_access_token';
const REFRESH_TOKEN_KEY = 'finance_refresh_token';
const SESSION_USER_KEY = 'finance_session_user';
/** Refresh access token when within this many seconds of JWT `exp`. */
const EXPIRY_BUFFER_SEC = 120;

type RefreshResponse = {
  access_token: string;
  token_type?: string;
  expires_in?: number;
};

let refreshInFlight: Promise<string> | null = null;

function base64UrlDecode(input: string): string {
  const padded = input.replace(/-/g, '+').replace(/_/g, '/');
  const pad = padded.length % 4 === 0 ? padded : padded + '='.repeat(4 - (padded.length % 4));
  return atob(pad);
}

/** JWT `exp` claim (Unix seconds), or null if missing/invalid. */
export function decodeJwtExp(token: string): number | null {
  try {
    const parts = token.split('.');
    if (parts.length < 2) return null;
    const payload = JSON.parse(base64UrlDecode(parts[1])) as { exp?: unknown };
    return typeof payload.exp === 'number' ? payload.exp : null;
  } catch {
    return null;
  }
}

export function isAccessTokenNearExpiry(token: string, bufferSec = EXPIRY_BUFFER_SEC): boolean {
  const exp = decodeJwtExp(token);
  if (exp === null) return true;
  const nowSec = Math.floor(Date.now() / 1000);
  return exp - nowSec <= bufferSec;
}

export function getToken(): string | null {
  if (typeof localStorage === 'undefined') return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof localStorage === 'undefined') return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function setRefreshToken(token: string) {
  localStorage.setItem(REFRESH_TOKEN_KEY, token);
}

export function setTokens(accessToken: string, refreshToken: string) {
  setToken(accessToken);
  setRefreshToken(refreshToken);
}

export function clearToken() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(SESSION_USER_KEY);
}

export type StoredSessionUser = {
  id: string;
  username: string;
  display_name: string;
  email: string;
  role_name: string | null;
  two_factor_enabled: boolean;
};

export function setSessionUser(user: StoredSessionUser) {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(SESSION_USER_KEY, JSON.stringify(user));
}

export function getSessionUser(): StoredSessionUser | null {
  if (typeof localStorage === 'undefined') return null;
  const raw = localStorage.getItem(SESSION_USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredSessionUser;
  } catch {
    return null;
  }
}

async function redirectToLogin(): Promise<void> {
  clearToken();
  if (typeof window === 'undefined') return;
  const { goto } = await import('$app/navigation');
  await goto('/login');
}

async function refreshAccessToken(): Promise<string> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    await redirectToLogin();
    throw new Error('Session expired');
  }

  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    const res = await fetch('/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) {
      await redirectToLogin();
      throw new Error('Session expired');
    }
    const data = (await res.json()) as RefreshResponse;
    if (!data.access_token) {
      await redirectToLogin();
      throw new Error('Session expired');
    }
    setToken(data.access_token);
    return data.access_token;
  })();

  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

/** Returns a valid access token, silently refreshing when near expiry. */
export async function ensureValidAccessToken(): Promise<string | null> {
  const token = getToken();
  if (!token) return null;
  if (!isAccessTokenNearExpiry(token)) return token;
  return refreshAccessToken();
}

export async function downloadCsv(path: string, filename: string): Promise<void> {
  const token = await ensureValidAccessToken();
  const headers = new Headers();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const res = await fetch(path, { headers });
  if (res.status === 401) {
    await redirectToLogin();
    throw new Error('Session expired');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.error?.message || res.statusText || 'Download failed');
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await ensureValidAccessToken();
  const headers = new Headers(init.headers);
  headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);

  let res = await fetch(path, { ...init, headers });

  if (res.status === 401 && getRefreshToken()) {
    try {
      const newToken = await refreshAccessToken();
      headers.set('Authorization', `Bearer ${newToken}`);
      res = await fetch(path, { ...init, headers });
    } catch {
      throw new Error('Session expired');
    }
  }

  if (res.status === 401) {
    await redirectToLogin();
    throw new Error('Session expired');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.error?.message || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
