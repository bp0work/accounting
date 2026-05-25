<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import {
    listAccountingPeriods,
    generateAccountingPeriods,
    approveTrialBalance,
    closeGlPeriod,
  } from '$lib/api/admin';
  let periods: Array<Record<string, unknown>> = [];
  let msg = '';
  let error = '';
  let loading = false;

  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    await refresh();
  });

  async function refresh() {
    periods = await listAccountingPeriods();
    periods.sort((a, b) => {
      const ay = Number(a.period_year);
      const am = Number(a.period_month);
      const by = Number(b.period_year);
      const bm = Number(b.period_month);
      return ay !== by ? by - ay : bm - am;
    });
  }

  async function gen() {
    loading = true;
    error = '';
    try {
      await generateAccountingPeriods(13);
      msg = 'Generated accounting periods for the current month and the next 12 months.';
      await refresh();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Generate failed';
    } finally {
      loading = false;
    }
  }

  async function approve(id: string) {
    await approveTrialBalance(id);
    msg = 'Trial balance approved.';
    await refresh();
  }

  async function close(id: string) {
    await closeGlPeriod(id);
    msg = 'GL period closed.';
    await refresh();
  }

  function periodLabel(p: Record<string, unknown>) {
    const m = Number(p.period_month);
    const y = Number(p.period_year);
    const names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${names[m] || m} ${y}`;
  }
</script>

<h1>Accounting calendar</h1>
<p>
  GL posting cutoff is <strong>3 working days</strong> after month end (system setting).
  Trial balance reviewer: <strong>finfa.mmlogistix@bp0.work</strong>.
</p>
{#if error}<p class="err">{error}</p>{/if}
{#if msg}<p class="ok">{msg}</p>{/if}
<button type="button" on:click={gen} disabled={loading}>
  {loading ? 'Generating…' : 'Generate periods (current + next 12 months)'}
</button>

<table>
  <thead>
    <tr>
      <th>Period</th>
      <th>GL cutoff</th>
      <th>Trial balance reviewer</th>
      <th>Status</th>
      <th>Actions</th>
    </tr>
  </thead>
  <tbody>
    {#each periods as p}
      <tr>
        <td>{periodLabel(p)}</td>
        <td>{p.gl_cutoff_date}</td>
        <td>{p.trial_balance_reviewer}</td>
        <td><span class="status status-{p.status}">{p.status}</span></td>
        <td class="actions">
          {#if p.status === 'open'}
            <button type="button" on:click={() => approve(String(p.id))}>Approve TB</button>
          {:else if p.status === 'review'}
            <button type="button" on:click={() => close(String(p.id))}>Close GL</button>
          {:else}
            —
          {/if}
        </td>
      </tr>
    {/each}
  </tbody>
</table>
{#if periods.length === 0}
  <p class="hint">No periods yet — click <strong>Generate periods</strong> to create rows for the current month through the next 12 months.</p>
{/if}

<style>
  table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
  th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid #e2e8f0; font-size: 0.9rem; }
  .status { text-transform: capitalize; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.8rem; }
  .status-open { background: #dcfce7; color: #166534; }
  .status-review { background: #fef9c3; color: #854d0e; }
  .status-closed { background: #f1f5f9; color: #475569; }
  .actions button { margin-right: 0.25rem; }
  .hint { color: #64748b; margin-top: 1rem; }
  .err { color: #b91c1c; }
  .ok { color: #15803d; }
</style>
