<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { listMailboxes, patchMailbox } from '$lib/api/admin';
  let items: Array<Record<string, unknown>> = [];
  let error = '';
  let msg = '';
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
    msg = 'Saved.';
  }
</script>
<h1>Mailboxes</h1>
<div class="notice">
  <strong>IMAP/SMTP credentials</strong> are stored encrypted and are not shown or editable in this UI.
  To rotate mailbox passwords or server settings, contact the <strong>platform administrator</strong>.
  You can update display names and escalation manager emails below.
</div>
{#if error}<p class="err">{error}</p>{/if}
{#if msg}<p class="ok">{msg}</p>{/if}
{#each items as m}
  <div class="card">
    <strong>{m.email_address}</strong> — {m.mailbox_mode} ({m.role || '—'})
    <label>Display name <input bind:value={m.display_name} /></label>
    <label>Escalation email <input bind:value={m.escalation_manager_email} /></label>
    <p class="meta">Login: {m.username_masked} · Host: {m.server_host}</p>
    <button type="button" on:click={() => save(m)}>Save</button>
  </div>
{/each}
<style>
  .notice { background: #f0f9ff; border: 1px solid #bae6fd; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; font-size: 0.9rem; }
  .card { background: #fff; border: 1px solid #e2e8f0; padding: 1rem; margin-bottom: 0.75rem; border-radius: 8px; }
  label { display: block; margin: 0.5rem 0; }
  input { width: 100%; padding: 0.4rem; box-sizing: border-box; }
  .meta { font-size: 0.8rem; color: #64748b; }
  .err { color: #b91c1c; }
  .ok { color: #15803d; }
</style>
