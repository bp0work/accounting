<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import {
    generateAccountingPeriods,
    getAccountingSettings,
    patchAccountingSettings,
    type AccountingSettings,
  } from '$lib/api/admin';

  let loading = true;
  let saving = false;
  let generating = false;
  let msg = '';
  let error = '';
  let specificMonth = '';

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
      if (!settings.accounting_start_date) {
        // mmlogistix default requested by ops.
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
    const names = [
      'January',
      'February',
      'March',
      'April',
      'May',
      'June',
      'July',
      'August',
      'September',
      'October',
      'November',
      'December',
    ];
    const idx = Number(month) - 1;
    return `${names[idx] ?? month} ${year}`;
  }

  async function saveSettings() {
    saving = true;
    msg = '';
    error = '';
    try {
      settings = await patchAccountingSettings({
        accounting_start_date: settings.accounting_start_date,
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

  async function generateFromSpecificMonth() {
    if (!specificMonth) {
      error = 'Select a month first.';
      return;
    }
    generating = true;
    msg = '';
    error = '';
    try {
      await generateAccountingPeriods({ start_month: specificMonth });
      const [year, month] = specificMonth.split('-');
      msg = `Generated periods from ${month}/${year} to current month + 12 months (skipping existing).`;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Generate failed';
    } finally {
      generating = false;
    }
  }
</script>

<h1>Accounting calendar</h1>
<p class="hint">Configure period generation start point and generate historical + forward periods.</p>

{#if error}<p class="err">{error}</p>{/if}
{#if msg}<p class="ok">{msg}</p>{/if}

{#if loading}
  <p>Loading…</p>
{:else}
  <section class="card">
    <h2>Calendar Settings</h2>

    <label>
      Company accounting start date
      <input type="date" bind:value={settings.accounting_start_date} />
    </label>
    <p class="hint">
      The month your company started operations or began using this system.
      For mmlogistix use <strong>2025-04-01</strong>.
    </p>

    <button type="button" on:click={saveSettings} disabled={saving}>
      {saving ? 'Saving…' : 'Save settings'}
    </button>
  </section>

  <section class="card">
    <h2>Generate periods</h2>
    <button type="button" on:click={generateFromConfigured} disabled={generating}>
      {generating
        ? 'Generating…'
        : `Generate all periods from ${monthLabel(settings.accounting_start_date)}`}
    </button>

    <div class="specific">
      <label>
        Generate from specific month
        <input type="month" bind:value={specificMonth} />
      </label>
      <button type="button" on:click={generateFromSpecificMonth} disabled={generating}>
        Generate from selected month
      </button>
    </div>

    <p class="hint">Existing periods are skipped, so no duplicates are created.</p>
  </section>
{/if}

<style>
  .card {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background: #fff;
    padding: 1rem;
    margin-bottom: 1rem;
  }
  label {
    display: block;
    margin-bottom: 0.5rem;
  }
  input {
    width: 100%;
    max-width: 280px;
    padding: 0.45rem;
    margin-top: 0.25rem;
  }
  .specific {
    margin-top: 1rem;
    display: flex;
    gap: 0.75rem;
    align-items: end;
    flex-wrap: wrap;
  }
  .hint {
    color: #64748b;
    font-size: 0.875rem;
  }
  .ok {
    color: #15803d;
  }
  .err {
    color: #b91c1c;
  }
</style>
