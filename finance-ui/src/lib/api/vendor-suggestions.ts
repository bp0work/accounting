import { apiFetch } from './client';

export type VendorSuggestion = {
  name: string;
  source: 'counterparty' | 'case_history';
  counterparty_type: string | null;
  email: string | null;
};

export function fetchVendorSuggestions(search: string, limit = 10) {
  const q = new URLSearchParams({ search, limit: String(limit) });
  return apiFetch<VendorSuggestion[]>(`/vendor-suggestions?${q}`);
}
