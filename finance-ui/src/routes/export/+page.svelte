<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { exportCasesCsv } from '$lib/api/cases';

  const today = new Date().toISOString().slice(0, 10);
  const monthStart = `${today.slice(0, 7)}-01`;

  let dateFrom = monthStart;
  let dateTo = today;
  let error = '';
  let message = '';

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
</script>

<h1>Export transactions</h1>
<p class="subtitle">Download a CSV of cases for the selected date range (created_at).</p>

{#if error}<p class="error">{error}</p>{/if}
{#if message}<p class="ok">{message}</p>{/if}

<form class="card form" on:submit|preventDefault={submit}>
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

<style>
  .subtitle {
    color: #64748b;
  }
  .error {
    color: #b91c1c;
  }
  .ok {
    color: #15803d;
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
</style>
