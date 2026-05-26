<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { fetchCoaStatus, listCoa, createCoa, patchCoa, importCoaCsv } from '$lib/api/admin';

  let items = $state<Array<Record<string, unknown>>>([]);
  let accountCount = $state(0);
  let empty = $state(true);
  let q = $state('');
  let error = $state('');
  let msg = $state('');
  let replaceAllOnImport = $state(true);
  let searching = $state(false);
  let code = $state('');
  let name = $state('');
  let type = $state('expense');

  async function load(opts?: { searchOnly?: boolean }) {
    const term = q.trim();
    if (!opts?.searchOnly) {
      const status = await fetchCoaStatus();
      accountCount = status.account_count;
      empty = status.empty;
    }
    items = await listCoa(term || undefined);
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
    error = '';
    try {
      await createCoa({ account_code: code, account_name: name, account_type: type });
      code = '';
      name = '';
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Add failed';
    }
  }

  async function onCsv(e: Event) {
    const f = (e.target as HTMLInputElement).files?.[0];
    if (!f) return;
    error = '';
    msg = '';
    try {
      const result = await importCoaCsv(f, replaceAllOnImport);
      msg = `Import complete: ${result.created} created, ${result.updated} updated, ${result.skipped} skipped. ${result.active_count} active account(s).`;
      await load();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Import failed';
    } finally {
      (e.target as HTMLInputElement).value = '';
    }
  }

  async function deactivate(id: string) {
    error = '';
    try {
      await patchCoa(id, { is_active: false });
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Deactivate failed';
    }
  }

  async function applySearch() {
    error = '';
    searching = true;
    try {
      await load({ searchOnly: true });
    } catch (e) {
      error = e instanceof Error ? e.message : 'Search failed';
    } finally {
      searching = false;
    }
  }

  async function clearSearch() {
    q = '';
    error = '';
    searching = true;
    try {
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    } finally {
      searching = false;
    }
  }
</script>
<h1>Chart of accounts</h1>
{#if error}<p class="err">{error}</p>{/if}
{#if msg}<p class="ok">{msg}</p>{/if}

{#if empty}
  <div class="banner">
    <strong>Chart of accounts is not configured.</strong>
    <p>Import your COA via CSV to enable posting and approvals. Required columns: <code>account_code</code>, <code>account_name</code>, <code>account_type</code> (optional <code>parent_code</code>).</p>
    <label class="replace">
      <input type="checkbox" bind:checked={replaceAllOnImport} />
      Replace entire chart (recommended — removes any demo accounts and loads only this file)
    </label>
    <label class="upload-btn">
      Upload CSV
      <input type="file" accept=".csv" on:change={onCsv} hidden />
    </label>
  </div>
{:else}
  <p class="meta">{accountCount} active account(s)</p>
  <div class="card search-row">
    <label class="search-field">
      <span class="search-label">Filter by code or name</span>
      <input
        bind:value={q}
        placeholder="e.g. 1000 or Cash"
        onkeydown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            void applySearch();
          }
        }}
      />
    </label>
    <button type="button" onclick={() => void applySearch()} disabled={searching}>
      {searching ? 'Searching…' : 'Search'}
    </button>
    {#if q.trim()}
      <button type="button" class="muted" onclick={() => void clearSearch()}>Clear</button>
    {/if}
    <label class="replace">
      <input type="checkbox" bind:checked={replaceAllOnImport} />
      Replace entire chart on import
    </label>
    <label class="csv-label">Import (CSV) <input type="file" accept=".csv" on:change={onCsv} /></label>
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

{#if q.trim() && items.length === 0 && !empty}
  <p class="meta">No accounts match “{q.trim()}”.</p>
{:else if items.length > 0}
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
  .ok { color: #15803d; margin-bottom: 0.5rem; }
  .replace { display: block; margin: 0.5rem 0; font-size: 0.875rem; }
  .search-row { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: flex-end; }
  .search-field { flex: 1; min-width: 12rem; }
  .search-label { display: block; font-size: 0.875rem; margin-bottom: 0.25rem; }
  .search-field input { width: 100%; padding: 0.4rem; box-sizing: border-box; }
  .muted { background: #f1f5f9; border: 1px solid #cbd5e1; padding: 0.4rem 0.75rem; border-radius: 6px; cursor: pointer; }
</style>
