import { apiFetch } from './client';

export type GatewayPerformance = {
  emails_today: number;
  emails_this_week: number;
  avg_processing_seconds: number;
  last_poll_at: string | null;
};

export type WorkerPerformance = {
  cases_today: number;
  cases_this_week: number;
  avg_processing_seconds: number;
  success_rate: number;
  queue_depth: number;
  last_activity_at: string | null;
  pending_confirmation?: number | null;
  pending_approval?: number | null;
};

export type DashboardStats = {
  agent_performance: {
    gateway: GatewayPerformance;
    accounts_worker: WorkerPerformance;
    expense_worker: WorkerPerformance;
    ap_worker: WorkerPerformance;
    ar_worker: WorkerPerformance;
  };
  cases_by_status: Record<string, number>;
  queue_depths: {
    accounts_queue: number;
    intake_queue: number;
  };
  period: {
    today_start: string;
    week_start: string;
  };
};

export function fetchDashboardStats() {
  return apiFetch<DashboardStats>('/dashboard/stats');
}
