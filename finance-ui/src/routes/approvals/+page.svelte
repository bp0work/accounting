<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { listCases, type CaseItem } from '$lib/api/cases';
  import { documentTypeLabel, clientVendorColumnValue } from '$lib/case-labels';

  let items: CaseItem[] = [];
  let error = '';

  onMount(async () => {
    try {
      const res = await listCases(200);
      items = res.data;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
    }
  });

  function formatAmount(c: CaseItem) {
    if (c.amount_value == null) return '—';
    return `${c.amount_currency} ${c.amount_value}`;
  }

  function formatActivity(c: CaseItem) {
    const ts = c.last_activity_at || c.created_at;
    return new Date(ts).toLocaleString();
  }
</script>

<h1>Cases & Approvals</h1>
<p class="subtitle">All cases — monitoring view for finance leadership (not a personal task queue).</p>

{#if error}<p class="error">{error}</p>{/if}

{#if items.length === 0 && !error}
  <p>No cases found.</p>
{:else}
  <div class="table-wrap card">
    <table>
      <thead>
        <tr>
          <th></th>
          <th>Case</th>
          <th>Document Type</th>
          <th>Status</th>
          <th>Submitted By</th>
          <th>Client / Vendor</th>
          <th>Amount</th>
          <th>Last Activity</th>
          <th>Error</th>
        </tr>
      </thead>
      <tbody>
        {#each items as item}
          <tr class:overdue={item.is_overdue}>
            <td class="indicator" title={item.is_overdue ? 'Overdue (past SLA)' : 'On track'}>
              {item.is_overdue ? '⚠' : '·'}
            </td>
            <td>
              <a href={`/cases/${item.id}`}>{item.case_number}</a>
            </td>
            <td>{documentTypeLabel(item.type)}</td>
            <td>{item.status}</td>
            <td>{item.from_address || '—'}</td>
            <td>{clientVendorColumnValue(item)}</td>
            <td>{formatAmount(item)}</td>
            <td>{formatActivity(item)}</td>
            <td class="error-cell">{item.error_reason || '—'}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  .subtitle {
    color: #64748b;
  }
  .error {
    color: #b91c1c;
  }
  .table-wrap {
    overflow-x: auto;
    padding: 0;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }
  th,
  td {
    text-align: left;
    padding: 0.6rem 0.75rem;
    border-bottom: 1px solid #e2e8f0;
  }
  tr.overdue {
    background: #fef2f2;
  }
  .indicator {
    width: 2rem;
    text-align: center;
    font-size: 1.1rem;
  }
  tr.overdue .indicator {
    color: #b91c1c;
  }
  .error-cell {
    color: #c2410c;
    max-width: 14rem;
    word-break: break-word;
  }
</style>
