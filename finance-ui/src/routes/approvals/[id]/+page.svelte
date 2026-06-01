<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { getApproval } from '$lib/api/approvals';

  let error = '';

  $: id = $page.params.id;

  onMount(async () => {
    error = '';
    try {
      const token = await ensureValidAccessToken();
      if (!token) {
        const { goto } = await import('$app/navigation');
        await goto('/login');
        return;
      }
      const approval = await getApproval(id);
      const { goto } = await import('$app/navigation');
      await goto(`/cases/${approval.case_id}`, { replaceState: true });
    } catch (e) {
      error = e instanceof Error ? e.message : 'Approval not found';
    }
  });
</script>

<p>Redirecting to case…</p>
{#if error}<p class="err">{error}</p>{/if}

<style>
  .err {
    color: #b91c1c;
  }
</style>
