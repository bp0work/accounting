<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch, ensureValidAccessToken } from '$lib/api/client';

  // ---- API contract types (mirror accfin/app/schemas/notification_api.py) ----

  type NotificationTemplate = {
    id: string;
    event_key: string;
    display_name: string;
    description: string | null;
    default_email: boolean;
    default_in_app: boolean;
    user_overridable: boolean;
    sort_order: number;
  };

  type SubscriptionPreference = {
    event_key: string;
    email: boolean;
    in_app: boolean;
    digest: string;
  };

  type NotificationPreferences = {
    quiet_hours: Record<string, unknown>;
    channels: Record<string, boolean>;
    subscriptions: SubscriptionPreference[];
  };

  type EventDef = {
    key: string;
    label: string;
    description: string;
  };

  type EventGroup = {
    name: string;
    events: EventDef[];
  };

  // ---- Grouped event catalog (UI-side labels override raw event_key) ----

  const GROUPS: EventGroup[] = [
    {
      name: 'Approvals',
      events: [
        { key: 'approval.requested',    label: 'Approval requested',    description: 'A case requires your approval' },
        { key: 'approval.sla_at_risk',  label: 'Approval SLA at risk',  description: 'An approval is approaching its deadline' },
        { key: 'approval.escalated',    label: 'Approval escalated',    description: 'An approval was escalated up the binding-authority chain' },
        { key: 'approval.approved',     label: 'Approval approved',     description: 'An approval you requested or are watching was approved' },
        { key: 'approval.rejected',     label: 'Approval rejected',     description: 'An approval you requested or are watching was rejected' },
      ],
    },
    {
      name: 'Cases',
      events: [
        { key: 'case.assigned',        label: 'Case assigned',        description: 'A case was assigned to you' },
        { key: 'case.status_changed',  label: 'Case status changed',  description: 'A case you watch moved to a new status' },
      ],
    },
    {
      name: 'Expense claims',
      events: [
        { key: 'expense.claim.submitted', label: 'Expense claim submitted', description: 'A new expense claim was submitted' },
        { key: 'expense.claim.approved',  label: 'Expense claim approved',  description: 'An expense claim was approved' },
        { key: 'expense.claim.rejected',  label: 'Expense claim rejected',  description: 'An expense claim was rejected' },
      ],
    },
    {
      name: 'Reports & digests',
      events: [
        { key: 'finance.daily_log', label: 'Daily finance digest', description: 'Daily 9pm SGT activity summary CSV' },
      ],
    },
    {
      name: 'Escalations',
      events: [
        { key: 'manager.escalation.request',        label: 'Manager escalation request',  description: 'A case was escalated to your queue for binding-authority approval' },
        { key: 'manager.outbound.approval.request', label: 'Outbound client email approval', description: 'A drafted client clarification email is waiting for your approval' },
      ],
    },
  ];

  const GROUPED_KEYS = new Set(GROUPS.flatMap((g) => g.events.map((e) => e.key)));

  // ---- Page state ----

  let loading = true;
  let saving = false;
  let error = '';
  let msg = '';

  let templatesByKey: Record<string, NotificationTemplate> = {};

  // Global channel toggles
  let globalEmail = true;
  let globalInApp = true;

  // Quiet hours
  let quietEnabled = false;
  let quietStart = '22:00';
  let quietEnd = '07:00';

  // Per-event subscription state
  let subs: Record<string, { email: boolean; in_app: boolean }> = {};

  // Computed: events from the catalog that are not in our group definitions
  let otherEvents: EventDef[] = [];

  onMount(async () => {
    if (!(await ensureValidAccessToken())) {
      error = 'Not signed in';
      loading = false;
      return;
    }
    try {
      const [templates, prefs] = await Promise.all([
        apiFetch<NotificationTemplate[]>('/notification-templates'),
        apiFetch<NotificationPreferences>('/users/me/notification-preferences'),
      ]);

      templatesByKey = Object.fromEntries(templates.map((t) => [t.event_key, t]));

      // Global channels — default true if prefs don't say otherwise
      globalEmail = prefs.channels?.email !== false;
      globalInApp = prefs.channels?.in_app !== false;

      // Quiet hours — backend stores free-form dict; we use {enabled, start, end}
      const qh = (prefs.quiet_hours ?? {}) as Record<string, unknown>;
      quietEnabled = qh.enabled === true;
      quietStart = typeof qh.start === 'string' ? (qh.start as string) : '22:00';
      quietEnd = typeof qh.end === 'string' ? (qh.end as string) : '07:00';

      // Build a lookup of saved subscriptions by event_key for overlay
      const savedByKey: Record<string, SubscriptionPreference> = {};
      for (const s of prefs.subscriptions ?? []) savedByKey[s.event_key] = s;

      // Seed subs from template defaults, then overlay user-saved values
      const next: Record<string, { email: boolean; in_app: boolean }> = {};
      for (const t of templates) {
        if (!t.user_overridable) continue;
        const saved = savedByKey[t.event_key];
        next[t.event_key] = {
          email: saved ? !!saved.email : !!t.default_email,
          in_app: saved ? !!saved.in_app : !!t.default_in_app,
        };
      }
      subs = next;

      // Anything in the catalog (user_overridable) that we don't have in GROUPS
      // gets put into an "Other notifications" group so the user can still
      // control it. Falls back to template display_name + description.
      otherEvents = templates
        .filter((t) => t.user_overridable && !GROUPED_KEYS.has(t.event_key))
        .sort((a, b) => a.sort_order - b.sort_order)
        .map((t) => ({
          key: t.event_key,
          label: t.display_name,
          description: t.description ?? '',
        }));
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    } finally {
      loading = false;
    }
  });

  function ensureRow(key: string): { email: boolean; in_app: boolean } {
    if (!subs[key]) {
      const t = templatesByKey[key];
      subs[key] = {
        email: t ? !!t.default_email : true,
        in_app: t ? !!t.default_in_app : true,
      };
      subs = subs;
    }
    return subs[key];
  }

  function isAvailable(key: string): boolean {
    const t = templatesByKey[key];
    return !!t && t.user_overridable;
  }

  async function save() {
    saving = true;
    error = '';
    msg = '';
    try {
      const subscriptions: SubscriptionPreference[] = Object.entries(subs).map(
        ([event_key, v]) => ({
          event_key,
          email: !!v.email,
          in_app: !!v.in_app,
          digest: 'off',
        })
      );
      const quiet_hours = quietEnabled
        ? { enabled: true, start: quietStart, end: quietEnd, timezone: 'Asia/Singapore' }
        : {};
      await apiFetch('/users/me/notification-preferences', {
        method: 'PUT',
        body: JSON.stringify({
          quiet_hours,
          channels: { email: globalEmail, in_app: globalInApp },
          subscriptions,
        }),
      });
      msg = 'Preferences saved.';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Save failed';
    } finally {
      saving = false;
    }
  }

  // Effective table interactivity: an event toggle is disabled when the
  // corresponding global channel is OFF (because it can't fire anyway).
  $: emailColumnEnabled = globalEmail;
  $: inAppColumnEnabled = globalInApp;
