<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { clearToken } from '$lib/api/client';
  import { requires2faWarning } from '$lib/api/auth';
  import { APP_TITLE } from '$lib/branding';
  import UserMenu from '$lib/components/UserMenu.svelte';
  import type { MenuLink } from '$lib/components/userMenuTypes';
  import {
    authReady,
    clearAuth,
    initAuth,
    sessionUser,
  } from '$lib/stores/session';

  const userMenuLinks: MenuLink[] = [
    { kind: 'link', href: '/settings/notifications', label: 'Notifications', icon: '🔔' },
    { kind: 'link', href: '/settings/security', label: 'Security', icon: '🔒' },
    { kind: 'link', href: '/settings/change-password', label: 'Change Password', icon: '🔑' },
  ];

  $: isLogin = $page.url.pathname === '/login';
  $: isLoggedIn = $authReady && $sessionUser !== null;
  $: show2faBanner = isLoggedIn && requires2faWarning($sessionUser);
  $: showAppChrome = !isLogin && $authReady;
  $: showNav = showAppChrome && isLoggedIn;

  onMount(async () => {
    const loggedIn = await initAuth();
    if (!isLogin && !loggedIn) {
      const { goto } = await import('$app/navigation');
      await goto('/login');
    }
  });

  async function logout() {
    clearToken();
    clearAuth();
    const { goto } = await import('$app/navigation');
    await goto('/login');
  }
</script>

<svelte:head>
  <title>{APP_TITLE}</title>
</svelte:head>

{#if isLogin}
  <main class="main">
    <slot />
  </main>
{:else if !showAppChrome}
  <header class="app-header app-header--skeleton" aria-busy="true" aria-label="Loading">
    <span class="brand skeleton-bar skeleton-brand"></span>
    <span class="skeleton-nav">
      <span class="skeleton-bar"></span>
      <span class="skeleton-bar"></span>
      <span class="skeleton-bar skeleton-short"></span>
    </span>
  </header>
  <main class="main">
    <slot />
  </main>
{:else}
  <header class="app-header">
    <strong class="brand">{APP_TITLE}</strong>
    {#if showNav}
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
  <main class="main">
    <slot />
  </main>
{/if}

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
  .app-header--skeleton {
    min-height: 3.25rem;
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
  .skeleton-nav {
    display: flex;
    flex: 1;
    gap: 0.75rem;
    justify-content: flex-end;
    align-items: center;
    min-width: 0;
  }
  .skeleton-bar {
    display: inline-block;
    height: 0.875rem;
    width: 5rem;
    border-radius: 4px;
    background: linear-gradient(90deg, #e2e8f0 25%, #f1f5f9 50%, #e2e8f0 75%);
    background-size: 200% 100%;
    animation: skeleton-shimmer 1.2s ease-in-out infinite;
  }
  .skeleton-brand {
    width: 12rem;
    height: 1.1rem;
  }
  .skeleton-short {
    width: 3.5rem;
    border-radius: 999px;
  }
  @keyframes skeleton-shimmer {
    0% {
      background-position: 100% 0;
    }
    100% {
      background-position: -100% 0;
    }
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
