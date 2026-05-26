import { apiFetch } from './client';

export type DashboardCheck = {
  section: string;
  label: string;
  complete: boolean;
  href: string;
  detail?: string | null;
};

export function fetchDashboard() {
  return apiFetch<{
    checks: DashboardCheck[];
    complete_count: number;
    total_count: number;
  }>('/admin/dashboard');
}

export function fetchTenantProfile() {
  return apiFetch<Record<string, unknown>>('/admin/company-profile');
}

export function patchTenantProfile(body: Record<string, unknown>) {
  const { tenant_id: _tenantId, ...payload } = body;
  return apiFetch<Record<string, unknown>>('/admin/company-profile', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function fetchCoaStatus() {
  return apiFetch<{ account_count: number; empty: boolean }>('/coa/status');
}

export function listCoa(q?: string) {
  const params = q ? `?q=${encodeURIComponent(q)}` : '';
  return apiFetch<Array<Record<string, unknown>>>(`/coa${params}`);
}

export function createCoa(body: Record<string, unknown>) {
  return apiFetch('/coa', { method: 'POST', body: JSON.stringify(body) });
}

export function patchCoa(id: string, body: Record<string, unknown>) {
  return apiFetch(`/coa/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
}

export async function importCoaCsv(file: File, replaceAll = false) {
  const token = localStorage.getItem('client_admin_access_token');
  const form = new FormData();
  form.append('file', file);
  const q = replaceAll ? '?replace_all=true' : '';
  const res = await fetch(`/api/coa/import${q}`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const msg =
      typeof body?.error?.message === 'string'
        ? body.error.message
        : `Import failed (${res.status})`;
    throw new Error(msg);
  }
  return res.json() as Promise<{
    created: number;
    updated: number;
    skipped: number;
    active_count: number;
  }>;
}

export function listMailboxes() {
  return apiFetch<Array<Record<string, unknown>>>('/mail/configuration');
}

export function patchMailbox(id: string, body: Record<string, unknown>) {
  return apiFetch(`/mail/configuration/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
}

export function listRoleUsers() {
  return apiFetch<Array<Record<string, unknown>>>('/users');
}

export function patchUser(id: string, body: Record<string, unknown>) {
  return apiFetch(`/users/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
}

export function getExpenseLimits() {
  return apiFetch<Record<string, string | null>>('/expense-policies/limits');
}

export function patchExpenseLimits(body: Record<string, unknown>) {
  return apiFetch('/expense-policies/limits', { method: 'PATCH', body: JSON.stringify(body) });
}

export function getTravelPolicyDocument() {
  return apiFetch<{
    uploaded: boolean;
    filename?: string;
    file_size?: number;
    uploaded_at?: string;
    download_url?: string;
  }>('/expense-policies/document');
}

export async function uploadTravelPolicyPdf(file: File) {
  return uploadPdf('/api/expense-policies/document', file);
}

export function listRegulatoryCatalog() {
  return apiFetch<
    Array<{
      document_key: string;
      label: string;
      uploaded: boolean;
      id?: string;
      filename?: string;
      file_size?: number;
      uploaded_at?: string;
      download_url?: string;
    }>
  >('/regulatory-documents/catalog');
}

export async function uploadRegulatoryPdf(documentKey: string, file: File) {
  return uploadPdf(`/api/regulatory-documents?document_key=${encodeURIComponent(documentKey)}`, file);
}

async function uploadPdf(url: string, file: File) {
  const token = localStorage.getItem('client_admin_access_token');
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(url, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { message?: string }).message || 'Upload failed');
  }
  return res.json();
}

export async function downloadAuthenticated(url: string, filename: string) {
  const token = localStorage.getItem('client_admin_access_token');
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error('Download failed');
  const blob = await res.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

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
  return apiFetch<Array<Record<string, unknown>>>('/accounting-periods');
}

export function generateAccountingPeriods(months = 13) {
  return apiFetch<Array<Record<string, unknown>>>(
    `/accounting-periods/generate?months=${months}`,
    { method: 'POST' }
  );
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
