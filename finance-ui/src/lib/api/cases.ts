import { apiFetch, downloadCsv } from './client';

export type CaseItem = {
  id: string;
  case_number: string;
  type: string;
  status: string;
  subject: string;
  counterparty_name?: string | null;
  client_vendor_name?: string | null;
  from_address?: string | null;
  submitted_by?: string | null;
  amount_value?: string | null;
  amount_currency: string;
  created_at: string;
  completed_at?: string | null;
  sla_deadline?: string | null;
  processing_time_minutes?: number | null;
  is_overdue: boolean;
  processing_stage?: string | null;
  status_group?: string | null;
  status_group_label?: string | null;
  action_by?: string | null;
  status_label?: string | null;
  error_reason?: string | null;
  status_reason?: string | null;
  last_activity_at?: string | null;
  workflow_metadata?: Record<string, unknown>;
  classification_metadata?: Record<string, unknown>;
  linked_gl_period_status?: string | null;
  current_approval_tier?: number | null;
  pending_approval_id?: string | null;
  binding_escalated_to_cfo?: boolean;
  journal_entry?: JournalEntryApprovalDetail | null;
};

export type JournalEntryApprovalDetail = {
  vendor?: string | null;
  document_number?: string | null;
  document_date?: string | null;
  document_type?: string | null;
  amount_sgd?: string | null;
  gst?: string | null;
  total?: string | null;
  debit_account?: string | null;
  credit_account?: string | null;
  approval_tier_label?: string | null;
  journal_entry_id?: string | null;
  entry_number?: string | null;
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

export type CaseRetryResult = {
  case_id: string;
  case_number: string;
  message_id: string;
  status: string;
  previous_status: string;
};

export function retryCase(caseId: string) {
  return apiFetch<CaseRetryResult>(`/cases/${caseId}/retry`, { method: 'POST' });
}

export type EscalationRespondResult = {
  escalation_id: string;
  case_id: string;
  action: string;
  status: string;
  message?: string | null;
  manager_comment?: string | null;
};

export function respondToCaseEscalation(
  caseId: string,
  body: { action: 'approve' | 'reject' | 'request_info' | 'retry'; comment?: string | null }
) {
  return apiFetch<EscalationRespondResult>(`/cases/${caseId}/escalation-respond`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export type ParsingConfirmationFields = {
  document_type: string;
  document_number?: string | null;
  document_date?: string | null;
  due_date?: string | null;
  vendor_name?: string | null;
  total_amount?: string | null;
  tax_amount?: string | null;
  currency: string;
  exchange_rate?: string | null;
  payment_terms?: string | null;
  business_purpose?: string | null;
  gl_account_id?: string | null;
  sender_validated: boolean;
};

export type ConfirmParsingResult = {
  case_id: string;
  case_number: string;
  status: string;
  message_id: string;
  parsing_confirmed_by: string;
  parsing_confirmed_at: string;
  correction_count: number;
};

export function confirmParsing(caseId: string, extracted_fields: ParsingConfirmationFields) {
  return apiFetch<ConfirmParsingResult>(`/cases/${caseId}/confirm-parsing`, {
    method: 'POST',
    body: JSON.stringify({ extracted_fields }),
  });
}

export function rejectParsing(caseId: string, reason: string) {
  return apiFetch<{ case_id: string; case_number: string; status: string }>(
    `/cases/${caseId}/reject-parsing`,
    { method: 'POST', body: JSON.stringify({ reason }) }
  );
}

export function overrideGlPeriodPost(
  periodId: string,
  caseId: string,
  overrideReason: string
) {
  return apiFetch<{ case_id: string; period_id: string; message_id: string; status: string }>(
    `/accounting-periods/${periodId}/override-post`,
    {
      method: 'POST',
      body: JSON.stringify({ case_id: caseId, override_reason: overrideReason }),
    }
  );
}

export function exportCasesCsv(dateFrom: string, dateTo: string) {
  const q = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
  return downloadCsv(`/cases/export?${q}`, `transactions_${dateFrom}_${dateTo}.csv`);
}
