<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { listMailboxes, patchMailbox } from '$lib/api/admin';

  type Mailbox = {
    id: string;
    email_address: string;
    display_name: string | null;
    role: string | null;
    mailbox_mode: string;
    escalation_manager_email: string | null;
    is_active: boolean;
    username_masked?: string;
    server_host?: string;
  };

  let items: Mailbox[] = [];
  let error = '';
  let msg = '';
  let savingId = '';

  const dirty: Record<string, { display_name?: string; escalation_manager_email?: string }> = {};

  $: executives = items.filter((m) => m.mailbox_mode === 'executive_agent');
  $: managers = items.filter((m) => m.mailbox_mode === 'manager_human');

  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    try {
      const rows = await listMailboxes();
      items = (rows as Mailbox[]).slice().sort(sortMailboxes);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    }
  });

  function sortMailboxes(a: Mailbox, b: Mailbox): number {
    const order = (m: Mailbox) => {
      if (m.mailbox_mode === 'executive_agent') return 0;
      if (m.mailbox_mode === 'manager_human') return 1;
      return 2;
    };
    const cmp = order(a) - order(b);
    if (cmp !== 0) return cmp;
    return a.email_address.localeCompare(b.email_address);
  }

  function typeLabel(mode: string): string {
    if (mode === 'executive_agent') return 'Executive Agent';
    if (mode === 'manager_human') return 'Manager';
    return mode;
  }

  function onDisplayNameInput(m: Mailbox, value: string) {
    m.display_name = value;
    dirty[m.id] = { ...(dirty[m.id] ?? {}), display_name: value };
  }

  function onEscalationInput(m: Mailbox, value: string) {
    const normalised = value.trim();
    m.escalation_manager_email = normalised || null;
    dirty[m.id] = { ...(dirty[m.id] ?? {}), escalation_manager_email: normalised };
  }

  async function save(m: Mailbox) {
    const changes = dirty[m.id];
    if (!changes || Object.keys(changes).length === 0) {
      msg = 'No changes for ' + m.email_address;
      return;
    }
    savingId = m.id;
    msg = '';
    error = '';
    try {
      await patchMailbox(m.id, changes);
      delete dirty[m.id];
      msg = 'Saved ' + m.email_address;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Save failed';
    } finally {
      savingId = '';
    }
  }

  function isDirty(id: string): boolean {
    const d = dirty[id];
    return !!d && Object.keys(d).length > 0;
  }
</script>

<h1>Mailboxes</h1>

<p class="note">
  <strong>IMAP/SMTP credentials</strong> are stored encrypted and are not shown or editable here.
  To rotate mailbox passwords or server settings, contact the <strong>platform administrator</strong>.
  You can update display names and escalation manager emails below.
</p>

