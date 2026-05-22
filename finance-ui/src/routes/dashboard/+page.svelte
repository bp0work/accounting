<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchDashboard, type CaseDashboard } from '$lib/api/cases';

  let data: CaseDashboard | null = null;
  let error = '';

  onMount(async () => {
    try {
      data = await fetchDashboard();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load dashboard';
    }
  });

  function formatMinutes(m: number | null | undefined) {
    if (m == null) return '—';
    if (m < 60) return `${Math.round(m)} min`;
    return `${(m / 60).toFixed(1)} h`;
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
        <li>Intake: <strong>{data.queue_depths.intake_queue}</strong></li>
        <li>Accounts: <strong>{data.queue_depths.accounts_queue}</strong></li>
        <li>Dead letter: <strong>{data.queue_depths.dead_letter_queue}</strong></li>
        <li>Retry pending: <strong>{data.queue_depths.retry_queue_pending}</strong></li>
      </ul>
    </div>
    <div class="card stat">
      <h2>Avg processing time</h2>
      <p class="big">{formatMinutes(data.average_processing_time_minutes)}</p>
      <p class="hint">Completed cases only</p>
    </div>
    <div class="card stat">
      <h2>Overdue (SLA)</h2>
      <p class="big overdue">{data.overdue_count}</p>
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
            <tr><td>{status}</td><td>{count}</td></tr>
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
            <th>Type</th>
            <th>Status</th>
            <th>Processing</th>
            <th>SLA deadline</th>
          </tr>
        </thead>
        <tbody>
          {#each data.overdue_cases as c}
            <tr class="overdue-row">
              <td><a href={`/cases/${c.id}`}>{c.case_number}</a></td>
              <td>{c.type}</td>
              <td>{c.status}</td>
              <td>{c.processing_time_minutes ?? '—'} min</td>
              <td>{c.sla_deadline ? new Date(c.sla_deadline).toLocaleString() : '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
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
</style>
