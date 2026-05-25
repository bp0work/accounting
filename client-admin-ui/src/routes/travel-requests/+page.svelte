<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { listTravelRequests, patchTravelRequest } from '$lib/api/admin';
  let items: Array<Record<string, unknown>> = [];
  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    items = await listTravelRequests();
  });
  async function setStatus(id: string, status: string) {
    await patchTravelRequest(id, status);
    items = await listTravelRequests();
  }
</script>
<h1>Travel requests</h1>
<table>
  <thead>
    <tr><th>Traveller</th><th>Destination</th><th>Dates</th><th>Status</th><th>Actions</th></tr>
  </thead>
  <tbody>
    {#each items as t}
      <tr>
        <td>{t.traveller_name}</td>
        <td>{t.destination || '—'}</td>
        <td>{t.travel_from} → {t.travel_to}</td>
        <td>{t.status}</td>
        <td>
          {#if t.status === 'submitted' || t.status === 'draft'}
            <button type="button" on:click={() => setStatus(String(t.id), 'approved')}>Approve</button>
            <button type="button" on:click={() => setStatus(String(t.id), 'rejected')}>Reject</button>
          {/if}
        </td>
      </tr>
    {/each}
  </tbody>
</table>
