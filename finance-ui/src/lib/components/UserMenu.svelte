<script lang="ts">
  import { onMount } from 'svelte';
  import { getToken } from '$lib/api/client';
  import { resolveNavDisplayName } from '$lib/displayUser';

  import type { MenuLink } from './userMenuTypes';

  export let links: MenuLink[] = [];
  export let onLogout: () => void | Promise<void>;

  let open = false;
  let rootEl: HTMLDivElement;
  let username = 'User';

  async function refreshUsername() {
    username = await resolveNavDisplayName(getToken);
  }

  onMount(() => {
    void refreshUsername();
  });

  function toggle(e: MouseEvent) {
    e.stopPropagation();
    open = !open;
    if (open) void refreshUsername();
  }

  function handleWindowClick(e: MouseEvent) {
    if (open && rootEl && !rootEl.contains(e.target as Node)) open = false;
  }

  function close() {
    open = false;
  }

  async function logoutClick() {
    close();
    await onLogout();
  }
</script>

<svelte:window on:click={handleWindowClick} />

<div class="user-menu" bind:this={rootEl}>
  <button
    type="button"
    class="user-trigger"
    on:click={toggle}
    aria-expanded={open}
    aria-haspopup="menu"
  >
    <span class="avatar" aria-hidden="true">{username.slice(0, 1).toUpperCase()}</span>
    <span class="name">{username}</span>
    <span class="chevron" aria-hidden="true">▾</span>
  </button>

  {#if open}
    <div class="dropdown" role="menu">
      <div class="menu-header" role="presentation">👤 {username}</div>
      {#each links as item}
        {#if item.kind === 'link'}
          <a class="menu-item" role="menuitem" href={item.href} on:click={close}>
            {#if item.icon}<span class="icon" aria-hidden="true">{item.icon}</span>{/if}
            {item.label}
          </a>
        {/if}
      {/each}
      <div class="divider" role="separator"></div>
      <button type="button" class="menu-item logout" role="menuitem" on:click={logoutClick}>
        Logout
      </button>
    </div>
  {/if}
</div>

<style>
  .user-menu {
    position: relative;
    margin-left: auto;
  }
  .user-trigger {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.35rem 0.6rem;
    border: 1px solid #e2e8f0;
    border-radius: 999px;
    background: #f8fafc;
    font: inherit;
    font-size: 0.875rem;
    color: #0f172a;
    cursor: pointer;
  }
  .user-trigger:hover {
    background: #f1f5f9;
    border-color: #cbd5e1;
  }
  .avatar {
    width: 1.75rem;
    height: 1.75rem;
    border-radius: 50%;
    background: #1d4ed8;
    color: #fff;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 600;
  }
  .name {
    max-width: 10rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .chevron {
    font-size: 0.65rem;
    color: #64748b;
  }
  .dropdown {
    position: absolute;
    right: 0;
    top: calc(100% + 0.35rem);
    min-width: 14rem;
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 0.5rem;
    box-shadow: 0 10px 25px rgba(15, 23, 42, 0.12);
    z-index: 50;
    padding: 0.35rem 0;
  }
  .menu-header {
    padding: 0.5rem 1rem;
    font-size: 0.875rem;
    font-weight: 600;
    color: #334155;
    cursor: default;
  }
  .menu-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
    padding: 0.5rem 1rem;
    border: none;
    background: none;
    font: inherit;
    font-size: 0.875rem;
    color: #0f172a;
    text-align: left;
    text-decoration: none;
    cursor: pointer;
  }
  .menu-item:hover {
    background: #f1f5f9;
  }
  .icon {
    width: 1.25rem;
    text-align: center;
  }
  .divider {
    height: 1px;
    margin: 0.35rem 0;
    background: #e2e8f0;
  }
  .logout {
    color: #b91c1c;
  }
  .logout:hover {
    background: #fef2f2;
  }
</style>
