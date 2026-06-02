<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import {
    fetchDashboardStats,
    type DashboardStats,
    type WorkerKpi,
    type WorkerPerformance,
  } from '$lib/api/dashboard';
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
  import { sessionUser } from '$lib/stores/session';

  let stats: DashboardStats | null = null;
  let recentCases: CaseItem[] = [];
  let activeStatusFilter: string | null = null;
  let error = '';
  let loading = true;
  let countdown = 60;
  let tickTimer: ReturnType<typeof setInterval> | null = null;
  let statsTimer: ReturnType<typeof setInterval> | null = null;
  let casesTimer: ReturnType<typeof setInterval> | null = null;
  let onCaseStatusChanged: ((event: Event) => void) | null = null;
  let arKpiExpanded = false;
  let apKpiExpanded = false;
  let expenseKpiExpanded = false;

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

  type WorkerKpiRow = { key: string; label: string };
  const KPI_PERIOD_KEYS: Array<'30d' | '60d' | '90d'> = ['30d', '60d', '90d'];
  const EXPENSE_KPI_ROWS: WorkerKpiRow[] = [
    { key: 'unable_to_parse', label: 'Unable to parse' },
    { key: 'duplicate_document', label: 'Duplicate document' },
    { key: 'counterparty_not_found', label: 'Counterparty not found (Employee)' },
    { key: 'document_not_validated', label: 'Document not validated' },
    { key: 'exchange_rate_issue', label: 'Exchange rate issue' },
    { key: 'policy_exceeded', label: 'Policy exceeded / Receipt invalid' },
    { key: 'missing_travel_requisition', label: 'Missing travel requisition' },
    { key: 'out_of_period', label: 'Out of period' },
    { key: 'coa_mapping', label: 'COA mapping' },
    { key: 'journal_entry', label: 'Journal entry' },
  ];
  const AP_KPI_ROWS: WorkerKpiRow[] = [
    { key: 'unable_to_parse', label: 'Unable to parse' },
    { key: 'duplicate_document', label: 'Duplicate document' },
    { key: 'counterparty_not_found', label: 'Counterparty not found (Vendor)' },
    { key: 'document_not_validated', label: 'Document not validated' },
    { key: 'exchange_rate_issue', label: 'Exchange rate issue' },
    { key: 'missing_supporting_doc', label: 'Missing supporting doc (PO/Contract/GRN/DO)' },
    { key: 'out_of_period', label: 'Out of period' },
    { key: 'coa_mapping', label: 'COA mapping' },
    { key: 'journal_entry', label: 'Journal entry' },
  ];
  const AR_KPI_ROWS: WorkerKpiRow[] = [
    { key: 'unable_to_parse', label: 'Unable to parse' },
    { key: 'duplicate_document', label: 'Duplicate document' },
    { key: 'counterparty_not_found', label: 'Counterparty not found (Customer)' },
    { key: 'credit_term_exposure', label: 'Credit term / Exposure issue' },
    { key: 'exchange_rate_issue', label: 'Exchange rate issue' },
    { key: 'out_of_period', label: 'Out of period' },
    { key: 'coa_mapping', label: 'COA mapping' },
    { key: 'journal_entry', label: 'Journal entry' },
  ];

  function statValue(kpi: WorkerKpi | null | undefined, key: string, period: '30d' | '60d' | '90d') {
    const stat = kpi?.[period]?.interventions?.[key];
    return `${formatCount(stat?.count ?? 0)} / ${(stat?.pct ?? 0).toFixed(1)}%`;
  }

  function totalCases(kpi: WorkerKpi | null | undefined, period: '30d' | '60d' | '90d') {
    return formatCount(kpi?.[period]?.total_cases ?? 0);
  }

  function totalInterventionClass(kpi: WorkerKpi | null | undefined): string {
    const pct = kpi?.['30d']?.interventions?.total_interventions?.pct ?? 0;
    if (pct > 30) return 'kpi-total-red';
    if (pct >= 15) return 'kpi-total-amber';
    return 'kpi-total-green';
  }

  function isZeroRow(kpi: WorkerKpi | null | undefined, key: string): boolean {
    return KPI_PERIOD_KEYS.every((period) => (kpi?.[period]?.interventions?.[key]?.count ?? 0) === 0);
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
      countdown = 60;
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
      countdown = Math.max(0, countdown - 1);
    }, 1000);

    onCaseStatusChanged = () => {
      void refreshAll();
    };
    window.addEventListener('finance:case-status-changed', onCaseStatusChanged);
  });

  onDestroy(() => {
    if (statsTimer) clearInterval(statsTimer);
    if (casesTimer) clearInterval(casesTimer);
    if (tickTimer) clearInterval(tickTimer);
    if (onCaseStatusChanged) {
      window.removeEventListener('finance:case-status-changed', onCaseStatusChanged);
    }
  });
