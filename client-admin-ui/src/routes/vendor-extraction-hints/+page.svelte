<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { deleteVendorHint, listAllVendorHints, type VendorExtractionHint } from '$lib/api/vendor-hints';

  let rows: VendorExtractionHint[] = [];
  let loading = true;
  let error = '';
  let msg = '';

  onMount(load);

  async function load() {
    loading = true;
    error = '';
    try {
      rows = await listAllVendorHints();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    } finally {
      loading = false;
    }
  }

  async function remove(row: VendorExtractionHint) {
    if (!confirm(`Remove hint for ${row.vendor_name} / ${row.field_name}?`)) return;
    error = '';
    msg = '';
    try {
      await deleteVendorHint(row.id);
      msg = 'Hint removed.';
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Delete failed';
    }
  }
</script>

<h1>Vendor extraction hints</h1>
<p class="hint">
  Hints teach Hermes how each vendor labels fields on invoices. Finance users add hints from
  case detail when a document is in manual review; manage or remove stored hints here.
</p>

{#if error}<p class="error">{error}</p>{/if}
{#if msg}<p class="success">{msg}</p>{/if}

{#if loading}
  <p>Loading…</p>
{:else if rows.length === 0}
  <p>No vendor hints configured yet.</p>
{:else}
  <table>
    <thead>
      <tr>
        <th>Vendor</th>
        <th>Field</th>
        <th>Label on document</th>
        <th>Example</th>
        <th>Date format</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row}
        <tr>
          <td>{row.vendor_name}</td>
          <td>{row.field_name}</td>
          <td>{row.field_label}</td>
          <td>{row.example_value ?? '—'}</td>
          <td>{row.date_format ?? '—'}</td>
          <td>
            <button type="button" class="danger" onclick={() => remove(row)}>Remove</button>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
{/if}

<style>
  .hint {
    color: #64748b;
    max-width: 52rem;
  }
  .error {
    color: #b91c1c;
  }
  .success {
    color: #15803d;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 1rem;
    font-size: 0.875rem;
  }
  th,
  td {
    border: 1px solid #e2e8f0;
    padding: 0.5rem 0.65rem;
    text-align: left;
    vertical-align: top;
  }
  th {
    background: #f8fafc;
  }
  .danger {
    padding: 0.25rem 0.5rem;
    border: 1px solid #fca5a5;
    border-radius: 4px;
    background: #fef2f2;
    color: #b91c1c;
    cursor: pointer;
  }
</style>
