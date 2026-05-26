<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { listRoleUsers, patchUser, upsertRoleUser } from '$lib/api/admin';

  type RoleRow = {
    id?: string;
    role_name: string;
    role_label: string;
    display_name: string;
    email: string;
    username?: string;
  };

  let items: RoleRow[] = [];
  let error = '';
  let msg = '';

  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    await reload();
  });

  async function reload() {
    error = '';
    try {
      const rows = await listRoleUsers();
      items = rows.map((u) => ({
        id: u.id ? String(u.id) : undefined,
        role_name: String(u.role_name ?? ''),
        role_label: String(u.role_label ?? ''),
        display_name: String(u.display_name ?? ''),
        email: String(u.email ?? ''),
        username: u.username ? String(u.username) : undefined,
      }));
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    }
  }

  async function save(row: RoleRow) {
    error = '';
    msg = '';
    const body = {
      display_name: row.display_name.trim(),
      email: row.email.trim(),
    };
    if (!body.email) {
      error = 'Email is required.';
      return;
    }
    if (!body.display_name) {
      error = 'Display name is required.';
      return;
    }
    try {
      if (row.id) {
        await patchUser(row.id, body);
      } else {
        const updated = await upsertRoleUser(row.role_name, body);
        row.id = updated.id ? String(updated.id) : row.id;
        row.username = updated.username ? String(updated.username) : row.username;
      }
      msg = 'Saved.';
      await reload();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Save failed';
    }
  }
</script>
<h1>Key role emails</h1>
<p>Operational contacts for approvals and escalations (order matches org hierarchy).</p>
{#if error}<p class="err">{error}</p>{/if}
{#if msg}<p class="ok">{msg}</p>{/if}
{#each items as row, i}
  <div class="card">
    <strong>{row.role_label}</strong>
    {#if !row.id}
      <p class="hint">No login account yet — enter contact details and save to provision this role.</p>
    {/if}
    <label>Display name <input bind:value={items[i].display_name} /></label>
    <label>Email <input type="email" bind:value={items[i].email} /></label>
    {#if row.username}
      <p class="meta">Username: {row.username}</p>
    {/if}
    <button type="button" on:click={() => save(row)}>Save</button>
  </div>
{/each}
<style>
  .card { background: #fff; border: 1px solid #e2e8f0; padding: 1rem; margin-bottom: 0.75rem; border-radius: 8px; }
  label { display: block; margin: 0.5rem 0; }
  input { width: 100%; padding: 0.4rem; box-sizing: border-box; }
  .meta { font-size: 0.8rem; color: #64748b; }
  .hint { color: #64748b; font-size: 0.875rem; }
  .err { color: #b91c1c; }
  .ok { color: #15803d; }
</style>
