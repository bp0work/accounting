import { apiFetch, apiUrl } from './client';

export type SessionUser = {
  id: string;
  username: string;
  display_name: string;
  email: string;
  role_name: string | null;
  two_factor_enabled: boolean;
  last_login_at?: string | null;
};

export type TwoFactorSetupResult = {
  secret: string;
  qr_code_uri: string;
  backup_codes: string[];
};

export type LoginUserResponse = {
  id: string;
  username: string;
  display_name: string;
  email: string;
  role_name?: string | null;
  two_factor_enabled: boolean;
  last_login_at?: string | null;
};

export type ActiveSession = {
  id: string;
  created_at: string;
  expires_at: string;
  revoked_at: string | null;
};

export type LoginRequest = {
  username: string;
  password: string;
  totp_code?: string;
};

export type LoginSuccess = {
  access_token: string;
  refresh_token: string;
  user: LoginUserResponse;
};

export type LoginError = {
  code: string;
  message: string;
};

/** API codes that require a second login step with TOTP (`05` §3). */
export const LOGIN_TOTP_REQUIRED_CODES = new Set(['TOTP_REQUIRED', '2FA_REQUIRED']);

export function isLoginTotpRequired(code: string): boolean {
  return LOGIN_TOTP_REQUIRED_CODES.has(code);
}

export async function loginRequest(
  payload: LoginRequest,
): Promise<{ ok: true; data: LoginSuccess } | { ok: false; error: LoginError }> {
  const body: Record<string, string> = {
    username: payload.username,
    password: payload.password,
  };
  if (payload.totp_code) {
    body.totp_code = payload.totp_code;
  }

  const res = await fetch(apiUrl('/auth/login'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();

  if (!res.ok) {
    return {
      ok: false,
      error: {
        code: data?.error?.code ?? 'LOGIN_FAILED',
        message: data?.error?.message ?? 'Login failed',
      },
    };
  }

  if (!data.access_token || !data.refresh_token) {
    return {
      ok: false,
      error: {
        code: 'LOGIN_FAILED',
        message: 'Login response missing tokens',
      },
    };
  }

  return { ok: true, data };
}

export function sessionUserFromLogin(user: LoginUserResponse): SessionUser {
  return {
    id: user.id,
    username: user.username,
    display_name: user.display_name,
    email: user.email,
    role_name: user.role_name ?? null,
    two_factor_enabled: user.two_factor_enabled,
    last_login_at: user.last_login_at ?? null,
  };
}

export function fetchMe() {
  return apiFetch<LoginUserResponse>('/auth/me');
}

export function listActiveSessions() {
  return apiFetch<ActiveSession[]>('/auth/sessions');
}

export function changePassword(currentPassword: string, newPassword: string) {
  return apiFetch<void>('/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
}

export function setup2fa() {
  return apiFetch<TwoFactorSetupResult>('/auth/2fa/setup', { method: 'POST' });
}

export function verify2fa(totpCode: string, secret: string) {
  return apiFetch<{ two_factor_enabled: boolean }>('/auth/2fa/verify', {
    method: 'POST',
    body: JSON.stringify({ totp_code: totpCode, secret }),
  });
}

/** Backend uses POST /auth/2fa/disable with TOTP confirmation (not DELETE). */
export function disable2fa(totpCode: string) {
  return apiFetch<void>('/auth/2fa/disable', {
    method: 'POST',
    body: JSON.stringify({ totp_code: totpCode }),
  });
}

export const MANDATORY_2FA_ROLES = new Set(['cfo', 'finance_manager']);

export function requires2faWarning(user: SessionUser | null): boolean {
  if (!user || user.two_factor_enabled) return false;
  const role = user.role_name?.toLowerCase() ?? '';
  return MANDATORY_2FA_ROLES.has(role);
}
