<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { listRoleUsers, patchUser } from '$lib/api/admin';
  let items: Array<Record<string, unknown>> = [];
  let error = '';
  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    try {
      items = await listRoleUsers();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    }
  });
  async function save(u: Record<string, unknown>) {
    await patchUser(String(u.id), { email: u.email, display_name: u.display_name });
  }
</script>
<h1>Key role emails</h1>
{#if error}<p class="err">{error}</p>{/if}
{#each items as u}
  <div class="card">
    <strong>{u.role_label}</strong>
    <label>Display name <input bind:value={u.display_name} /></label>
    <label>Email <input bind:value={u.email} /></label>
    <button type="button" on:click={() => save(u)}>Save</button>
  </div>
{/each}
