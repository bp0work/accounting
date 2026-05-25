<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { fetchCoaStatus, listCoa, createCoa, patchCoa, importCoaCsv } from '$lib/api/admin';
  let items: Array<Record<string, unknown>> = [];
  let accountCount = 0;
  let empty = true;
  let q = '';
  let error = '';
  let code = '';
  let name = '';
  let type = 'expense';
  async function load() {
    const status = await fetchCoaStatus();
    accountCount = status.account_count;
    empty = status.empty;
    items = empty && !q ? [] : await listCoa(q || undefined);
  }
  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    try {
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    }
  });
  async function add() {
    await createCoa({ account_code: code, account_name: name, account_type: type });
    code = '';
    name = '';
    await load();
  }
  async function onCsv(e: Event) {
    const f = (e.target as HTMLInputElement).files?.[0];
    if (!f) return;
    await importCoaCsv(f);
    await load();
  }
  async function deactivate(id: string) {
    await patchCoa(id, { is_active: false });
    await load();
  }
  async function search() {
    await load();
  }
</script>
<h1>Chart of accounts</h1>
{#if error}<p class="err">{error}</p>{/if}

{#if empty}
  <div class="banner">
    <strong>Chart of accounts is not configured.</strong>
    <p>Import your COA via CSV to enable posting and approvals. Required columns: <code>account_code</code>, <code>account_name</code>, <code>account_type</code> (optional <code>parent_code</code>).</p>
    <label class="upload-btn">
      Upload CSV
      <input type="file" accept=".csv" on:change={onCsv} hidden />
    </label>
  </div>
{:else}
  <p class="meta">{accountCount} active account(s)</p>
  <div class="card">
    <label>Search <input bind:value={q} on:keydown={(e) => e.key === 'Enter' && search()} placeholder="Code or name" /></label>
    <button type="button" on:click={search}>Search</button>
    <label class="csv-label">Import more (CSV) <input type="file" accept=".csv" on:change={onCsv} /></label>
  </div>
{/if}

<div class="card">
  <h2>Add account</h2>
  <input placeholder="Code" bind:value={code} />
  <input placeholder="Name" bind:value={name} />
  <select bind:value={type}>
    <option value="asset">asset</option>
    <option value="liability">liability</option>
    <option value="equity">equity</option>
    <option value="revenue">revenue</option>
    <option value="expense">expense</option>
  </select>
  <button type="button" on:click={add}>Add</button>
</div>

{#if !empty || items.length > 0}
  <table>
    <thead><tr><th>Code</th><th>Name</th><th>Type</th><th></th></tr></thead>
    <tbody>
      {#each items as a}
        <tr>
          <td>{a.account_code}</td>
          <td>{a.account_name}</td>
          <td>{a.account_type}</td>
          <td><button type="button" on:click={() => deactivate(String(a.id))}>Deactivate</button></td>
        </tr>
      {/each}
    </tbody>
  </table>
{/if}
<style>
  .banner { background: #fff7ed; border: 1px solid #fdba74; padding: 1.25rem; border-radius: 8px; margin-bottom: 1rem; }
  .upload-btn { display: inline-block; margin-top: 0.75rem; padding: 0.5rem 1rem; background: #1d4ed8; color: #fff; border-radius: 6px; cursor: pointer; }
  .meta { color: #64748b; }
  .card { background: #fff; border: 1px solid #e2e8f0; padding: 1rem; margin-bottom: 1rem; border-radius: 8px; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid #e2e8f0; }
  .err { color: #b91c1c; }
</style>
