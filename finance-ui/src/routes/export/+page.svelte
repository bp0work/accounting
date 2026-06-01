<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { exportCasesCsv } from '$lib/api/cases';
  import {
    downloadTrialBalanceCsv,
    fetchTrialBalance,
    type TrialBalanceReport,
  } from '$lib/api/reports';
  import { formatDateOnly, formatTrialBalanceAmount } from '$lib/format';

  const MONTHS = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];

  const today = new Date().toISOString().slice(0, 10);
  const monthStart = `${today.slice(0, 7)}-01`;

  let dateFrom = monthStart;
  let dateTo = today;
  let error = '';
  let message = '';

  let tbAsAt = today;
  let tbReport: TrialBalanceReport | null = null;
  let tbError = '';
  let tbMessage = '';
  let tbLoading = false;
  let tbPeriodLabel: string | null = null;

  $: periodYearParam = $page.url.searchParams.get('period_year');
  $: periodMonthParam = $page.url.searchParams.get('period_month');

  function lastDayOfMonthIso(year: number, month1Based: number): string {
    const d = new Date(year, month1Based, 0);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }

  function applyPeriodFromUrl() {
    if (!periodYearParam || !periodMonthParam) {
      tbPeriodLabel = null;
      return;
    }
    const year = Number(periodYearParam);
    const month = Number(periodMonthParam);
    if (!Number.isFinite(year) || !Number.isFinite(month) || month < 1 || month > 12) {
      tbPeriodLabel = null;
      return;
    }
    tbAsAt = lastDayOfMonthIso(year, month);
    tbPeriodLabel = `${MONTHS[month - 1] || month} ${year}`;
  }

  $: if (periodYearParam !== null || periodMonthParam !== null) {
    applyPeriodFromUrl();
  }

  $: tbHeading =
    tbPeriodLabel != null
      ? `Trial Balance — ${tbPeriodLabel}`
      : `Trial Balance — As at ${formatDateOnly(tbReport?.as_at ?? tbAsAt)}`;

  async function submit() {
    error = '';
    message = '';
    if (!dateFrom || !dateTo) {
      error = 'Both dates are required';
      return;
    }
    if (dateFrom > dateTo) {
      error = 'From date must be on or before To date';
      return;
    }
    try {
      await exportCasesCsv(dateFrom, dateTo);
      message = `Download started: transactions_${dateFrom}_${dateTo}.csv`;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Export failed';
    }
  }

  async function loadTrialBalance() {
    tbLoading = true;
    tbError = '';
    try {
      tbReport = await fetchTrialBalance(tbAsAt);
    } catch (e) {
      tbReport = null;
      tbError = e instanceof Error ? e.message : 'Failed to load trial balance';
    } finally {
      tbLoading = false;
    }
  }

  async function downloadTb() {
    tbMessage = '';
    tbError = '';
    try {
      await downloadTrialBalanceCsv(tbAsAt);
      tbMessage = `Download started: trial_balance_${tbAsAt}.csv`;
    } catch (e) {
      tbError = e instanceof Error ? e.message : 'Trial balance export failed';
    }
  }

  onMount(() => {
    applyPeriodFromUrl();
    void loadTrialBalance();
  });
</script>

<h1>Export</h1>

