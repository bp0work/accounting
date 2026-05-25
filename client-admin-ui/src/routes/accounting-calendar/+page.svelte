<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { listAccountingPeriods, generateAccountingPeriods, approveTrialBalance, closeGlPeriod } from '$lib/api/admin';
  let periods: Array<Record<string, unknown>> = [];
  let msg = '';
  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    await refresh();
  });
  async function refresh() {
    periods = await listAccountingPeriods();
  }
  async function gen() {
    await generateAccountingPeriods(12);
    msg = 'Generated 12 periods.';
    await refresh();
  }
  async function approve(id: string) {
    await approveTrialBalance(id);
    await refresh();
  }
  async function close(id: string) {
    await closeGlPeriod(id);
    await refresh();
  }
</script>
<h1>Accounting calendar</h1>
<p>GL posting cutoff: 3 working days after month end (configurable in system settings). Trial balance reviewer: finfa.mmlogistix@bp0.work</p>
{#if msg}<p class="ok">{msg}</p>{/if}
<button type="button" on:click={gen}>Generate periods</button>
<table>
  <thead><tr><th>Period</th><th>GL cutoff</th><th>TB reviewer</th><th>Status</th><th>Actions</th></tr></thead>
  <tbody>
    {#each periods as p}
      <tr>
        <td>{p.period_year}-{String(p.period_month).padStart(2, '0')}</td>
        <td>{p.gl_cutoff_date}</td>
        <td>{p.trial_balance_reviewer}</td>
        <td>{p.status}</td>
        <td>
          {#if p.status === 'open'}
            <button type="button" on:click={() => approve(String(p.id))}>Approve trial balance</button>
          {:else if p.status === 'review'}
            <button type="button" on:click={() => close(String(p.id))}>Close GL</button>
          {/if}
        </td>
      </tr>
    {/each}
  </tbody>
</table>
