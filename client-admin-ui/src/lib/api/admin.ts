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

