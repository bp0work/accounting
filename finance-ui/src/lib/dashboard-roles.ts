/** Dashboard status filters and role visibility — `0.15.09-dashboard-redesign`. */

export const DASHBOARD_STATUS_ORDER = [
  'pending_confirmation',
  'pending_approval',
  'on_hold',
  'manual_review',
  'posted',
  'rejected',
  'case_rejected',
  'reversed',
  'classified',
  'processing',
] as const;

export type DashboardStatusFilter = (typeof DASHBOARD_STATUS_ORDER)[number];

const STATUS_LABELS: Record<string, string> = {
  pending_confirmation: 'Pending Confirmation',
  pending_approval: 'Pending Approval',
  on_hold: 'On Hold',
  manual_review: 'Manual Review',
  posted: 'Posted',
  rejected: 'Rejected',
  case_rejected: 'Case Rejected',
  reversed: 'Reversed',
  classified: 'Classified',
  processing: 'Processing',
};

export function dashboardStatusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status.replace(/_/g, ' ');
}

export function visibleStatusesForRole(roleName: string | null | undefined): string[] {
  const role = (roleName ?? '').toLowerCase();
  if (role === 'finance_manager') {
    return ['posted', 'reversed', 'on_hold'];
  }
  return [...DASHBOARD_STATUS_ORDER];
}

export function recentCasesAllowedStatuses(roleName: string | null | undefined): Set<string> | null {
  const role = (roleName ?? '').toLowerCase();
  if (role === 'finance_manager') {
    return new Set(['posted', 'reversed']);
  }
  return null;
}
