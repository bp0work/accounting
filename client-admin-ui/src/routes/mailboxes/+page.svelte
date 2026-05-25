<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { listMailboxes, patchMailbox } from '$lib/api/admin';
  let items: Array<Record<string, unknown>> = [];
  let error = '';
  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    try {
      items = await listMailboxes();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    }
  });
  async function save(m: Record<string, unknown>) {
    await patchMailbox(String(m.id), {
      display_name: m.display_name,
      escalation_manager_email: m.escalation_manager_email,
    });
  }
</script>
<h1>Mailboxes</h1>
<p>IMAP/SMTP credentials are masked and not editable here.</p>
{#if error}<p class="err">{error}</p>{/if}
{#each items as m}
  <div class="card">
    <strong>{m.email_address}</strong> — {m.mailbox_mode}
    <label>Display name <input bind:value={m.display_name} /></label>
    <label>Escalation email <input bind:value={m.escalation_manager_email} /></label>
    <p class="meta">User: {m.username_masked} · Host: {m.server_host}</p>
    <button type="button" on:click={() => save(m)}>Save</button>
  </div>
{/each}
<style>
  .card { background: #fff; border: 1px solid #e2e8f0; padding: 1rem; margin-bottom: 0.75rem; border-radius: 8px; }
  label { display: block; margin: 0.5rem 0; }
  input { width: 100%; padding: 0.4rem; box-sizing: border-box; }
  .meta { font-size: 0.8rem; color: #64748b; }
  .err { color: #b91c1c; }
</style>
