import { apiFetch } from './client';

export const TENANT_ID = '00000000-0000-0000-0000-000000000200';

export function fetchDashboard() {
  return apiFetch<{ checks: { section: string; label: string; complete: boolean; href: string }[]; complete_count: number; total_count: number }>('/admin/dashboard');
}

export function fetchTenantProfile() {
  return apiFetch<Record<string, unknown>>(`/tenants/${TENANT_ID}/profile`);
}

export function patchTenantProfile(body: Record<string, unknown>) {
  return apiFetch(`/tenants/${TENANT_ID}/profile`, { method: 'PATCH', body: JSON.stringify(body) });
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

export async function importCoaCsv(file: File) {
  const token = localStorage.getItem('client_admin_access_token');
  const form = new FormData();
  form.append('file', file);
  const res = await fetch('/api/coa/import', {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) throw new Error('Import failed');
  return res.json();
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

export function listRegulatoryDocs() {
  return apiFetch<Array<Record<string, unknown>>>('/regulatory-documents');
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

export function listTravelRequests() {
  return apiFetch<Array<Record<string, unknown>>>('/travel-requests');
}

export function patchTravelRequest(id: string, status: string) {
  return apiFetch(`/travel-requests/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) });
}

export function listAccountingPeriods() {
  return apiFetch<Array<Record<string, unknown>>>('/accounting-periods');
}

export function generateAccountingPeriods(months = 12) {
  return apiFetch<Array<Record<string, unknown>>>(`/accounting-periods/generate?months=${months}`, { method: 'POST' });
}

export function approveTrialBalance(periodId: string) {
  return apiFetch(`/accounting-periods/${periodId}/approve-trial-balance`, { method: 'POST' });
}

export function closeGlPeriod(periodId: string) {
  return apiFetch(`/accounting-periods/${periodId}/close`, { method: 'POST' });
}
