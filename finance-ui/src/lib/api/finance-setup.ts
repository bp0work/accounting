import { apiFetch } from './client';

export function listRentalAgreements() {
  return apiFetch<Array<Record<string, unknown>>>('/agreements/rental');
}

export function createRentalAgreement(body: Record<string, unknown>) {
  return apiFetch('/agreements/rental', { method: 'POST', body: JSON.stringify(body) });
}

export function listDirectorAgreements() {
  return apiFetch<Array<Record<string, unknown>>>('/agreements/director-expense');
}

export function createDirectorAgreement(body: Record<string, unknown>) {
  return apiFetch('/agreements/director-expense', { method: 'POST', body: JSON.stringify(body) });
}

export type AccountingSettings = {
  accounting_fye_month: number;
  trial_balance_frequency: string;
  audit_frequency: string;
  gl_cutoff_working_days: number;
};

export function getAccountingSettings() {
  return apiFetch<AccountingSettings>('/admin/accounting-settings');
}

export function patchAccountingSettings(body: Partial<AccountingSettings>) {
  return apiFetch<AccountingSettings>('/admin/accounting-settings', {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export type GlCutoffReminder = {
  id: string;
  tenant_id: string;
  email: string;
  display_name?: string;
  notify_7_days: boolean;
  notify_3_days: boolean;
  notify_1_day: boolean;
  notify_on_date: boolean;
  is_active: boolean;
};

export function listGlCutoffReminders() {
  return apiFetch<GlCutoffReminder[]>('/admin/gl-cutoff-reminders');
}

export function createGlCutoffReminder(body: Record<string, unknown>) {
  return apiFetch<GlCutoffReminder>('/admin/gl-cutoff-reminders', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function patchGlCutoffReminder(id: string, body: Record<string, unknown>) {
  return apiFetch<GlCutoffReminder>(`/admin/gl-cutoff-reminders/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export function deleteGlCutoffReminder(id: string) {
  return apiFetch<void>(`/admin/gl-cutoff-reminders/${id}`, { method: 'DELETE' });
}

export function listAccountingPeriods() {
  return apiFetch<Array<Record<string, unknown>>>('/accounting-periods?include_historical=true');
}

export function generateAccountingPeriods(months = 13) {
  return apiFetch<Array<Record<string, unknown>>>(
    `/accounting-periods/generate?months=${months}`,
    { method: 'POST' }
  );
}

export function submitTrialBalanceReview(periodId: string) {
  return apiFetch(`/accounting-periods/${periodId}/submit-trial-balance-review`, {
    method: 'POST',
  });
}

export function approveTrialBalance(periodId: string) {
  return apiFetch(`/accounting-periods/${periodId}/approve-trial-balance`, { method: 'POST' });
}

export function closeGlPeriod(
  periodId: string,
  body?: {
    audit_adjustments_completed?: boolean;
    year_end_adjustments_completed?: boolean;
    auditor_name?: string;
    auditor_firm?: string;
    sign_off_date?: string;
  }
) {
  return apiFetch(`/accounting-periods/${periodId}/close`, {
    method: 'POST',
    body: body ? JSON.stringify(body) : undefined,
  });
}

export function reopenGlPeriod(periodId: string) {
  return apiFetch(`/accounting-periods/${periodId}/reopen`, { method: 'POST' });
}

export function listCounterparties(type?: string, q?: string) {
  const params = new URLSearchParams();
  if (type) params.set('type', type);
  if (q) params.set('q', q);
  const qs = params.toString();
  return apiFetch<Array<Record<string, unknown>>>(`/counterparties${qs ? `?${qs}` : ''}`);
}

export function createCounterparty(body: Record<string, unknown>) {
  return apiFetch('/counterparties', { method: 'POST', body: JSON.stringify(body) });
}

export function patchCounterparty(id: string, body: Record<string, unknown>) {
  return apiFetch(`/counterparties/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
}

export function listCounterpartyAccounts(counterpartyId?: string, q?: string) {
  const params = new URLSearchParams();
  if (counterpartyId) params.set('counterparty_id', counterpartyId);
  if (q) params.set('q', q);
  const qs = params.toString();
  return apiFetch<Array<Record<string, unknown>>>(`/counterparty-accounts${qs ? `?${qs}` : ''}`);
}

export function createCounterpartyAccount(body: Record<string, unknown>) {
  return apiFetch('/counterparty-accounts', { method: 'POST', body: JSON.stringify(body) });
}

export function patchCounterpartyAccount(id: string, body: Record<string, unknown>) {
  return apiFetch(`/counterparty-accounts/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
}

export function listPaymentTerms() {
  return apiFetch<Array<Record<string, unknown>>>('/payment-terms');
}

export function createPaymentTerm(body: Record<string, unknown>) {
  return apiFetch('/payment-terms', { method: 'POST', body: JSON.stringify(body) });
}

export function listTaxCodes() {
  return apiFetch<Array<Record<string, unknown>>>('/tenant/tax-codes');
}

export function createTaxCode(body: Record<string, unknown>) {
  return apiFetch('/tenant/tax-codes', { method: 'POST', body: JSON.stringify(body) });
}
