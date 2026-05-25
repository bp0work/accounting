<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { fetchDashboard } from '$lib/api/admin';
  let data: Awaited<ReturnType<typeof fetchDashboard>> | null = null;
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
      <li class:done={c.complete}>
        <a href={c.href}>{c.label}</a>
        {c.complete ? '✓' : '— missing'}
      </li>
    {/each}
  </ul>
{/if}
<style>
  .checks { list-style: none; padding: 0; }
  .checks li { padding: 0.5rem 0; border-bottom: 1px solid #e2e8f0; }
  .checks li.done { color: #15803d; }
  .err { color: #b91c1c; }
</style>
