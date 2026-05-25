<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { getToken } from '$lib/api/client';
  onMount(() => goto(getToken() ? '/dashboard' : '/login'));
</script>
<p>Loading…</p>
