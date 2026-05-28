<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import {
    createGlCutoffReminder,
    deleteGlCutoffReminder,
    generateAccountingPeriods,
    getAccountingSettings,
    listGlCutoffReminders,
    patchAccountingSettings,
    patchGlCutoffReminder,
    type AccountingSettings,
    type GlCutoffReminder,
  } from '$lib/api/admin';

  const MONTHS = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];

  let loading = true;
  let saving = false;
  let generating = false;
  let msg = '';
  let error = '';
  let reminders: GlCutoffReminder[] = [];
  let showAddRecipient = false;
  let newRecipient = {
    display_name: '',
    email: '',
    notify_7_days: true,
    notify_3_days: true,
    notify_1_day: true,
    notify_on_date: true,
    is_active: true,
  };

  let settings: AccountingSettings = {
    accounting_fye_month: 12,
    trial_balance_frequency: 'monthly',
    audit_frequency: 'annual',
    gl_cutoff_working_days: 3,
    accounting_start_date: null,
  };

  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    try {
      settings = await getAccountingSettings();
      reminders = await listGlCutoffReminders();
      if (!settings.accounting_start_date) {
        settings.accounting_start_date = '2025-04-01';
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    } finally {
      loading = false;
    }
  });

  function monthLabel(isoDate: string | null): string {
    if (!isoDate) return 'start month';
    const [year, month] = isoDate.split('-');
    const idx = Number(month) - 1;
    return `${MONTHS[idx] ?? month} ${year}`;
  }

  async function saveSettings() {
    saving = true;
    msg = '';
    error = '';
    try {
      settings = await patchAccountingSettings({
        accounting_start_date: settings.accounting_start_date,
        accounting_fye_month: settings.accounting_fye_month,
        trial_balance_frequency: settings.trial_balance_frequency,
        audit_frequency: settings.audit_frequency,
        gl_cutoff_working_days: settings.gl_cutoff_working_days,
      });
      msg = 'Calendar settings saved.';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Save failed';
    } finally {
      saving = false;
    }
  }

  async function generateFromConfigured() {
    generating = true;
    msg = '';
    error = '';
    try {
      await generateAccountingPeriods();
      msg = settings.accounting_start_date
        ? `Generated periods from ${monthLabel(settings.accounting_start_date)} to current month + 12 months (skipping existing).`
        : 'Generated periods for current month + 12 months (skipping existing).';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Generate failed';
    } finally {
      generating = false;
    }
  }

  async function addRecipient() {
    await createGlCutoffReminder(newRecipient);
    showAddRecipient = false;
    newRecipient = {
      display_name: '',
      email: '',
      notify_7_days: true,
      notify_3_days: true,
      notify_1_day: true,
      notify_on_date: true,
      is_active: true,
    };
    reminders = await listGlCutoffReminders();
    msg = 'Recipient added.';
  }

  async function toggleReminder(r: GlCutoffReminder, field: keyof GlCutoffReminder) {
    const val = r[field];
    if (typeof val !== 'boolean') return;
    await patchGlCutoffReminder(r.id, { [field]: !val });
    reminders = await listGlCutoffReminders();
  }

  async function removeRecipient(r: GlCutoffReminder) {
    if (!confirm(`Remove reminder recipient ${r.email}?`)) return;
    await deleteGlCutoffReminder(r.id);
    reminders = await listGlCutoffReminders();
    msg = 'Recipient removed.';
  }
</script>

<h1>Accounting calendar</h1>
<p class="hint">Configure calendar settings, generate periods, and manage GL cutoff reminders.</p>

