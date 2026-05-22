<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { apiFetch } from '$lib/api/client';
  import type { CaseItem } from '$lib/api/cases';

  let item: CaseItem | null = null;
  let error = '';

  $: id = $page.params.id;

  onMount(load);

  async function load() {
    error = '';
    try {
      item = await apiFetch<CaseItem>(`/cases/${id}`);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Not found';
    }
  }
</script>

<a href="/approvals">← Cases & Approvals</a>
<h1>Case detail</h1>

{#if error}<p class="error">{error}</p>{/if}
{#if item}
  <div class="card" class:overdue={item.is_overdue}>
    {#if item.is_overdue}<p class="badge">Overdue — past SLA threshold</p>{/if}
    <p><strong>{item.case_number}</strong> · {item.type}</p>
    <p>Status: <strong>{item.status}</strong></p>
    <p>{item.subject}</p>
    <p>Counterparty: {item.counterparty_name || '—'}</p>
    <p>Processing time: {item.processing_time_minutes != null ? `${item.processing_time_minutes} min` : '—'}</p>
    <p>Created: {new Date(item.created_at).toLocaleString()}</p>
    {#if item.sla_deadline}
      <p>SLA deadline: {new Date(item.sla_deadline).toLocaleString()}</p>
    {/if}
  </div>
{/if}

<style>
  .error {
    color: #b91c1c;
  }
  .overdue {
    border-color: #fecaca;
    background: #fef2f2;
  }
  .badge {
    color: #b91c1c;
    font-weight: 600;
    margin-top: 0;
  }
</style>
