import { apiFetch } from './client';

export type ApprovalItem = {
  id: string;
  case_id: string;
  case_number: string;
  case_type: string;
  tier: number;
  status: string;
  subject?: string;
  amount?: { value: string; currency: string };
  sla_deadline?: string;
  created_at?: string;
  responded_at?: string | null;
  response_note?: string | null;
  binding_escalated_to_cfo?: boolean;
};

export type BindingQueue = 'acc' | 'cfo';

export function listApprovals(opts?: {
  status?: string;
  bindingQueue?: BindingQueue;
  myPending?: boolean;
}) {
  const params = new URLSearchParams();
  if (opts?.status) params.set('status', opts.status);
  if (opts?.bindingQueue) params.set('binding_queue', opts.bindingQueue);
  if (opts?.myPending) params.set('my_pending', 'true');
  const q = params.toString() ? `?${params}` : '';
  return apiFetch<{ data: ApprovalItem[] }>(`/approvals${q}`);
}

export function bindingQueueForRole(roleName: string | null | undefined): BindingQueue | undefined {
  const r = (roleName ?? '').toLowerCase();
  if (r === 'accounts_clerk' || r === 'finance_officer' || r === 'finance_manager') return 'acc';
  if (r === 'cfo' || r === 'finance_director') return 'cfo';
  return undefined;
}

export function getApproval(id: string) {
  return apiFetch<ApprovalItem>(`/approvals/${id}`);
}

export function approve(id: string, note: string) {
  return apiFetch(`/approvals/${id}/approve`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  });
}

export function reject(id: string, reason: string) {
  return apiFetch(`/approvals/${id}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason, rejection_category: 'other' }),
  });
}

export function escalateToCfo(id: string, note?: string) {
  return apiFetch(`/approvals/${id}/escalate`, {
    method: 'POST',
    body: JSON.stringify({ note: note ?? null }),
  });
}
