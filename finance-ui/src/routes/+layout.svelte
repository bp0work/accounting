<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { clearToken, getToken } from '$lib/api/client';
  import { requires2faWarning } from '$lib/api/auth';
  import { APP_TITLE } from '$lib/branding';
  import UserMenu from '$lib/components/UserMenu.svelte';
  import type { MenuLink } from '$lib/components/userMenuTypes';
  import { initSessionUser, sessionUser } from '$lib/stores/session';

  const userMenuLinks: MenuLink[] = [
    { kind: 'link', href: '/settings/notifications', label: 'Notifications', icon: '🔔' },
    { kind: 'link', href: '/settings/security', label: 'Security', icon: '🔒' },
    { kind: 'link', href: '/settings/change-password', label: 'Change Password', icon: '🔑' },
  ];

  $: isLogin = $page.url.pathname === '/login';

  /** Sync read on first client paint — avoids nav hidden until async onMount. */
  let isLoggedIn =
    typeof localStorage !== 'undefined' && !!localStorage.getItem('finance_access_token');

  $: show2faBanner = isLoggedIn && requires2faWarning($sessionUser);

  onMount(async () => {
    initSessionUser();
    isLoggedIn = !!getToken();
    if (!isLogin && !isLoggedIn) {
      const { goto } = await import('$app/navigation');
      await goto('/login');
    }
  });

  async function logout() {
    clearToken();
    isLoggedIn = false;
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
    {#if isLoggedIn}
      <nav class="nav">
        <a href="/dashboard">Dashboard</a>
        <a href="/approvals">Cases & Approvals</a>
        <a href="/counterparty-accounts">Counterparty Accounts</a>
        <a href="/agreements">Agreements</a>
        <a href="/accounting-calendar">Accounting Calendar</a>
        <a href="/export">Export</a>
        <UserMenu links={userMenuLinks} onLogout={logout} />
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
    width: 100%;
  }
  .brand {
    font-size: 1.05rem;
  }
  .nav {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    align-items: center;
    flex: 1;
    min-width: 0;
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
