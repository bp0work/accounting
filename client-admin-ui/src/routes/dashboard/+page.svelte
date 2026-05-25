<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { fetchDashboard, type DashboardCheck } from '$lib/api/admin';
  let data: { checks: DashboardCheck[]; complete_count: number; total_count: number } | null = null;
  let error = '';
  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    try {
      data = await fetchDashboard();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
    }
  });
</script>
<h1>Configuration dashboard</h1>
<p>Overview of tenant setup completeness.</p>
{#if error}<p class="err">{error}</p>{/if}
{#if data}
  <p><strong>{data.complete_count}</strong> of <strong>{data.total_count}</strong> sections complete.</p>
  <ul class="checks">
    {#each data.checks as c}
      <li class:done={c.complete} class:pending={!c.complete}>
        <a href={c.href}>{c.label}</a>
        <span class="status">{c.complete ? 'Complete' : 'Incomplete'}</span>
        {#if c.detail}
          <p class="detail">{c.detail}</p>
        {/if}
      </li>
    {/each}
  </ul>
{/if}
<style>
  .checks { list-style: none; padding: 0; }
  .checks li { padding: 0.75rem 0; border-bottom: 1px solid #e2e8f0; }
  .checks li.done .status { color: #15803d; }
  .checks li.pending .status { color: #b45309; }
  .status { font-size: 0.875rem; margin-left: 0.5rem; }
  .detail { margin: 0.35rem 0 0; font-size: 0.875rem; color: #64748b; }
  .err { color: #b91c1c; }
</style>