</script>

<h1>Operations dashboard</h1>
<p class="subtitle">
  <span class="updated">Next update in: {countdown}s</span>
</p>

{#if error}<p class="error">{error}</p>{/if}

{#if stats}
  <section class="section">
    <h2>Agent performance</h2>
    <div class="agent-row row-2">
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
    </div>

    <div class="agent-row row-3">
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
        <button type="button" class="kpi-toggle" onclick={() => (arKpiExpanded = !arKpiExpanded)}>
          KPIs {arKpiExpanded ? '▴' : '▾'}
        </button>
        {#if arKpiExpanded}
          <div class="kpi-block">
            <table class="kpi-table">
              <thead>
                <tr><th>Cases processed</th><th>30d</th><th>60d</th><th>90d</th></tr>
              </thead>
              <tbody>
                <tr>
                  <td></td>
                  <td>{totalCases(stats.agent_performance.ar_worker.kpi, '30d')}</td>
                  <td>{totalCases(stats.agent_performance.ar_worker.kpi, '60d')}</td>
                  <td>{totalCases(stats.agent_performance.ar_worker.kpi, '90d')}</td>
                </tr>
              </tbody>
            </table>
            <table class="kpi-table">
              <thead>
                <tr><th>Intervention</th><th>30d</th><th>60d</th><th>90d</th></tr>
              </thead>
              <tbody>
                {#each AR_KPI_ROWS as row}
                  <tr class:muted={isZeroRow(stats.agent_performance.ar_worker.kpi, row.key)}>
                    <td>{row.label}</td>
                    <td>{statValue(stats.agent_performance.ar_worker.kpi, row.key, '30d')}</td>
                    <td>{statValue(stats.agent_performance.ar_worker.kpi, row.key, '60d')}</td>
                    <td>{statValue(stats.agent_performance.ar_worker.kpi, row.key, '90d')}</td>
                  </tr>
                {/each}
                <tr class={`kpi-total ${totalInterventionClass(stats.agent_performance.ar_worker.kpi)}`}>
                  <td>Total interventions</td>
                  <td>{statValue(stats.agent_performance.ar_worker.kpi, 'total_interventions', '30d')}</td>
                  <td>{statValue(stats.agent_performance.ar_worker.kpi, 'total_interventions', '60d')}</td>
                  <td>{statValue(stats.agent_performance.ar_worker.kpi, 'total_interventions', '90d')}</td>
                </tr>
              </tbody>
            </table>
          </div>
        {/if}
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
        <button type="button" class="kpi-toggle" onclick={() => (apKpiExpanded = !apKpiExpanded)}>
          KPIs {apKpiExpanded ? '▴' : '▾'}
        </button>
        {#if apKpiExpanded}
          <div class="kpi-block">
            <table class="kpi-table">
              <thead>
                <tr><th>Cases processed</th><th>30d</th><th>60d</th><th>90d</th></tr>
              </thead>
              <tbody>
                <tr>
                  <td></td>
                  <td>{totalCases(stats.agent_performance.ap_worker.kpi, '30d')}</td>
                  <td>{totalCases(stats.agent_performance.ap_worker.kpi, '60d')}</td>
                  <td>{totalCases(stats.agent_performance.ap_worker.kpi, '90d')}</td>
                </tr>
              </tbody>
            </table>
            <table class="kpi-table">
              <thead>
                <tr><th>Intervention</th><th>30d</th><th>60d</th><th>90d</th></tr>
              </thead>
              <tbody>
                {#each AP_KPI_ROWS as row}
                  <tr class:muted={isZeroRow(stats.agent_performance.ap_worker.kpi, row.key)}>
                    <td>{row.label}</td>
                    <td>{statValue(stats.agent_performance.ap_worker.kpi, row.key, '30d')}</td>
                    <td>{statValue(stats.agent_performance.ap_worker.kpi, row.key, '60d')}</td>
                    <td>{statValue(stats.agent_performance.ap_worker.kpi, row.key, '90d')}</td>
                  </tr>
                {/each}
                <tr class={`kpi-total ${totalInterventionClass(stats.agent_performance.ap_worker.kpi)}`}>
                  <td>Total interventions</td>
                  <td>{statValue(stats.agent_performance.ap_worker.kpi, 'total_interventions', '30d')}</td>
                  <td>{statValue(stats.agent_performance.ap_worker.kpi, 'total_interventions', '60d')}</td>
                  <td>{statValue(stats.agent_performance.ap_worker.kpi, 'total_interventions', '90d')}</td>
                </tr>
              </tbody>
            </table>
          </div>
        {/if}
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
        <button
          type="button"
          class="kpi-toggle"
          onclick={() => (expenseKpiExpanded = !expenseKpiExpanded)}
        >
          KPIs {expenseKpiExpanded ? '▴' : '▾'}
        </button>
        {#if expenseKpiExpanded}
          <div class="kpi-block">
            <table class="kpi-table">
              <thead>
                <tr><th>Cases processed</th><th>30d</th><th>60d</th><th>90d</th></tr>
              </thead>
              <tbody>
                <tr>
                  <td></td>
                  <td>{totalCases(stats.agent_performance.expense_worker.kpi, '30d')}</td>
                  <td>{totalCases(stats.agent_performance.expense_worker.kpi, '60d')}</td>
                  <td>{totalCases(stats.agent_performance.expense_worker.kpi, '90d')}</td>
                </tr>
              </tbody>
            </table>
            <table class="kpi-table">
              <thead>
                <tr><th>Intervention</th><th>30d</th><th>60d</th><th>90d</th></tr>
              </thead>
              <tbody>
                {#each EXPENSE_KPI_ROWS as row}
                  <tr class:muted={isZeroRow(stats.agent_performance.expense_worker.kpi, row.key)}>
                    <td>{row.label}</td>
                    <td>{statValue(stats.agent_performance.expense_worker.kpi, row.key, '30d')}</td>
                    <td>{statValue(stats.agent_performance.expense_worker.kpi, row.key, '60d')}</td>
                    <td>{statValue(stats.agent_performance.expense_worker.kpi, row.key, '90d')}</td>
                  </tr>
                {/each}
                <tr class={`kpi-total ${totalInterventionClass(stats.agent_performance.expense_worker.kpi)}`}>
                  <td>Total interventions</td>
                  <td>{statValue(stats.agent_performance.expense_worker.kpi, 'total_interventions', '30d')}</td>
                  <td>{statValue(stats.agent_performance.expense_worker.kpi, 'total_interventions', '60d')}</td>
                  <td>{statValue(stats.agent_performance.expense_worker.kpi, 'total_interventions', '90d')}</td>
                </tr>
              </tbody>
            </table>
          </div>
        {/if}
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
    gap: 1rem;
    margin-bottom: 1rem;
  }
  .agent-row.row-2 {
    grid-template-columns: repeat(2, minmax(260px, 1fr));
  }
  .agent-row.row-3 {
    grid-template-columns: repeat(3, minmax(220px, 1fr));
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
  .kpi-toggle {
    margin-top: 0.75rem;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    background: #f8fafc;
    padding: 0.3rem 0.6rem;
    font-size: 0.8rem;
    cursor: pointer;
  }
  .kpi-block {
    margin-top: 0.75rem;
  }
  .kpi-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
    margin-bottom: 0.5rem;
  }
  .kpi-table th,
  .kpi-table td {
    padding: 0.25rem 0.35rem;
    border-bottom: 1px solid #e2e8f0;
    white-space: nowrap;
    text-align: right;
  }
  .kpi-table th:first-child,
  .kpi-table td:first-child {
    text-align: left;
  }
  .kpi-table tbody tr.muted {
    color: #94a3b8;
  }
  .kpi-total {
    font-weight: 700;
  }
  .kpi-total-green {
    color: #15803d;
  }
  .kpi-total-amber {
    color: #a16207;
  }
  .kpi-total-red {
    color: #b91c1c;
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
  @media (max-width: 1100px) {
    .agent-row.row-2,
    .agent-row.row-3 {
      grid-template-columns: 1fr;
    }
  }
</style>
