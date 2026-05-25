<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { listRoleUsers, patchUser } from '$lib/api/admin';
  let items: Array<Record<string, unknown>> = [];
  let error = '';
  let msg = '';
  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    try {
      items = await listRoleUsers();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    }
  });
  async function save(u: Record<string, unknown>) {
    if (!u.id) return;
    await patchUser(String(u.id), { email: u.email, display_name: u.display_name });
    msg = 'Saved.';
  }
</script>
<h1>Key role emails</h1>
<p>Operational contacts for approvals and escalations (order matches org hierarchy).</p>
{#if error}<p class="err">{error}</p>{/if}
{#if msg}<p class="ok">{msg}</p>{/if}
{#each items as u}
  <div class="card">
    <strong>{u.role_label}</strong>
    {#if !u.id}
      <p class="warn">No active user for this role — contact the platform administrator to provision the account.</p>
    {:else}
      <label>Display name <input bind:value={u.display_name} /></label>
      <label>Email <input type="email" bind:value={u.email} /></label>
      <p class="meta">Username: {u.username}</p>
      <button type="button" on:click={() => save(u)}>Save</button>
    {/if}
  </div>
{/each}
<style>
  .card { background: #fff; border: 1px solid #e2e8f0; padding: 1rem; margin-bottom: 0.75rem; border-radius: 8px; }
  label { display: block; margin: 0.5rem 0; }
  input { width: 100%; padding: 0.4rem; box-sizing: border-box; }
  .meta { font-size: 0.8rem; color: #64748b; }
  .warn { color: #b45309; font-size: 0.875rem; }
  .err { color: #b91c1c; }
  .ok { color: #15803d; }
</style>
