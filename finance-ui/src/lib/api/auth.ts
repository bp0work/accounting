import { apiFetch } from './client';

export type SessionUser = {
  id: string;
  username: string;
  display_name: string;
  email: string;
  role_name: string | null;
  two_factor_enabled: boolean;
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
};

export function sessionUserFromLogin(user: LoginUserResponse): SessionUser {
  return {
    id: user.id,
    username: user.username,
    display_name: user.display_name,
    email: user.email,
    role_name: user.role_name ?? null,
    two_factor_enabled: user.two_factor_enabled,
  };
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
