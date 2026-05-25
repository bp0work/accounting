<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { listCoa, createCoa, patchCoa, importCoaCsv } from '$lib/api/admin';
  let items: Array<Record<string, unknown>> = [];
  let q = '';
  let error = '';
  let code = '';
  let name = '';
  let type = 'expense';
  async function load() {
    items = await listCoa(q || undefined);
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
</script>
<h1>Chart of accounts</h1>
{#if error}<p class="err">{error}</p>{/if}
<div class="card">
  <label>Search <input bind:value={q} on:change={load} /></label>
  <label>CSV import <input type="file" accept=".csv" on:change={onCsv} /></label>
</div>
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
