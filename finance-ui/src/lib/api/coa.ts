import { apiFetch } from './client';

export type CoaAccountItem = {
  id: string;
  account_code: string;
  account_name: string;
  account_subtype?: string | null;
};

export function listCoaAccounts(params?: { account_type?: string; is_active?: boolean }) {
  const q = new URLSearchParams();
  if (params?.account_type) q.set('account_type', params.account_type);
  if (params?.is_active != null) q.set('is_active', String(params.is_active));
  const suffix = q.toString() ? `?${q}` : '';
  return apiFetch<CoaAccountItem[]>(`/coa-accounts${suffix}`);
}
