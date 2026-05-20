<script lang="ts">
  import { onMount } from 'svelte';
  import { getToken } from '$lib/api/client';

  onMount(() => {
    window.location.href = getToken() ? '/approvals' : '/login';
  });
</script>

<p>Loading…</p>
