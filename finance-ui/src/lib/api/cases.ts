import { apiFetch, downloadCsv } from './client';

export type CaseItem = {
  id: string;
  case_number: string;
  type: string;
  status: string;
  subject: string;
  counterparty_name?: string | null;
  amount_value?: string | null;
  amount_currency: string;
  created_at: string;
  completed_at?: string | null;
  sla_deadline?: string | null;
  processing_time_minutes?: number | null;
  is_overdue: boolean;
};

export type CaseDashboard = {
  queue_depths: {
    intake_queue: number;
    accounts_queue: number;
    dead_letter_queue: number;
    retry_queue_pending: number;
  };
  cases_by_status: Record<string, number>;
  average_processing_time_minutes: number | null;
  overdue_count: number;
  overdue_cases: CaseItem[];
};

export function fetchDashboard() {
  return apiFetch<CaseDashboard>('/cases/dashboard');
}

export function listCases(limit = 200) {
  return apiFetch<{ data: CaseItem[] }>(`/cases?limit=${limit}`);
}

export function exportCasesCsv(dateFrom: string, dateTo: string) {
  const q = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
  return downloadCsv(`/cases/export?${q}`, `transactions_${dateFrom}_${dateTo}.csv`);
}
