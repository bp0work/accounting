<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { fetchDashboardStats, type DashboardStats, type WorkerPerformance } from '$lib/api/dashboard';
  import { listCases, type CaseItem } from '$lib/api/cases';
  import {
    caseActionByLabel,
    caseStateColumnLabel,
    documentTypeLabel,
    submittedByDisplay,
  } from '$lib/case-labels';
  import {
    dashboardStatusLabel,
    recentCasesAllowedStatuses,
    visibleStatusesForRole,
  } from '$lib/dashboard-roles';
  import { formatAmount, formatCount } from '$lib/format';
  import { subscribeFinanceEvents } from '$lib/sse-client';
  import { sessionUser } from '$lib/stores/session';

  let stats: DashboardStats | null = null;
  let recentCases: CaseItem[] = [];
  let activeStatusFilter: string | null = null;
  let error = '';
  let loading = true;
  let lastUpdatedAt: Date | null = null;
  let secondsSinceUpdate = 0;
  let tickTimer: ReturnType<typeof setInterval> | null = null;
  let statsTimer: ReturnType<typeof setInterval> | null = null;
  let casesTimer: ReturnType<typeof setInterval> | null = null;
  let unsubscribeSse: (() => void) | null = null;

  $: role = ($sessionUser?.role_name ?? '').toLowerCase();
  $: visibleStatuses = visibleStatusesForRole(role);
  $: allowedRecent = recentCasesAllowedStatuses(role);

  function documentNumber(item: CaseItem): string {
    const raw = item.workflow_metadata?.extracted_fields;
    if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
      const num = (raw as Record<string, unknown>).document_number;
      if (num != null && String(num).trim()) return String(num);
    }
    return '—';
  }

  function formatDuration(seconds: number): string {
    if (!Number.isFinite(seconds) || seconds <= 0) return '—';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
  }

  function formatRelativeTime(iso: string | null | undefined): string {
    if (!iso) return '—';
    const then = new Date(iso).getTime();
    const diffSec = Math.max(0, Math.floor((Date.now() - then) / 1000));
    if (diffSec < 60) return `${diffSec}s ago`;
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)} min ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} h ago`;
    return new Date(iso).toLocaleString();
  }

  type AgentState = 'active' | 'idle' | 'stalled';

  function workerAgentState(worker: WorkerPerformance): AgentState {
    const lastMs = worker.last_activity_at ? new Date(worker.last_activity_at).getTime() : 0;
    const ageMin = lastMs ? (Date.now() - lastMs) / 60000 : Infinity;
    if (worker.queue_depth > 0 && ageMin > 10) return 'stalled';
    if (worker.queue_depth > 0 || ageMin <= 5) return 'active';
    return 'idle';
  }

  function gatewayAgentState(lastPoll: string | null | undefined): AgentState {
    if (!lastPoll) return 'idle';
    const ageMin = (Date.now() - new Date(lastPoll).getTime()) / 60000;
    if (ageMin <= 5) return 'active';
    if (ageMin > 10) return 'stalled';
    return 'idle';
  }

  function agentStateLabel(state: AgentState): string {
    if (state === 'active') return 'Active';
    if (state === 'stalled') return 'Stalled';
    return 'Idle';
  }

  function toggleStatusFilter(status: string) {
    activeStatusFilter = activeStatusFilter === status ? null : status;
    void loadRecentCases();
  }

  function pillCount(status: string): number {
    if (!stats) return 0;
    if (activeStatusFilter && activeStatusFilter !== status) {
      return stats.cases_by_status[status] ?? 0;
    }
    return stats.cases_by_status[status] ?? 0;
  }

  async function loadStats() {
    try {
      stats = await fetchDashboardStats();
      lastUpdatedAt = new Date();
      secondsSinceUpdate = 0;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load dashboard stats';
    }
  }

  async function loadRecentCases() {
    try {
      if (activeStatusFilter) {
        const res = await listCases(500, activeStatusFilter);
        recentCases = res.data;
      } else {
        const res = await listCases(50);
        let rows = res.data;
        if (allowedRecent) {
          rows = rows.filter((c) => allowedRecent.has(c.status));
        }
        recentCases = rows;
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load cases';
    }
  }

  async function refreshAll() {
    await Promise.all([loadStats(), loadRecentCases()]);
    loading = false;
  }

  onMount(() => {
    void refreshAll();

    statsTimer = setInterval(() => {
      void loadStats();
    }, 60_000);

    casesTimer = setInterval(() => {
      void loadRecentCases();
    }, 30_000);

    tickTimer = setInterval(() => {
      if (lastUpdatedAt) {
        secondsSinceUpdate = Math.floor((Date.now() - lastUpdatedAt.getTime()) / 1000);
      }
    }, 1000);

    unsubscribeSse = subscribeFinanceEvents((eventType) => {
      if (eventType === 'case.status_changed' || eventType === 'message') {
        void refreshAll();
      }
    });
  });

  onDestroy(() => {
    if (statsTimer) clearInterval(statsTimer);
    if (casesTimer) clearInterval(casesTimer);
    if (tickTimer) clearInterval(tickTimer);
    unsubscribeSse?.();
  });
</script>

<h1>Operations dashboard</h1>
<p class="subtitle">
  Agent performance, case status overview, and recent activity.
  {#if lastUpdatedAt}
    <span class="updated">Last updated: {secondsSinceUpdate}s ago</span>
  {/if}
</p>

{#if error}<p class="error">{error}</p>{/if}

{#if stats}
  <section class="section">
    <h2>Agent performance</h2>
    <div class="agent-row">
      <article class="agent-card">
        <h3>Gateway</h3>
        <dl class="metrics">
          <div><dt>Emails today</dt><dd>{formatCount(stats.agent_performance.gateway.emails_today)}</dd></div>
          <div><dt>This week</dt><dd>{formatCount(stats.agent_performance.gateway.emails_this_week)}</dd></div>
          <div><dt>Avg processing</dt><dd>{formatDuration(stats.agent_performance.gateway.avg_processing_seconds)}</dd></div>
          <div><dt>Last poll</dt><dd>{formatRelativeTime(stats.agent_performance.gateway.last_poll_at)}</dd></div>
        </dl>
        <p class="status-line">
          <span class="dot {gatewayAgentState(stats.agent_performance.gateway.last_poll_at)}"></span>
          {agentStateLabel(gatewayAgentState(stats.agent_performance.gateway.last_poll_at))}
        </p>
      </article>

      <article class="agent-card">
        <h3>Accounts Worker</h3>
        <dl class="metrics">
          <div><dt>Cases today</dt><dd>{formatCount(stats.agent_performance.accounts_worker.cases_today)}</dd></div>
          <div><dt>This week</dt><dd>{formatCount(stats.agent_performance.accounts_worker.cases_this_week)}</dd></div>
          <div><dt>Avg time</dt><dd>{formatDuration(stats.agent_performance.accounts_worker.avg_processing_seconds)}</dd></div>
          <div><dt>Success rate</dt><dd>{Math.round(stats.agent_performance.accounts_worker.success_rate * 100)}%</dd></div>
          <div><dt>Queue</dt><dd>{formatCount(stats.agent_performance.accounts_worker.queue_depth)}</dd></div>
        </dl>
        <p class="status-line">
          <span class="dot {workerAgentState(stats.agent_performance.accounts_worker)}"></span>
          {agentStateLabel(workerAgentState(stats.agent_performance.accounts_worker))}
        </p>
      </article>

      <article class="agent-card">
        <h3>Expense Worker</h3>
        <dl class="metrics">
          <div><dt>Cases today</dt><dd>{formatCount(stats.agent_performance.expense_worker.cases_today)}</dd></div>
          <div><dt>This week</dt><dd>{formatCount(stats.agent_performance.expense_worker.cases_this_week)}</dd></div>
          <div><dt>Avg time</dt><dd>{formatDuration(stats.agent_performance.expense_worker.avg_processing_seconds)}</dd></div>
          <div><dt>Success rate</dt><dd>{Math.round(stats.agent_performance.expense_worker.success_rate * 100)}%</dd></div>
          <div><dt>Queue</dt><dd>{formatCount(stats.agent_performance.expense_worker.queue_depth)}</dd></div>
          <div><dt>Pending confirmation</dt><dd>{formatCount(stats.agent_performance.expense_worker.pending_confirmation ?? 0)}</dd></div>
          <div><dt>Pending approval</dt><dd>{formatCount(stats.agent_performance.expense_worker.pending_approval ?? 0)}</dd></div>
        </dl>
        <p class="status-line">
          <span class="dot {workerAgentState(stats.agent_performance.expense_worker)}"></span>
          {agentStateLabel(workerAgentState(stats.agent_performance.expense_worker))}
        </p>
      </article>

      <article class="agent-card">
        <h3>AP Worker</h3>
        <dl class="metrics">
          <div><dt>Cases today</dt><dd>{formatCount(stats.agent_performance.ap_worker.cases_today)}</dd></div>
          <div><dt>This week</dt><dd>{formatCount(stats.agent_performance.ap_worker.cases_this_week)}</dd></div>
          <div><dt>Avg time</dt><dd>{formatDuration(stats.agent_performance.ap_worker.avg_processing_seconds)}</dd></div>
          <div><dt>Success rate</dt><dd>{Math.round(stats.agent_performance.ap_worker.success_rate * 100)}%</dd></div>
          <div><dt>Queue</dt><dd>{formatCount(stats.agent_performance.ap_worker.queue_depth)}</dd></div>
        </dl>
        <p class="status-line">
          <span class="dot {workerAgentState(stats.agent_performance.ap_worker)}"></span>
          {agentStateLabel(workerAgentState(stats.agent_performance.ap_worker))}
        </p>
      </article>

      <article class="agent-card">
        <h3>AR Worker</h3>
        <dl class="metrics">
          <div><dt>Cases today</dt><dd>{formatCount(stats.agent_performance.ar_worker.cases_today)}</dd></div>
          <div><dt>This week</dt><dd>{formatCount(stats.agent_performance.ar_worker.cases_this_week)}</dd></div>
          <div><dt>Avg time</dt><dd>{formatDuration(stats.agent_performance.ar_worker.avg_processing_seconds)}</dd></div>
          <div><dt>Success rate</dt><dd>{Math.round(stats.agent_performance.ar_worker.success_rate * 100)}%</dd></div>
          <div><dt>Queue</dt><dd>{formatCount(stats.agent_performance.ar_worker.queue_depth)}</dd></div>
        </dl>
        <p class="status-line">
          <span class="dot {workerAgentState(stats.agent_performance.ar_worker)}"></span>
          {agentStateLabel(workerAgentState(stats.agent_performance.ar_worker))}
        </p>
      </article>
    </div>
  </section>

  <section class="section">
    <h2>Cases by status</h2>
    <div class="status-pills">
      {#each visibleStatuses as status (status)}
        {@const count = pillCount(status)}
        <button
          type="button"
          class="pill"
          class:active={activeStatusFilter === status}
          class:zero={count === 0}
          onclick={() => toggleStatusFilter(status)}
        >
          {dashboardStatusLabel(status)}: {formatCount(count)}
        </button>
      {/each}
    </div>
  </section>

  <section class="section">
    <h2>
      Recent cases
      {#if activeStatusFilter}
        <span class="filter-tag">— {dashboardStatusLabel(activeStatusFilter)}</span>
      {/if}
    </h2>
    {#if loading}
      <p class="hint">Loading…</p>
    {:else if recentCases.length === 0}
      <p class="hint">No cases match the current filter.</p>
    {:else}
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Case Number</th>
              <th>Submitted By</th>
              <th>Type</th>
              <th>Status</th>
              <th>Document Number</th>
              <th>Amount</th>
              <th>Date Submitted</th>
              <th>Action by</th>
            </tr>
          </thead>
          <tbody>
            {#each recentCases as c (c.id)}
              <tr>
                <td><a href={`/cases/${c.id}`}>{c.case_number}</a></td>
                <td>{submittedByDisplay(c)}</td>
                <td>{documentTypeLabel(c.type)}</td>
                <td>{caseStateColumnLabel(c)}</td>
                <td>{documentNumber(c)}</td>
                <td>
                  {#if c.amount_value != null}
                    {formatAmount(Number(c.amount_value))} {c.amount_currency}
                  {:else}
                    —
                  {/if}
                </td>
                <td>{new Date(c.created_at).toLocaleString()}</td>
                <td>{caseActionByLabel(c)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </section>
{/if}

<style>
  .subtitle {
    color: #64748b;
    margin-top: 0;
  }
  .updated {
    margin-left: 0.5rem;
    font-size: 0.875rem;
  }
  .error {
    color: #b91c1c;
  }
  .section {
    margin-bottom: 1.5rem;
  }
  .section h2 {
    margin-bottom: 0.75rem;
    font-size: 1.1rem;
  }
  .filter-tag {
    font-weight: 500;
    color: #475569;
    font-size: 0.95rem;
  }
  .agent-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
  }
  .agent-card {
    border: 1px solid #e2e8f0;
    border-radius: 0.5rem;
    padding: 1rem;
    background: #fff;
  }
  .agent-card h3 {
    margin: 0 0 0.75rem;
    font-size: 1rem;
  }
  .metrics {
    margin: 0;
    display: grid;
    gap: 0.35rem;
    font-size: 0.875rem;
  }
  .metrics div {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
  }
  .metrics dt {
    color: #64748b;
    margin: 0;
  }
  .metrics dd {
    margin: 0;
    font-weight: 600;
    text-align: right;
  }
  .status-line {
    margin: 0.75rem 0 0;
    font-size: 0.8125rem;
    color: #475569;
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }
  .dot {
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 50%;
    display: inline-block;
  }
  .dot.active {
    background: #16a34a;
  }
  .dot.idle {
    background: #94a3b8;
  }
  .dot.stalled {
    background: #ea580c;
  }
  .status-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  .pill {
    border: 1px solid #cbd5e1;
    background: #f8fafc;
    border-radius: 999px;
    padding: 0.35rem 0.75rem;
    font: inherit;
    font-size: 0.8125rem;
    cursor: pointer;
  }
  .pill:hover {
    background: #f1f5f9;
  }
  .pill.active {
    background: #dbeafe;
    border-color: #3b82f6;
    color: #1d4ed8;
    font-weight: 600;
  }
  .pill.zero {
    opacity: 0.55;
  }
  .hint {
    color: #64748b;
  }
  .table-wrap {
    overflow-x: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }
  th,
  td {
    text-align: left;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid #e2e8f0;
    white-space: nowrap;
  }
  a {
    color: #1d4ed8;
    text-decoration: none;
  }
  a:hover {
    text-decoration: underline;
  }
</style>
