<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import {
    listAccountingPeriods,
    generateAccountingPeriods,
    approveTrialBalance,
    closeGlPeriod,
    reopenGlPeriod,
    getAccountingSettings,
    patchAccountingSettings,
    listGlCutoffReminders,
    createGlCutoffReminder,
    patchGlCutoffReminder,
    deleteGlCutoffReminder,
    type AccountingSettings,
    type GlCutoffReminder,
  } from '$lib/api/admin';

  const MONTHS = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];

  let settings: AccountingSettings = {
    accounting_fye_month: 12,
    trial_balance_frequency: 'monthly',
    audit_frequency: 'annual',
    gl_cutoff_working_days: 3,
  };
  let periods: Array<Record<string, unknown>> = [];
  let reminders: GlCutoffReminder[] = [];
  let msg = '';
  let error = '';
  let loading = false;
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
  let closeTarget: Record<string, unknown> | null = null;
  let reopenTarget: Record<string, unknown> | null = null;
  let closeForm = {
    audit_adjustments_completed: false,
    year_end_adjustments_completed: false,
    auditor_name: '',
    auditor_firm: '',
    sign_off_date: '',
  };

  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    await refreshAll();
  });

  async function refreshAll() {
    settings = await getAccountingSettings();
    await refresh();
    reminders = await listGlCutoffReminders();
  }

  async function refresh() {
    periods = await listAccountingPeriods();
    periods.sort((a, b) => {
      const ay = Number(a.period_year);
      const am = Number(a.period_month);
      const by = Number(b.period_year);
      const bm = Number(b.period_month);
      return ay !== by ? by - ay : bm - am;
    });
  }

  async function saveSettings() {
    error = '';
    try {
      settings = await patchAccountingSettings(settings);
      msg = 'Settings saved.';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Save failed';
    }
  }

  async function gen() {
    loading = true;
    error = '';
    try {
      await generateAccountingPeriods(13);
      msg = 'Generated periods for current month and the next 12 months.';
      await refresh();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Generate failed';
    } finally {
      loading = false;
    }
  }

  async function approve(id: string) {
    await approveTrialBalance(id);
    msg = 'Trial balance approved.';
    await refresh();
  }

  function openClose(p: Record<string, unknown>) {
    closeTarget = p;
    closeForm = {
      audit_adjustments_completed: false,
      year_end_adjustments_completed: false,
      auditor_name: '',
      auditor_firm: '',
      sign_off_date: '',
    };
  }

  function openReopen(p: Record<string, unknown>) {
    reopenTarget = p;
  }

  async function confirmReopen() {
    if (!reopenTarget) return;
    error = '';
    try {
      await reopenGlPeriod(String(reopenTarget.id));
      msg = 'GL period reopened.';
      reopenTarget = null;
      await refresh();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Reopen failed';
    }
  }

  async function confirmClose() {
    if (!closeTarget) return;
    const ptype = String(closeTarget.period_type);
    try {
      await closeGlPeriod(String(closeTarget.id), {
        audit_adjustments_completed:
          ptype === 'audit' ? closeForm.audit_adjustments_completed : undefined,
        year_end_adjustments_completed:
          ptype === 'year_end' ? closeForm.year_end_adjustments_completed : undefined,
        auditor_name: closeForm.auditor_name || undefined,
        auditor_firm: closeForm.auditor_firm || undefined,
        sign_off_date: closeForm.sign_off_date || undefined,
      });
      msg = 'GL period closed.';
      closeTarget = null;
      await refresh();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Close failed';
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

  function periodLabel(p: Record<string, unknown>) {
    const m = Number(p.period_month);
    const y = Number(p.period_year);
    return `${MONTHS[m - 1] || m} ${y}`;
  }

  function typeBadge(ptype: string) {
    if (ptype === 'year_end') return { label: 'Year-end', class: 'year-end' };
    if (ptype === 'audit') return { label: 'Audit', class: 'audit' };
    return { label: 'Monthly', class: 'monthly' };
  }
</script>

<h1>Accounting calendar</h1>
{#if error}<p class="err">{error}</p>{/if}
{#if msg}<p class="ok">{msg}</p>{/if}

<section class="card">
  <h2>Calendar settings</h2>
  <div class="grid">
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
  <button type="button" on:click={saveSettings}>Save settings</button>
</section>

<button type="button" class="gen-btn" on:click={gen} disabled={loading}>
  {loading ? 'Generating…' : 'Generate periods (current + next 12 months)'}
</button>

<table>
  <thead>
    <tr>
      <th>Period</th>
      <th>Type</th>
      <th>GL cutoff</th>
      <th>TB reviewer</th>
      <th>Status</th>
      <th>Actions</th>
    </tr>
  </thead>
  <tbody>
    {#each periods as p}
      {@const badge = typeBadge(String(p.period_type || 'monthly'))}
      <tr>
        <td>{periodLabel(p)}</td>
        <td><span class="badge {badge.class}">{badge.label}</span></td>
        <td>{p.gl_cutoff_date}</td>
        <td>{p.trial_balance_reviewer}</td>
        <td><span class="status status-{p.status}">{p.status}</span></td>
        <td class="actions">
          {#if p.status === 'open'}
            <button type="button" on:click={() => approve(String(p.id))}>Approve TB</button>
          {:else if p.status === 'review'}
            <button type="button" on:click={() => openClose(p)}>Close GL</button>
          {:else if p.status === 'closed'}
            <button type="button" class="reopen" title="Reopen period" on:click={() => openReopen(p)}>🔓</button>
          {:else}
            —
          {/if}
        </td>
      </tr>
    {/each}
  </tbody>
</table>
{#if periods.length === 0}
  <p class="hint">No periods yet — save settings, then generate periods.</p>
{/if}

<section class="card recipients">
  <h2>GL cutoff reminder recipients</h2>
  <p class="hint">Daily cron emails at 7 / 3 / 1 days before cutoff and on cutoff date (08:00 SGT).</p>
  {#if reminders.length === 0 && !showAddRecipient}
    <p class="warn">No reminder recipients configured. Add recipients to receive GL cutoff notifications.</p>
  {/if}
  {#if reminders.length > 0}
    <table class="compact">
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

{#if reopenTarget}
  <div class="modal-backdrop" role="presentation">
    <div class="modal card">
      <h2>Reopen GL period</h2>
      <p>
        Are you sure you want to reopen {periodLabel(reopenTarget)}? This will allow new postings
        to this period. All previous postings will remain intact.
      </p>
      <div class="modal-actions">
        <button type="button" on:click={confirmReopen}>Reopen period</button>
        <button type="button" class="muted" on:click={() => (reopenTarget = null)}>Cancel</button>
      </div>
    </div>
  </div>
{/if}

{#if closeTarget}
  <div class="modal-backdrop" role="presentation">
    <div class="modal card">
      <h2>Close GL — {periodLabel(closeTarget)}</h2>
      <p>Trial balance must already be approved.</p>
      {#if closeTarget.period_type === 'audit'}
        <label><input type="checkbox" bind:checked={closeForm.audit_adjustments_completed} /> Audit adjustments completed</label>
      {/if}
      {#if closeTarget.period_type === 'year_end'}
        <label><input type="checkbox" bind:checked={closeForm.year_end_adjustments_completed} /> Year-end adjustments completed</label>
      {/if}
      <label>Auditor name <input bind:value={closeForm.auditor_name} /></label>
      <label>Auditor firm <input bind:value={closeForm.auditor_firm} /></label>
      <label>Sign-off date <input type="date" bind:value={closeForm.sign_off_date} /></label>
      <div class="modal-actions">
        <button type="button" on:click={confirmClose}>Confirm close</button>
        <button type="button" class="muted" on:click={() => (closeTarget = null)}>Cancel</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .card { background: #fff; border: 1px solid #e2e8f0; padding: 1rem; margin-bottom: 1rem; border-radius: 8px; }
  h2 { margin: 0 0 0.75rem; font-size: 1rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.75rem; }
  label { display: block; font-size: 0.875rem; }
  input, select { width: 100%; padding: 0.4rem; box-sizing: border-box; margin-top: 0.25rem; }
  .gen-btn { margin-bottom: 0.75rem; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid #e2e8f0; font-size: 0.9rem; }
  table.compact { font-size: 0.85rem; }
  .badge { font-size: 0.75rem; padding: 0.15rem 0.45rem; border-radius: 4px; }
  .badge.monthly { background: #dcfce7; color: #166534; }
  .badge.audit { background: #dbeafe; color: #1e40af; }
  .badge.year-end { background: #fee2e2; color: #991b1b; }
  .status { text-transform: capitalize; font-size: 0.8rem; }
  .status-open { color: #166534; }
  .status-review { color: #854d0e; }
  .status-closed { color: #64748b; }
  .hint { color: #64748b; font-size: 0.875rem; }
  .warn { color: #b45309; }
  .err { color: #b91c1c; }
  .ok { color: #15803d; }
  .danger { color: #b91c1c; }
  .muted { background: #f1f5f9; }
  .modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 50; }
  .modal { max-width: 420px; width: 90%; }
  .modal-actions { display: flex; gap: 0.5rem; margin-top: 1rem; }
  .reopen { font-size: 1.1rem; padding: 0.25rem 0.5rem; cursor: pointer; background: #f0fdf4; border: 1px solid #86efac; border-radius: 4px; }
  .recipients { margin-top: 1.5rem; }
  .add-form { margin-top: 0.75rem; }
</style>
