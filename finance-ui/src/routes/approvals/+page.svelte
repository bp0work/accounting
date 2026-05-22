<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { listApprovals, type ApprovalItem } from '$lib/api/approvals';

  let items: ApprovalItem[] = [];
  let error = '';

  onMount(async () => {
    try {
      const res = await listApprovals(true);
      items = res.data;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
    }
  });
</script>

<h1>My pending approvals</h1>
{#if error}<p style="color: #b91c1c;">{error}</p>{/if}

{#if items.length === 0}
  <p>No pending approvals.</p>
{:else}
  {#each items as item}
    <a href={`/approvals/${item.id}`} class="card" style="display: block; text-decoration: none; color: inherit;">
      <strong>{item.case_number}</strong> — {item.case_type}
      <div>{item.subject || 'No subject'}</div>
      {#if item.amount}
        <div>{item.amount.currency} {item.amount.value}</div>
      {/if}
      <div>Status: {item.status}</div>
    </a>
  {/each}
{/if}
