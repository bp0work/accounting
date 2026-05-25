<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { getExpenseLimits, patchExpenseLimits, listRegulatoryDocs } from '$lib/api/admin';
  let tab: 'expense' | 'regulatory' = 'expense';
  let limits: Record<string, string> = {};
  let docs: Array<Record<string, unknown>> = [];
  let error = '';
  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    try {
      limits = (await getExpenseLimits()) as Record<string, string>;
      docs = await listRegulatoryDocs();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    }
  });
  async function saveLimits() {
    await patchExpenseLimits(limits);
  }
</script>
<h1>Policies</h1>
{#if error}<p class="err">{error}</p>{/if}
<div class="tabs">
  <button type="button" class:active={tab === 'expense'} on:click={() => (tab = 'expense')}>Expense</button>
  <button type="button" class:active={tab === 'regulatory'} on:click={() => (tab = 'regulatory')}>Regulatory</button>
</div>
{#if tab === 'expense'}
  <div class="card">
    <label>Meal limit / day (SGD) <input type="number" bind:value={limits.meal_limit_per_day} /></label>
    <label>Transport / trip (SGD) <input type="number" bind:value={limits.transport_limit_per_trip} /></label>
    <label>Accommodation / night (SGD) <input type="number" bind:value={limits.accommodation_limit_per_night} /></label>
    <label>Per diem (SGD) <input type="number" bind:value={limits.per_diem_rate} /></label>
    <label>Entertainment / occasion (SGD) <input type="number" bind:value={limits.entertainment_limit_per_occasion} /></label>
    <button type="button" on:click={saveLimits}>Save limits</button>
  </div>
{:else}
  <p>Upload regulatory PDFs via API (MAS TRM, PDPA, Companies Act, IRAS GST, Income Tax Act).</p>
  <ul>
    {#each docs as d}
      <li>{d.name} — {d.filename} ({d.file_size} bytes) — {d.uploaded_at}</li>
    {/each}
  </ul>
{/if}
