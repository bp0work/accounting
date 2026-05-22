<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { approve, getApproval, reject, type ApprovalItem } from '$lib/api/approvals';

  let item: ApprovalItem | null = null;
  let note = '';
  let reason = '';
  let message = '';
  let error = '';

  $: id = $page.params.id;

  onMount(load);

  async function load() {
    try {
      item = await getApproval(id);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Not found';
    }
  }

  async function doApprove() {
    message = '';
    try {
      await approve(id, note || 'Approved');
      message = 'Approved';
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Approve failed';
    }
  }

  async function doReject() {
    message = '';
    try {
      await reject(id, reason || 'Rejected');
      message = 'Rejected';
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Reject failed';
    }
  }
</script>

<a href="/approvals">← Back</a>
<h1>Approval detail</h1>

{#if error}<p style="color: #b91c1c;">{error}</p>{/if}
{#if message}<p style="color: #15803d;">{message}</p>{/if}

{#if item}
  <div class="card">
    <p><strong>{item.case_number}</strong> ({item.case_type})</p>
    <p>{item.subject}</p>
    <p>Status: <strong>{item.status}</strong></p>
  </div>

  {#if item.status === 'pending'}
    <div class="card">
      <h2>Approve</h2>
      <textarea bind:value={note} placeholder="Note" rows="3" style="width: 100%;"></textarea>
      <button on:click={doApprove} style="margin-top: 0.5rem;">Approve</button>
    </div>
    <div class="card">
      <h2>Reject</h2>
      <textarea bind:value={reason} placeholder="Reason (required)" rows="3" style="width: 100%;"></textarea>
      <button on:click={doReject} style="margin-top: 0.5rem;">Reject</button>
    </div>
  {/if}
{/if}