<section class="card section">
  <h2>Export transactions</h2>
  <p class="subtitle">Download a CSV of cases for the selected date range (created_at).</p>

  {#if error}<p class="error">{error}</p>{/if}
  {#if message}<p class="ok">{message}</p>{/if}

  <form class="form" on:submit|preventDefault={submit}>
    <div class="field">
      <label for="from">From date</label>
      <input id="from" type="date" bind:value={dateFrom} required />
    </div>
    <div class="field">
      <label for="to">To date</label>
      <input id="to" type="date" bind:value={dateTo} required />
    </div>
    <button type="submit">Download CSV</button>
  </form>
</section>

<section class="card section tb-section">
  <div class="tb-header">
    <h2>{tbHeading}</h2>
    <div class="tb-actions">
      <label class="tb-date">
        As at
        <input
          type="date"
          bind:value={tbAsAt}
          on:change={() => {
            tbPeriodLabel = null;
            void loadTrialBalance();
          }}
        />
      </label>
      <button type="button" class="secondary" disabled={tbLoading} on:click={loadTrialBalance}>
        {tbLoading ? 'Loading…' : 'Refresh'}
      </button>
      <button type="button" disabled={tbLoading} on:click={downloadTb}>Download TB</button>
    </div>
  </div>

  {#if tbError}<p class="error">{tbError}</p>{/if}
  {#if tbMessage}<p class="ok">{tbMessage}</p>{/if}

  {#if tbLoading && !tbReport}
    <p class="hint">Loading trial balance…</p>
  {:else if tbReport}
    {#each tbReport.groups as group (group.account_type)}
      <div class="tb-group">
        <h3 class="tb-group-label">{group.label}</h3>
        <table class="tb-table">
          <thead>
            <tr>
              <th>Account Code</th>
              <th>Account Name</th>
              <th class="num">Debit</th>
              <th class="num">Credit</th>
              <th class="num">Balance</th>
            </tr>
          </thead>
          <tbody>
            {#each group.rows as row (row.account_code)}
              <tr>
                <td>{row.account_code}</td>
                <td>{row.account_name}</td>
                <td class="num">{formatTrialBalanceAmount(row.debit)}</td>
                <td class="num">{formatTrialBalanceAmount(row.credit)}</td>
                <td class="num">{row.balance}</td>
              </tr>
            {/each}
            <tr class="subtotal">
              <td colspan="3"></td>
              <td class="num subtotal-label">Total</td>
              <td class="num">{group.total_balance}</td>
            </tr>
          </tbody>
        </table>
      </div>
    {/each}

    <table class="tb-table grand-total">
      <tbody>
        <tr>
          <td colspan="3"></td>
          <td class="num subtotal-label">TOTAL</td>
          <td class="num">{tbReport.grand_total_balance}</td>
        </tr>
      </tbody>
    </table>
  {/if}
</section>

<style>
  h1 {
    margin-bottom: 1rem;
  }
  .section {
    margin-bottom: 1.5rem;
  }
  .section h2 {
    margin: 0 0 0.35rem;
    font-size: 1.15rem;
  }
  .subtitle {
    color: #64748b;
    margin: 0 0 1rem;
  }
  .error {
    color: #b91c1c;
  }
  .ok {
    color: #15803d;
  }
  .hint {
    color: #64748b;
  }
  .card {
    padding: 1rem 1.25rem;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background: #fff;
  }
  .form {
    max-width: 360px;
  }
  .field {
    margin-bottom: 1rem;
  }
  .field label {
    display: block;
    margin-bottom: 0.35rem;
    font-weight: 500;
  }
  .field input {
    width: 100%;
    padding: 0.5rem;
    box-sizing: border-box;
  }
  .tb-header {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 1rem;
  }
  .tb-header h2 {
    margin: 0;
  }
  .tb-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
  }
  .tb-date {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.875rem;
  }
  .tb-date input {
    padding: 0.35rem 0.5rem;
  }
  button.secondary {
    background: #f8fafc;
    border: 1px solid #cbd5e1;
  }
  .tb-group {
    margin-bottom: 1.25rem;
  }
  .tb-group-label {
    margin: 0 0 0.5rem;
    font-size: 0.95rem;
    letter-spacing: 0.02em;
  }
  .tb-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
    font-variant-numeric: tabular-nums;
  }
  .tb-table th,
  .tb-table td {
    padding: 0.4rem 0.5rem;
    text-align: left;
    border-bottom: 1px solid #e2e8f0;
  }
  .tb-table th.num,
  .tb-table td.num {
    text-align: right;
  }
  .tb-table tr.subtotal td {
    border-bottom: none;
    font-weight: 600;
  }
  .subtotal-label {
    text-align: right;
  }
  .grand-total {
    margin-top: 0.5rem;
  }
  .grand-total td {
    border-bottom: none;
    font-weight: 700;
  }
</style>
