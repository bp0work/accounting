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

export type MailboxConfig = {
  id: string;
  email_address: string;
  display_name: string | null;
  role: string | null;
  mailbox_mode: string;
  escalation_manager_email: string | null;
  is_active: boolean;
  username_masked?: string | null;
  server_host?: string | null;
};

export type MailboxConfigUpdate = {
  display_name?: string | null;
  escalation_manager_email?: string | null;
};

export function listMailboxes(): Promise<MailboxConfig[]> {
  return apiFetch<MailboxConfig[]>('/mail/configuration');
}

export function patchMailbox(id: string, body: MailboxConfigUpdate): Promise<MailboxConfig> {
  return apiFetch<MailboxConfig>(`/mail/configuration/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export function listRoleUsers() {
  return apiFetch<Array<Record<string, unknown>>>('/users');
}

export function patchUser(id: string, body: Record<string, unknown>) {
  return apiFetch(`/users/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
}

export function upsertRoleUser(roleName: string, body: Record<string, unknown>) {
  return apiFetch<Record<string, unknown>>(`/users/by-role/${encodeURIComponent(roleName)}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });
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

export type BindingAuthorityThresholds = {
  tier_1_ceiling: number;
  tier_2_ceiling: number;
  tier_3_threshold: number;
  stp_confidence_minimum: number;
  tier_2_sla_hours: number;
  tier_3_sla_hours: number;
};

export type BindingAuthorityDocument = {
  document_key: string;
  label: string;
  thresholds: BindingAuthorityThresholds;
};

export type BindingAuthorityConfig = {
  ap_invoice: BindingAuthorityDocument;
  ar_invoice: BindingAuthorityDocument;
  expense_claim: BindingAuthorityDocument;
};

export function getBindingAuthority() {
  return apiFetch<BindingAuthorityConfig>('/admin/binding-authority');
}

export function patchBindingAuthority(body: {
  ap_approval_thresholds?: Partial<BindingAuthorityThresholds>;
  ar_approval_thresholds?: Partial<BindingAuthorityThresholds>;
  expense_approval_thresholds?: Partial<BindingAuthorityThresholds>;
}) {
  return apiFetch<BindingAuthorityConfig>('/admin/binding-authority', {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
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

export type AccountingSettings = {
  accounting_fye_month: number;
  trial_balance_frequency: string;
  audit_frequency: string;
  gl_cutoff_working_days: number;
  accounting_start_date: string | null;
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

export function generateAccountingPeriods(body?: {
  months_forward?: number;
  start_month?: string;
}) {
  const params = new URLSearchParams();
  if (body?.months_forward != null) params.set('months_forward', String(body.months_forward));
  if (body?.start_month) params.set('start_month', body.start_month);
  const qs = params.toString();
  return apiFetch<Array<Record<string, unknown>>>(
    `/accounting-periods/generate${qs ? `?${qs}` : ''}`,
    { method: 'POST' }
  );
}

export type GlCutoffReminder = {
  id: string;
  tenant_id: string;
  email: string;
  display_name?: string | null;
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

