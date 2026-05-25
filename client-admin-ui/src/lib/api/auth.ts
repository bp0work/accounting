import { apiFetch, apiUrl, setTokens } from './client';

export type LoginResult = {
  access_token: string;
  refresh_token: string;
  user: { role_name?: string | null };
};

export async function loginRequest(username: string, password: string, totpCode?: string) {
  const body: Record<string, string> = { username, password };
  if (totpCode) body.totp_code = totpCode;
  const res = await fetch(apiUrl('/auth/login'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.error?.message || 'Login failed');
  }
  if (data.user?.role_name !== 'client_admin') {
    throw new Error('Client administrator role required.');
  }
  return data as LoginResult;
}

export function completeLogin(data: LoginResult) {
  setTokens(data.access_token, data.refresh_token);
}
