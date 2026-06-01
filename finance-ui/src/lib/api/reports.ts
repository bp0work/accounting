import { apiFetch, downloadCsv } from './client';

export type TrialBalanceRow = {
  account_code: string;
  account_name: string;
  debit: string | null;
  credit: string | null;
  balance: string;
};

export type TrialBalanceGroup = {
  account_type: string;
  label: string;
  rows: TrialBalanceRow[];
  total_balance: string;
};

export type TrialBalanceReport = {
  as_at: string;
  groups: TrialBalanceGroup[];
  grand_total_balance: string;
};

export function fetchTrialBalance(asAt?: string) {
  const q = asAt ? `?as_at=${encodeURIComponent(asAt)}` : '';
  return apiFetch<TrialBalanceReport>(`/reports/trial-balance${q}`);
}

export function downloadTrialBalanceCsv(asAt?: string) {
  const q = asAt ? `?as_at=${encodeURIComponent(asAt)}` : '';
  const datePart = asAt ?? new Date().toISOString().slice(0, 10);
  return downloadCsv(`/reports/trial-balance/export${q}`, `trial_balance_${datePart}.csv`);
}
