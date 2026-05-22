<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { getToken } from '$lib/api/client';
  import { APP_TITLE } from '$lib/branding';

  $: isLogin = $page.url.pathname === '/login';
  $: authed = !!getToken();

  onMount(() => {
    if (!isLogin && !getToken()) {
      window.location.href = '/login';
    }
  });
</script>

<svelte:head>
  <title>{APP_TITLE}</title>
</svelte:head>

<header style="padding: 1rem; border-bottom: 1px solid #e2e8f0; background: #fff;">
  <strong>{APP_TITLE}</strong>
  {#if authed}
    <nav style="display: inline-flex; gap: 1rem; margin-left: 2rem;">
      <a href="/approvals">Approvals</a>
      <a href="/settings/notifications">Notifications</a>
    </nav>
  {/if}
</header>
<main style="padding: 1.5rem; max-width: 960px; margin: 0 auto;">
  <slot />
</main>
