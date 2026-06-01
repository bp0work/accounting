<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchDashboard, listCases, type CaseDashboard, type CaseItem } from '$lib/api/cases';
  import {
    caseActionByLabel,
    caseStateColumnLabel,
    isExcludedFromRecentCases,
    submittedByDisplay,
  } from '$lib/case-labels';
  import { formatCount } from '$lib/format';

  let data: CaseDashboard | null = null;
  let recentCases: CaseItem[] = [];
  let error = '';

  onMount(async () => {
    try {
      const [dash, cases] = await Promise.all([fetchDashboard(), listCases(50)]);
      data = dash;
      const overdueIds = new Set(dash.overdue_cases.map((c) => c.id));
      recentCases = cases.data.filter((c) => !isExcludedFromRecentCases(c, overdueIds));
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load dashboard';
    }
  });

  function formatMinutes(m: number | null | undefined) {
    if (m == null) return '—';
    const rounded = Math.round(m);
    if (rounded < 60) return `${formatCount(rounded)} min`;
    const hours = Math.round((rounded / 60) * 10) / 10;
    return hours % 1 === 0 ? `${formatCount(hours)} h` : `${hours.toFixed(1)} h`;
  }

  function formatActivity(c: CaseItem) {
    const ts = c.last_activity_at || c.created_at;
    return new Date(ts).toLocaleString();
  }

</script>

<h1>Operations dashboard</h1>
<p class="subtitle">Monitoring and oversight for CFO and Finance Manager roles.</p>

{#if error}<p class="error">{error}</p>{/if}

{#if data}
  <section class="grid">
    <div class="card stat">
      <h2>Queue depths</h2>
      <ul>
        <li>Intake: <strong>{formatCount(data.queue_depths.intake_queue)}</strong></li>
        <li>Accounts: <strong>{formatCount(data.queue_depths.accounts_queue)}</strong></li>
        <li>Dead letter: <strong>{formatCount(data.queue_depths.dead_letter_queue)}</strong></li>
        <li>Retry pending: <strong>{formatCount(data.queue_depths.retry_queue_pending)}</strong></li>
      </ul>
    </div>
    <div class="card stat">
      <h2>Avg processing time</h2>
      <p class="big">{formatMinutes(data.average_processing_time_minutes)}</p>
      <p class="hint">Completed cases only</p>
    </div>
    <div class="card stat">
      <h2>Overdue (SLA)</h2>
      <p class="big overdue">{formatCount(data.overdue_count)}</p>
      <p class="hint">Active cases past SLA deadline</p>
    </div>
  </section>

  <section class="card">
    <h2>Cases by status</h2>
    {#if Object.keys(data.cases_by_status).length === 0}
      <p>No cases yet.</p>
    {:else}
      <table>
        <thead>
          <tr><th>Status</th><th>Count</th></tr>
        </thead>
        <tbody>
          {#each Object.entries(data.cases_by_status) as [status, count]}
            <tr><td>{status}</td><td>{formatCount(count)}</td></tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>

  {#if data.overdue_cases.length > 0}
    <section class="card">
      <h2>Overdue cases</h2>
      <table>
        <thead>
          <tr>
            <th>Case</th>
            <th>Submitted by</th>
            <th>Type</th>
            <th>State</th>
            <th>Action by</th>
            <th>Last Activity</th>
          </tr>
        </thead>
        <tbody>
          {#each data.overdue_cases as c}
            <tr class="overdue-row">
              <td><a href={`/cases/${c.id}`}>{c.case_number}</a></td>
              <td>{submittedByDisplay(c)}</td>
              <td>{c.type}</td>
              <td>{caseStateColumnLabel(c)}</td>
              <td>{caseActionByLabel(c)}</td>
              <td>{formatActivity(c)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>
  {/if}

  {#if recentCases.length > 0}
    <section class="card">
      <h2>Recent cases</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Case</th>
              <th>Submitted by</th>
              <th>Type</th>
              <th>State</th>
              <th>Action by</th>
            </tr>
          </thead>
          <tbody>
            {#each recentCases as c}
              <tr>
                <td><a href={`/cases/${c.id}`}>{c.case_number}</a></td>
                <td>{submittedByDisplay(c)}</td>
                <td>{c.type}</td>
                <td>{caseStateColumnLabel(c)}</td>
                <td>{caseActionByLabel(c)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <p class="hint"><a href="/approvals">View all cases →</a></p>
    </section>
  {/if}
{/if}

<style>
  .subtitle {
    color: #64748b;
    margin-top: 0;
  }
  .error {
    color: #b91c1c;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
    margin-bottom: 1rem;
  }
  .stat .big {
    font-size: 1.75rem;
    font-weight: 700;
    margin: 0.5rem 0;
  }
  .stat .overdue {
    color: #b91c1c;
  }
  .hint {
    color: #64748b;
    font-size: 0.875rem;
    margin: 0;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }
  th,
  td {
    text-align: left;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid #e2e8f0;
  }
  .overdue-row {
    background: #fef2f2;
  }
  .table-wrap {
    overflow-x: auto;
  }
</style>
