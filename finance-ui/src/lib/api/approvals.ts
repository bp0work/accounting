import { apiFetch } from './client';

export type ApprovalItem = {
  id: string;
  case_number: string;
  case_type: string;
  status: string;
  subject?: string;
  amount?: { value: string; currency: string };
  sla_deadline?: string;
};

export function listApprovals(myPending = true) {
  const q = myPending ? '?my_pending=true' : '';
  return apiFetch<{ data: ApprovalItem[] }>(`/approvals${q}`);
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
