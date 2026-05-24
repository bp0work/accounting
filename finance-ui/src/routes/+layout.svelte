<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { clearToken, getToken } from '$lib/api/client';
  import { requires2faWarning } from '$lib/api/auth';
  import { APP_TITLE } from '$lib/branding';
  import { initSessionUser, sessionUser } from '$lib/stores/session';

  $: isLogin = $page.url.pathname === '/login';
  $: authed = !!getToken();
  $: show2faBanner = authed && requires2faWarning($sessionUser);

  onMount(async () => {
    initSessionUser();
    if (!isLogin && !getToken()) {
      const { goto } = await import('$app/navigation');
      await goto('/login');
    }
  });

  async function logout() {
    clearToken();
    sessionUser.set(null);
    const { goto } = await import('$app/navigation');
    await goto('/login');
  }
</script>

<svelte:head>
  <title>{APP_TITLE}</title>
</svelte:head>

{#if !isLogin}
  <header class="app-header">
    <strong class="brand">{APP_TITLE}</strong>
    {#if authed}
      <nav class="nav">
        <a href="/dashboard">Dashboard</a>
        <a href="/approvals">Cases & Approvals</a>
        <a href="/export">Export</a>
        <a href="/settings/notifications">Notifications</a>
        <a href="/settings/security">Security</a>
        <button type="button" class="link-btn" on:click={logout}>Logout</button>
      </nav>
    {/if}
  </header>
  {#if show2faBanner}
    <div class="banner-2fa" role="alert">
      ⚠️ Two-factor authentication is required for your role. Please enable it in
      <a href="/settings/security">Security Settings</a>.
    </div>
  {/if}
{/if}
<main class="main">
  <slot />
</main>

<style>
  .app-header {
    padding: 1rem;
    border-bottom: 1px solid #e2e8f0;
    background: #fff;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 1rem;
  }
  .brand {
    font-size: 1.05rem;
  }
  .nav {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 1rem;
    align-items: center;
  }
  .link-btn {
    background: none;
    border: none;
    color: #1d4ed8;
    font: inherit;
    padding: 0;
    text-decoration: underline;
  }
  .banner-2fa {
    background: #fef3c7;
    border-bottom: 1px solid #fcd34d;
    color: #92400e;
    padding: 0.75rem 1rem;
    font-weight: 500;
  }
  .banner-2fa a {
    color: #b45309;
    font-weight: 600;
  }
  .main {
    padding: 1.5rem;
    max-width: 1100px;
    margin: 0 auto;
  }
</style>
