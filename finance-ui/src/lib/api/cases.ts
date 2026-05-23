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
  processing_stage?: string | null;
  error_reason?: string | null;
  status_reason?: string | null;
  last_activity_at?: string | null;
  workflow_metadata?: Record<string, unknown>;
  classification_metadata?: Record<string, unknown>;
};

export type TimelineEntry = {
  id: string;
  event_type: string;
  from_status?: string | null;
  to_status?: string | null;
  actor: string;
  description?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
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

export function fetchCase(caseId: string) {
  return apiFetch<CaseItem>(`/cases/${caseId}`);
}

export function fetchCaseTimeline(caseId: string) {
  return apiFetch<TimelineEntry[]>(`/cases/${caseId}/timeline`);
}

export function exportCasesCsv(dateFrom: string, dateTo: string) {
  const q = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
  return downloadCsv(`/cases/export?${q}`, `transactions_${dateFrom}_${dateTo}.csv`);
}