{#if error}<p class="err">{error}</p>{/if}
{#if msg}<p class="ok">{msg}</p>{/if}

{#if loading}
  <p>Loading…</p>
{:else}
  <section class="card">
    <h2>Calendar settings</h2>
    <div class="grid">
      <label>
        Company accounting start date
        <input type="date" bind:value={settings.accounting_start_date} />
        <span class="hint small">
          The month your company started operations or began using this system.
          For mmlogistix use <strong>2025-04-01</strong>.
        </span>
      </label>
      <label>Financial year end month
        <select bind:value={settings.accounting_fye_month}>
          {#each MONTHS as name, i}
            <option value={i + 1}>{name}</option>
          {/each}
        </select>
      </label>
      <label>Trial balance review frequency
        <select bind:value={settings.trial_balance_frequency}>
          <option value="monthly">Monthly</option>
          <option value="weekly">Weekly</option>
        </select>
      </label>
      <label>Audit frequency
        <select bind:value={settings.audit_frequency}>
          <option value="annual">Annual only</option>
          <option value="semi_annual">Semi-annual</option>
          <option value="quarterly">Quarterly</option>
        </select>
      </label>
      <label>GL cutoff working days
        <input type="number" min="1" max="30" bind:value={settings.gl_cutoff_working_days} />
      </label>
    </div>
    <button type="button" on:click={saveSettings} disabled={saving}>
      {saving ? 'Saving…' : 'Save settings'}
    </button>
  </section>

  <section class="card">
    <h2>Generate periods</h2>
    <button type="button" on:click={generateFromConfigured} disabled={generating}>
      {generating ? 'Generating…' : `Generate all periods from ${monthLabel(settings.accounting_start_date)}`}
    </button>
    <p class="hint">Existing periods are skipped, so no duplicates are created.</p>
  </section>

  <section class="card recipients">
    <h2>GL cutoff reminder recipients</h2>
    <p class="hint">Daily cron emails at 7 / 3 / 1 days before cutoff and on cutoff date (08:00 SGT).</p>
    {#if reminders.length === 0 && !showAddRecipient}
      <p class="warn">No reminder recipients configured. Add recipients to receive GL cutoff notifications.</p>
    {/if}
    {#if reminders.length > 0}
      <table>
        <thead>
          <tr>
            <th>Name</th><th>Email</th><th>7d</th><th>3d</th><th>1d</th><th>On date</th><th>Active</th><th></th>
          </tr>
        </thead>
        <tbody>
          {#each reminders as r}
            <tr>
              <td>{r.display_name || '—'}</td>
              <td>{r.email}</td>
              <td><input type="checkbox" checked={r.notify_7_days} on:change={() => toggleReminder(r, 'notify_7_days')} /></td>
              <td><input type="checkbox" checked={r.notify_3_days} on:change={() => toggleReminder(r, 'notify_3_days')} /></td>
              <td><input type="checkbox" checked={r.notify_1_day} on:change={() => toggleReminder(r, 'notify_1_day')} /></td>
              <td><input type="checkbox" checked={r.notify_on_date} on:change={() => toggleReminder(r, 'notify_on_date')} /></td>
              <td><input type="checkbox" checked={r.is_active} on:change={() => toggleReminder(r, 'is_active')} /></td>
              <td><button type="button" class="danger" on:click={() => removeRecipient(r)}>Delete</button></td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
    {#if showAddRecipient}
      <div class="add-form">
        <label>Display name <input bind:value={newRecipient.display_name} /></label>
        <label>Email <input type="email" bind:value={newRecipient.email} required /></label>
        <label><input type="checkbox" bind:checked={newRecipient.notify_7_days} /> 7 days before</label>
        <label><input type="checkbox" bind:checked={newRecipient.notify_3_days} /> 3 days before</label>
        <label><input type="checkbox" bind:checked={newRecipient.notify_1_day} /> 1 day before</label>
        <label><input type="checkbox" bind:checked={newRecipient.notify_on_date} /> On cutoff date</label>
        <button type="button" on:click={addRecipient}>Save recipient</button>
        <button type="button" class="muted" on:click={() => (showAddRecipient = false)}>Cancel</button>
      </div>
    {:else}
      <button type="button" on:click={() => (showAddRecipient = true)}>Add recipient</button>
    {/if}
  </section>
{/if}

<style>
  .card { border: 1px solid #e2e8f0; border-radius: 8px; background: #fff; padding: 1rem; margin-bottom: 1rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.75rem; margin-bottom: 0.75rem; }
  label { display: block; margin-bottom: 0.5rem; font-size: 0.875rem; }
  input, select { width: 100%; max-width: 320px; padding: 0.45rem; margin-top: 0.25rem; box-sizing: border-box; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 0.75rem; }
  th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid #e2e8f0; font-size: 0.875rem; }
  .hint { color: #64748b; font-size: 0.875rem; }
  .small { display: block; margin-top: 0.35rem; }
  .warn { color: #b45309; }
  .ok { color: #15803d; }
  .err { color: #b91c1c; }
  .danger { color: #b91c1c; }
  .muted { background: #f1f5f9; }
  .add-form { margin-top: 0.75rem; }
</style>
