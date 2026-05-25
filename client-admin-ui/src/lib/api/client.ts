export const API_PREFIX = '/api';
/** localStorage key — layout reads synchronously for first-paint nav. */
export const ACCESS_TOKEN_KEY = 'client_admin_access_token';
const REFRESH_TOKEN_KEY = 'client_admin_refresh_token';
export function apiUrl(path: string): string {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  if (normalized === API_PREFIX || normalized.startsWith(`${API_PREFIX}/`)) return normalized;
  return `${API_PREFIX}${normalized}`;
}

export function getToken(): string | null {
  if (typeof localStorage === 'undefined') return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof localStorage === 'undefined') return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, access);
  localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
}

export function clearToken() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

let refreshInFlight: Promise<string> | null = null;

async function redirectToLogin() {
  clearToken();
  const { goto } = await import('$app/navigation');
  await goto('/login');
}

async function refreshAccessToken(): Promise<string> {
  const refresh = getRefreshToken();
  if (!refresh) {
    await redirectToLogin();
    throw new Error('Session expired');
  }
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    const res = await fetch(apiUrl('/auth/refresh'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) {
      await redirectToLogin();
      throw new Error('Session expired');
    }
    const data = (await res.json()) as { access_token: string };
    localStorage.setItem(ACCESS_TOKEN_KEY, data.access_token);
    return data.access_token;
  })();
  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

export async function ensureValidAccessToken(): Promise<string | null> {
  return getToken();
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  let token = getToken();
  if (!token) return redirectToLogin().then(() => undefined as T);
  const headers = new Headers(init.headers);
  headers.set('Content-Type', 'application/json');
  headers.set('Authorization', `Bearer ${token}`);
  const url = apiUrl(path);
  let res = await fetch(url, { ...init, headers });
  if (res.status === 401 && getRefreshToken()) {
    token = await refreshAccessToken();
    headers.set('Authorization', `Bearer ${token}`);
    res = await fetch(url, { ...init, headers });
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