{#if error}<p class="err">{error}</p>{/if}
{#if msg}<p class="ok">{msg}</p>{/if}

<section>
  <h2>Executive Agent Mailboxes</h2>
  {#if executives.length === 0}
    <p class="empty">No executive agent mailboxes configured.</p>
  {:else}
    <table>
      <thead>
        <tr>
          <th>Mailbox address</th>
          <th>Type</th>
          <th>Display name</th>
          <th>Escalation email</th>
          <th>Active</th>
          <th class="actions-col">Actions</th>
        </tr>
      </thead>
      <tbody>
        {#each executives as m (m.id)}
          <tr>
            <td class="addr"><code>{m.email_address}</code>{#if m.role}<div class="role">{m.role}</div>{/if}</td>
            <td><span class="badge type">{typeLabel(m.mailbox_mode)}</span></td>
            <td>
              <input
                type="text"
                value={m.display_name ?? ''}
                on:input={(e) => onDisplayNameInput(m, (e.currentTarget as HTMLInputElement).value)}
              />
            </td>
            <td>
              <input
                type="email"
                value={m.escalation_manager_email ?? ''}
                placeholder="manager@bp0.work"
                on:input={(e) => onEscalationInput(m, (e.currentTarget as HTMLInputElement).value)}
              />
            </td>
            <td><span class="badge {m.is_active ? 'active' : 'inactive'}">{m.is_active ? 'Active' : 'Inactive'}</span></td>
            <td class="actions-col">
              <button
                type="button"
                on:click={() => save(m)}
                disabled={!isDirty(m.id) || savingId === m.id}
              >{savingId === m.id ? 'Saving…' : 'Save'}</button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</section>

<section>
  <h2>Manager Mailboxes</h2>
  {#if managers.length === 0}
    <p class="empty">No manager mailboxes configured.</p>
  {:else}
    <table>
      <thead>
        <tr>
          <th>Mailbox address</th>
          <th>Type</th>
          <th>Display name</th>
          <th>Escalation email</th>
          <th>Active</th>
          <th class="actions-col">Actions</th>
        </tr>
      </thead>
      <tbody>
        {#each managers as m (m.id)}
          <tr>
            <td class="addr"><code>{m.email_address}</code>{#if m.role}<div class="role">{m.role}</div>{/if}</td>
            <td><span class="badge type">{typeLabel(m.mailbox_mode)}</span></td>
            <td>
              <input
                type="text"
                value={m.display_name ?? ''}
                on:input={(e) => onDisplayNameInput(m, (e.currentTarget as HTMLInputElement).value)}
              />
            </td>
            <td>
              <input
                type="email"
                value={m.escalation_manager_email ?? ''}
                placeholder="manager@bp0.work"
                on:input={(e) => onEscalationInput(m, (e.currentTarget as HTMLInputElement).value)}
              />
            </td>
            <td><span class="badge {m.is_active ? 'active' : 'inactive'}">{m.is_active ? 'Active' : 'Inactive'}</span></td>
            <td class="actions-col">
              <button
                type="button"
                on:click={() => save(m)}
                disabled={!isDirty(m.id) || savingId === m.id}
              >{savingId === m.id ? 'Saving…' : 'Save'}</button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</section>

<style>
  h1 { margin: 0 0 0.5rem; }
  h2 { font-size: 1.05rem; margin: 1.25rem 0 0.5rem; color: #1e293b; }
  .note {
    font-size: 0.8rem;
    color: #475569;
    background: #f8fafc;
    border-left: 3px solid #94a3b8;
    padding: 0.5rem 0.75rem;
    margin: 0 0 1rem;
    border-radius: 4px;
  }
  section { margin-bottom: 1.5rem; }
  table {
    width: 100%;
    border-collapse: collapse;
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
    font-size: 0.875rem;
  }
  thead { background: #f1f5f9; }
  th, td {
    padding: 0.55rem 0.75rem;
    text-align: left;
    vertical-align: middle;
    border-bottom: 1px solid #e2e8f0;
  }
  tbody tr:last-child td { border-bottom: none; }
  th { font-weight: 600; color: #334155; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.03em; }
  .addr code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.85rem; color: #0f172a; }
  .role { font-size: 0.75rem; color: #64748b; margin-top: 0.15rem; }
  input[type="text"], input[type="email"] {
    width: 100%;
    padding: 0.35rem 0.5rem;
    font-size: 0.875rem;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    box-sizing: border-box;
  }
  input:focus { outline: 2px solid #2563eb; outline-offset: -1px; border-color: #2563eb; }
  .badge {
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    line-height: 1.4;
  }
  .badge.active { background: #dcfce7; color: #166534; }
  .badge.inactive { background: #fee2e2; color: #991b1b; }
  .badge.type { background: #e0e7ff; color: #3730a3; }
  .actions-col { width: 6.5rem; text-align: right; }
  button {
    padding: 0.35rem 0.85rem;
    font-size: 0.85rem;
    border: 1px solid #1d4ed8;
    background: #2563eb;
    color: #fff;
    border-radius: 4px;
    cursor: pointer;
  }
  button:disabled {
    background: #cbd5e1;
    border-color: #cbd5e1;
    color: #64748b;
    cursor: not-allowed;
  }
  .err { color: #b91c1c; font-size: 0.875rem; }
  .ok { color: #15803d; font-size: 0.875rem; }
  .empty { color: #64748b; font-size: 0.875rem; font-style: italic; }
</style>
