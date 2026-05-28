<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import {
    listMailboxes,
    patchMailbox,
    type MailboxConfig,
    type MailboxConfigUpdate,
  } from '$lib/api/admin';

  type Row = MailboxConfig & {
    display_name_input: string;
    escalation_input: string;
    require_parsing_confirmation: boolean;
    require_parsing_confirmation_saved: boolean;
    saving: boolean;
  };

  let rows: Row[] = [];
  let error = '';
  let msg = '';
  let loading = true;

  $: executives = rows.filter((m) => m.mailbox_mode === 'executive_agent');
  $: managers = rows.filter((m) => m.mailbox_mode === 'manager_human');

  onMount(async () => {
    if (!(await ensureValidAccessToken())) {
      error = 'Not signed in';
      loading = false;
      return;
    }
    await reload();
  });

  async function reload() {
    error = '';
    loading = true;
    try {
      const items = await listMailboxes();
      rows = items
        .slice()
        .sort(sortMailboxes)
        .map((m) => ({
          ...m,
          display_name_input: m.display_name ?? '',
          escalation_input: m.escalation_manager_email ?? '',
          require_parsing_confirmation: Boolean(m.require_parsing_confirmation),
          require_parsing_confirmation_saved: Boolean(m.require_parsing_confirmation),
          saving: false,
        }));
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    } finally {
      loading = false;
    }
  }

  function sortMailboxes(a: MailboxConfig, b: MailboxConfig): number {
    const order = (m: MailboxConfig) => (m.mailbox_mode === 'executive_agent' ? 0 : 1);
    const cmp = order(a) - order(b);
    if (cmp !== 0) return cmp;
    return a.email_address.localeCompare(b.email_address);
  }

  function typeLabel(mode: string): string {
    if (mode === 'executive_agent') return 'Executive Agent';
    if (mode === 'manager_human') return 'Manager';
    return mode;
  }

  function showParsingToggle(row: Row): boolean {
    if (row.mailbox_mode !== 'executive_agent') return false;
    const addr = row.email_address.toLowerCase();
    return (
      addr.startsWith('accap.') ||
      addr.startsWith('accar.') ||
      addr.startsWith('accexp.')
    );
  }

  function rowIsDirty(row: Row): boolean {
    const dn = row.display_name_input.trim();
    const es = row.escalation_input.trim();
    const currentDn = (row.display_name ?? '').trim();
    const currentEs = (row.escalation_manager_email ?? '').trim();
    const parsingDirty =
      showParsingToggle(row) &&
      row.require_parsing_confirmation !== row.require_parsing_confirmation_saved;
    return dn !== currentDn || es !== currentEs || parsingDirty;
  }

  async function save(row: Row) {
    if (!rowIsDirty(row)) {
      msg = 'No changes for ' + row.email_address;
      return;
    }
    error = '';
    msg = '';
    row.saving = true;
    rows = rows;
    const body: MailboxConfigUpdate = {};
    const dn = row.display_name_input.trim();
    const es = row.escalation_input.trim();
    if (dn !== (row.display_name ?? '').trim()) body.display_name = dn;
    if (es !== (row.escalation_manager_email ?? '').trim()) {
      body.escalation_manager_email = es || null;
    }
    if (
      showParsingToggle(row) &&
      row.require_parsing_confirmation !== row.require_parsing_confirmation_saved
    ) {
      body.require_parsing_confirmation = row.require_parsing_confirmation;
    }
    try {
      const updated = await patchMailbox(row.id, body);
      row.display_name = updated.display_name;
      row.escalation_manager_email = updated.escalation_manager_email;
      row.display_name_input = updated.display_name ?? '';
      row.escalation_input = updated.escalation_manager_email ?? '';
      row.require_parsing_confirmation = Boolean(updated.require_parsing_confirmation);
      row.require_parsing_confirmation_saved = row.require_parsing_confirmation;
      msg = 'Saved ' + row.email_address;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Save failed';
    } finally {
      row.saving = false;
      rows = rows;
    }
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

{#if loading}
  <p class="empty">Loading mailboxes…</p>
{:else}
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
            <th>Parsing confirm</th>
            <th>Active</th>
            <th class="actions-col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each executives as row, i (row.id)}
            {@const idx = rows.indexOf(row)}
            <tr>
              <td class="addr">
                <code>{row.email_address}</code>
                {#if row.role}<div class="role">{row.role}</div>{/if}
              </td>
              <td><span class="badge type">{typeLabel(row.mailbox_mode)}</span></td>
              <td>
                <input type="text" bind:value={rows[idx].display_name_input} />
              </td>
              <td>
                <input
                  type="email"
                  placeholder="manager@bp0.work"
                  bind:value={rows[idx].escalation_input}
                />
              </td>
              <td class="parsing-col">
                {#if showParsingToggle(row)}
                  <label class="toggle">
                    <input
                      type="checkbox"
                      bind:checked={rows[idx].require_parsing_confirmation}
                    />
                    Require parsing confirmation
                  </label>
                {:else}
                  <span class="muted">—</span>
                {/if}
              </td>
              <td>
                <span class="badge {row.is_active ? 'active' : 'inactive'}"
                  >{row.is_active ? 'Active' : 'Inactive'}</span
                >
              </td>
              <td class="actions-col">
                <button
                  type="button"
                  on:click={() => save(row)}
                  disabled={row.saving || !rowIsDirty(row)}
                  >{row.saving ? 'Saving…' : 'Save'}</button
                >
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
          {#each managers as row, i (row.id)}
            {@const idx = rows.indexOf(row)}
            <tr>
              <td class="addr">
                <code>{row.email_address}</code>
                {#if row.role}<div class="role">{row.role}</div>{/if}
              </td>
              <td><span class="badge type">{typeLabel(row.mailbox_mode)}</span></td>
              <td>
                <input type="text" bind:value={rows[idx].display_name_input} />
              </td>
              <td>
                <input
                  type="email"
                  placeholder="manager@bp0.work"
                  bind:value={rows[idx].escalation_input}
                />
              </td>
              <td>
                <span class="badge {row.is_active ? 'active' : 'inactive'}"
                  >{row.is_active ? 'Active' : 'Inactive'}</span
                >
              </td>
              <td class="actions-col">
                <button
                  type="button"
                  on:click={() => save(row)}
                  disabled={row.saving || !rowIsDirty(row)}
                  >{row.saving ? 'Saving…' : 'Save'}</button
                >
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>
{/if}

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
  .parsing-col .toggle {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.85rem;
    white-space: nowrap;
  }
  .parsing-col .muted {
    color: #94a3b8;
  }
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
