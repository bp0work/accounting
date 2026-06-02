<script lang="ts">
  import '../app.css';
  import { onDestroy, onMount } from 'svelte';
  import { page } from '$app/stores';
  import { clearToken } from '$lib/api/client';
  import { fetchDashboardStats } from '$lib/api/dashboard';
  import { requires2faWarning } from '$lib/api/auth';
  import UserMenu from '$lib/components/UserMenu.svelte';
  import type { MenuLink } from '$lib/components/userMenuTypes';
  import {
    liveUpdates,
    startLiveUpdates,
    stopLiveUpdates,
  } from '$lib/stores/live-updates';
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

  /** Source asset 1536×1024 — displayed at 10% (154×102 CSS px). */
  const LOGO_WIDTH_PX = 154;
  const LOGO_HEIGHT_PX = 102;

  $: isLogin = $page.url.pathname === '/login';
  $: isLoggedIn = $authReady && $sessionUser !== null;
  $: show2faBanner = isLoggedIn && requires2faWarning($sessionUser);
  $: showAppChrome = !isLogin && $authReady;
  $: showNav = showAppChrome && isLoggedIn;
  $: navBadgeCount = dashboardActionCountForRole(
    ($sessionUser?.role_name ?? '').toLowerCase(),
    actionRequiredCount
  );
  $: showNavBadge = navBadgeCount > 0;

  let actionRequiredCount = 0;
  let lastLiveSequence = 0;

  onMount(async () => {
    const loggedIn = await initAuth();
    if (!isLogin && !loggedIn) {
      const { goto } = await import('$app/navigation');
      await goto('/login');
      return;
    }
    if (loggedIn) {
      await refreshActionCount();
      startLiveUpdates();
    }
  });

  onDestroy(() => {
    stopLiveUpdates();
  });

  $: if (
    typeof window !== 'undefined' &&
    isLoggedIn &&
    $liveUpdates.sequence !== lastLiveSequence
  ) {
    lastLiveSequence = $liveUpdates.sequence;
    const payload = $liveUpdates.lastCaseStatusEvent;
    if (payload) {
      window.dispatchEvent(new CustomEvent('finance:case-status-changed', { detail: payload }));
      void refreshActionCount();
    }
  }

  async function refreshActionCount() {
    if (!isLoggedIn) return;
    try {
      const stats = await fetchDashboardStats();
      actionRequiredCount = stats.action_required_count ?? 0;
    } catch {
      actionRequiredCount = 0;
    }
  }

  function dashboardActionCountForRole(role: string, count: number): number {
    if (role === 'finance_manager') return 0;
    if (
      role === 'accounts_manager' ||
      role === 'accounts_clerk' ||
      role === 'cfo' ||
      role === 'finance_director'
    ) {
      return count;
    }
    return 0;
  }

  async function logout() {
    stopLiveUpdates();
    clearToken();
    clearAuth();
    const { goto } = await import('$app/navigation');
    await goto('/login');
  }
</script>

<svelte:head>
  <title>mmlogistix Finance Operations</title>
</svelte:head>

{#if isLogin}
  <main class="main">
    <slot />
  </main>
{:else if !showAppChrome}
  <div class="app-topbar">
    <header class="app-header app-header--skeleton" aria-busy="true" aria-label="Loading">
      <span class="skeleton-bar skeleton-logo"></span>
      <span class="skeleton-nav">
        <span class="skeleton-bar"></span>
        <span class="skeleton-bar"></span>
        <span class="skeleton-bar skeleton-short"></span>
      </span>
    </header>
  </div>
  <main class="main main--offset">
    <slot />
  </main>
{:else}
  <div class="app-topbar">
    <header class="app-header">
      <a href="/dashboard" class="brand" aria-label="bp0.work — home">
        <img
          class="brand-logo"
          src="/bp0work-logo.png"
          alt="bp0.work — Business Process Automation"
          width={LOGO_WIDTH_PX}
          height={LOGO_HEIGHT_PX}
          decoding="async"
        />
      </a>
      {#if showNav}
        <nav class="nav">
          <a href="/dashboard">Dashboard</a>
          <a href="/approvals" class="cases-nav-link">
            Cases & Approvals
            {#if showNavBadge}
              <span class="nav-badge" aria-label={`${navBadgeCount} cases need action`}>
                {navBadgeCount}
              </span>
            {/if}
          </a>
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
  </div>
  <main class="main main--offset" class:main--offset-banner={show2faBanner}>
    <slot />
  </main>
{/if}

<style>
  .app-topbar {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 200;
    background: #fff;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
  }

  .app-header {
    padding: 0.5rem 1rem;
    border-bottom: 1px solid #e2e8f0;
    background: #fff;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 1rem;
    width: 100%;
    min-height: calc(102px + 1rem);
    box-sizing: border-box;
  }

  .app-header--skeleton {
    min-height: calc(102px + 1rem);
  }

  .brand {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    line-height: 0;
    text-decoration: none;
  }

  .brand-logo {
    display: block;
    width: 154px;
    height: 102px;
    object-fit: contain;
  }

  .nav {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    align-items: center;
    flex: 1;
    min-width: 0;
    justify-content: flex-end;
  }

  .nav a {
    color: #1e40af;
    text-decoration: none;
    font-size: 0.9rem;
  }

  .nav a:hover {
    text-decoration: underline;
  }

  .cases-nav-link {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
  }

  .nav-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.25rem;
    height: 1.25rem;
    padding: 0 0.35rem;
    border-radius: 999px;
    background: #dc2626;
    color: #fff;
    font-size: 0.72rem;
    font-weight: 700;
    line-height: 1;
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

  .skeleton-logo {
    width: 154px;
    height: 102px;
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

  /* Header min-height (102px logo + padding) + border */
  .main--offset {
    padding-top: calc(102px + 1.5rem + 2px);
  }

  .main--offset-banner {
    padding-top: calc(102px + 1.5rem + 2px + 3.25rem);
  }
</style>
