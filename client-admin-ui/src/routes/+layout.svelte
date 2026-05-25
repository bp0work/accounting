<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { clearToken, getToken } from '$lib/api/client';
  import { APP_TITLE } from '$lib/branding';

  $: isLogin = $page.url.pathname === '/login';
  let isLoggedIn =
    typeof localStorage !== 'undefined' && !!localStorage.getItem('client_admin_access_token');

  onMount(async () => {
    isLoggedIn = !!getToken();
    if (!isLogin && !isLoggedIn) {
      const { goto } = await import('$app/navigation');
      await goto('/login');
    }
  });

  async function logout() {
    clearToken();
    isLoggedIn = false;
    const { goto } = await import('$app/navigation');
    await goto('/login');
  }
</script>

<svelte:head><title>{APP_TITLE}</title></svelte:head>

{#if !isLogin}
  <header class="app-header">
    <strong>{APP_TITLE}</strong>
    {#if isLoggedIn}
      <nav class="nav">
        <a href="/dashboard">Dashboard</a>
        <a href="/company">Company</a>
        <a href="/chart-of-accounts">Chart of Accounts</a>
        <a href="/mailboxes">Mailboxes</a>
        <a href="/users">Users</a>
        <a href="/policies">Policies</a>
        <a href="/agreements">Agreements</a>
        <a href="/travel-requests">Travel Requests</a>
        <a href="/accounting-calendar">Accounting Calendar</a>
        <button type="button" class="link-btn" on:click={logout}>Logout</button>
      </nav>
    {/if}
  </header>
{/if}
<main class="main"><slot /></main>

<style>
  .app-header {
    padding: 1rem;
    border-bottom: 1px solid #e2e8f0;
    background: #fff;
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    align-items: center;
  }
  .nav {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    font-size: 0.875rem;
  }
  .link-btn {
    background: none;
    border: none;
    color: #1d4ed8;
    font: inherit;
    text-decoration: underline;
    cursor: pointer;
  }
  .main {
    padding: 1.5rem;
    max-width: 1100px;
    margin: 0 auto;
  }
</style>
