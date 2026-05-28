<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { ACCESS_TOKEN_KEY, clearToken, getToken } from '$lib/api/client';
  import { APP_TITLE } from '$lib/branding';
  import UserMenu from '$lib/components/UserMenu.svelte';
  import type { MenuLink } from '$lib/components/userMenuTypes';

  const userMenuLinks: MenuLink[] = [
    { kind: 'link', href: '/settings/security', label: 'Change Password', icon: '🔑' },
  ];

  /** Source asset 1536×1024 — displayed at 10% (154×102 CSS px). */
  const LOGO_WIDTH_PX = 154;
  const LOGO_HEIGHT_PX = 102;

  $: isLogin = $page.url.pathname === '/login';
  /** Re-run on navigation (e.g. after login) — initial `let` alone does not update on client route change. */
  $: routePath = $page.url.pathname;
  $: isLoggedIn =
    !isLogin &&
    typeof localStorage !== 'undefined' &&
    (!!localStorage.getItem(ACCESS_TOKEN_KEY) || !!getToken());

  onMount(async () => {
    if (!isLogin && !getToken()) {
      const { goto } = await import('$app/navigation');
      await goto('/login');
    }
  });

  async function logout() {
    clearToken();
    const { goto } = await import('$app/navigation');
    await goto('/login');
  }
</script>

<svelte:head><title>{APP_TITLE}</title></svelte:head>

{#if isLogin}
  <main class="main">
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
      {#if isLoggedIn}
        <nav class="nav">
          <a href="/dashboard">Dashboard</a>
          <a href="/company">Company</a>
          <a href="/chart-of-accounts">Chart of Accounts</a>
          <a href="/mailboxes">Mailboxes</a>
          <a href="/vendor-extraction-hints">Vendor hints</a>
          <a href="/binding-authority">Binding Authority</a>
          <a href="/policies">Travel &amp; Entertainment</a>
          <a href="/regulatory-policies">Regulatory Policies</a>
          <a href="/accounting-calendar">Accounting Calendar</a>
          <UserMenu links={userMenuLinks} onLogout={logout} />
        </nav>
      {/if}
    </header>
  </div>
  <main class="main main--offset">
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
    gap: 0.75rem;
    font-size: 0.875rem;
    align-items: center;
    flex: 1;
    min-width: 0;
    justify-content: flex-end;
  }

  .nav a {
    color: #1e40af;
    text-decoration: none;
  }

  .nav a:hover {
    text-decoration: underline;
  }

  .main {
    padding: 1.5rem;
    max-width: 1100px;
    margin: 0 auto;
  }

  .main--offset {
    padding-top: calc(102px + 1.5rem + 2px);
  }
</style>
