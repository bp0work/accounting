<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { fetchTenantProfile, patchTenantProfile } from '$lib/api/admin';
  let p: Record<string, unknown> = {};
  let msg = '';
  let error = '';
  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    try {
      p = await fetchTenantProfile();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    }
  });
  async function save() {
    msg = '';
    error = '';
    try {
      p = await patchTenantProfile(p);
      msg = 'Saved.';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Save failed';
    }
  }
</script>
<h1>Company profile</h1>
{#if error}<p class="err">{error}</p>{/if}
{#if msg}<p class="ok">{msg}</p>{/if}
<form on:submit|preventDefault={save} class="card">
  <label>Legal name <input bind:value={p.legal_name} /></label>
  <label>Trading name <input bind:value={p.trading_name} /></label>
  <label>UEN <input bind:value={p.uen} /></label>
  <label>GST registration <input bind:value={p.gst_registration_number} /></label>
  <label>Registered address <textarea bind:value={p.registered_address}></textarea></label>
  <label>Contact email <input bind:value={p.contact_email} /></label>
  <label>Phone <input bind:value={p.contact_phone} /></label>
  <label>Website <input bind:value={p.website} /></label>
  <button type="submit">Save</button>
</form>
<style>
  label { display: block; margin-bottom: 0.75rem; }
  input, textarea { width: 100%; padding: 0.5rem; box-sizing: border-box; }
  .card { background: #fff; border: 1px solid #e2e8f0; padding: 1rem; border-radius: 8px; }
  .err { color: #b91c1c; } .ok { color: #15803d; }
</style>