</script>

<h1>Notification preferences</h1>

{#if error}<p class="err">{error}</p>{/if}
{#if msg}<p class="ok">{msg}</p>{/if}

{#if loading}
  <p class="hint">Loading preferences…</p>
{:else}
  <!-- ===== Global settings panel ===== -->
  <section class="card global">
    <h2>Global settings</h2>
    <p class="hint">
      Master switches and quiet hours apply across every event below.
      When a global channel is off, individual event toggles for that channel are disabled.
    </p>

    <div class="row">
      <label class="toggle-line">
        <input type="checkbox" bind:checked={globalEmail} />
        <span class="toggle-label">Email notifications</span>
        <span class="toggle-sub">Send to the address on your user profile.</span>
      </label>
    </div>

    <div class="row">
      <label class="toggle-line">
        <input type="checkbox" bind:checked={globalInApp} />
        <span class="toggle-label">In-app notifications</span>
        <span class="toggle-sub">Show in the bell / inbox inside this app.</span>
      </label>
    </div>

    <div class="row quiet">
      <label class="toggle-line">
        <input type="checkbox" bind:checked={quietEnabled} />
        <span class="toggle-label">Quiet hours</span>
        <span class="toggle-sub">No email or in-app notifications during this window (Asia/Singapore).</span>
      </label>
      <div class="quiet-inputs" class:disabled={!quietEnabled}>
        <label>
          Start
          <input type="time" bind:value={quietStart} disabled={!quietEnabled} />
        </label>
        <label>
          End
          <input type="time" bind:value={quietEnd} disabled={!quietEnabled} />
        </label>
        <span class="tz">SGT</span>
      </div>
    </div>
  </section>

  <!-- ===== Per-event subscription tables ===== -->
  {#each GROUPS as group (group.name)}
    {@const rows = group.events.filter((e) => isAvailable(e.key))}
    {#if rows.length > 0}
      <section class="card">
        <h2>{group.name}</h2>
        <table>
          <thead>
            <tr>
              <th>Event</th>
              <th>Description</th>
              <th class="ch-col">Email</th>
              <th class="ch-col">In-app</th>
            </tr>
          </thead>
          <tbody>
            {#each rows as ev (ev.key)}
              {@const row = ensureRow(ev.key)}
              <tr>
                <td class="ev-name">{ev.label}</td>
                <td class="ev-desc">{ev.description}</td>
                <td class="ch-col">
                  <input
                    type="checkbox"
                    bind:checked={row.email}
                    disabled={!emailColumnEnabled}
                    aria-label="Email — {ev.label}"
                  />
                </td>
                <td class="ch-col">
                  <input
                    type="checkbox"
                    bind:checked={row.in_app}
                    disabled={!inAppColumnEnabled}
                    aria-label="In-app — {ev.label}"
                  />
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </section>
    {/if}
  {/each}

  {#if otherEvents.length > 0}
    <section class="card">
      <h2>Other notifications</h2>
      <p class="hint">Events present in the server catalog that aren't yet grouped.</p>
      <table>
        <thead>
          <tr>
            <th>Event</th>
            <th>Description</th>
            <th class="ch-col">Email</th>
            <th class="ch-col">In-app</th>
          </tr>
        </thead>
        <tbody>
          {#each otherEvents as ev (ev.key)}
            {@const row = ensureRow(ev.key)}
            <tr>
              <td class="ev-name">{ev.label}</td>
              <td class="ev-desc">{ev.description}</td>
              <td class="ch-col">
                <input
                  type="checkbox"
                  bind:checked={row.email}
                  disabled={!emailColumnEnabled}
                  aria-label="Email — {ev.label}"
                />
              </td>
              <td class="ch-col">
                <input
                  type="checkbox"
                  bind:checked={row.in_app}
                  disabled={!inAppColumnEnabled}
                  aria-label="In-app — {ev.label}"
                />
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>
  {/if}

  <!-- ===== Save bar ===== -->
  <div class="save-bar">
    <button type="button" class="primary" on:click={save} disabled={saving}>
      {saving ? 'Saving…' : 'Save preferences'}
    </button>
  </div>
{/if}

<style>
  h1 { margin: 0 0 0.5rem; }
  h2 { font-size: 1rem; margin: 0 0 0.5rem; color: #1e293b; }
  .card {
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 1rem;
  }
  .global { border-left: 4px solid #2563eb; }
  .hint {
    font-size: 0.875rem;
    color: #475569;
    margin: 0 0 0.75rem;
  }
  .row {
    border-top: 1px solid #f1f5f9;
    padding-top: 0.75rem;
    margin-top: 0.75rem;
  }
  .row:first-of-type { border-top: none; padding-top: 0; margin-top: 0.5rem; }
  .toggle-line {
    display: grid;
    grid-template-columns: auto 1fr;
    column-gap: 0.6rem;
    row-gap: 0.15rem;
    align-items: start;
    cursor: pointer;
  }
  .toggle-line input[type="checkbox"] { width: 18px; height: 18px; margin-top: 0.15rem; grid-row: span 2; }
  .toggle-label { font-weight: 600; color: #0f172a; font-size: 0.9rem; }
  .toggle-sub { font-size: 0.8rem; color: #64748b; }
  .quiet-inputs {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    margin: 0.5rem 0 0 1.6rem;
    align-items: end;
    font-size: 0.85rem;
  }
  .quiet-inputs label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.8rem; color: #475569; }
  .quiet-inputs input[type="time"] {
    padding: 0.3rem 0.4rem;
    font-size: 0.9rem;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    background: #fff;
  }
  .quiet-inputs.disabled { opacity: 0.5; }
  .tz { font-size: 0.75rem; color: #64748b; padding-bottom: 0.4rem; }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }
  thead { background: #f8fafc; }
  th, td {
    text-align: left;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid #f1f5f9;
    vertical-align: middle;
  }
  th { font-weight: 600; color: #334155; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.03em; }
  tbody tr:last-child td { border-bottom: none; }
  th.ch-col, td.ch-col {
    width: 5.5rem;
    text-align: center;
  }
  .ev-name { font-weight: 600; color: #0f172a; white-space: nowrap; }
  .ev-desc { color: #475569; }
  input[type="checkbox"] { width: 16px; height: 16px; accent-color: #2563eb; cursor: pointer; }
  input[type="checkbox"]:disabled { cursor: not-allowed; }
  .save-bar {
    display: flex;
    justify-content: flex-end;
    padding: 0.75rem 0 2rem;
  }
  button.primary {
    padding: 0.55rem 1.25rem;
    font-size: 0.95rem;
    background: #2563eb;
    color: #fff;
    border: 1px solid #1d4ed8;
    border-radius: 6px;
    cursor: pointer;
  }
  button.primary:disabled { background: #94a3b8; border-color: #94a3b8; cursor: not-allowed; }
  .err { color: #b91c1c; font-size: 0.875rem; }
  .ok  { color: #15803d; font-size: 0.875rem; }
</style>
