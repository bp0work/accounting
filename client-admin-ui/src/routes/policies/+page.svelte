<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import {
    getExpenseLimits,
    patchExpenseLimits,
    getTravelPolicyDocument,
    uploadTravelPolicyPdf,
    downloadAuthenticated,
  } from '$lib/api/admin';

  let limits: Record<string, string> = {};
  let travelPolicy: Awaited<ReturnType<typeof getTravelPolicyDocument>> | null = null;
  let error = '';
  let msg = '';

  function formatBytes(n?: number) {
    if (n == null) return '—';
    if (n < 1024) return `${n} B`;
    return `${(n / 1024).toFixed(1)} KB`;
  }

  function formatDate(iso?: string) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString();
  }

  async function refresh() {
    travelPolicy = await getTravelPolicyDocument();
  }

  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    try {
      limits = (await getExpenseLimits()) as Record<string, string>;
      await refresh();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    }
  });

  async function saveLimits() {
    await patchExpenseLimits(limits);
    msg = 'Expense limits saved.';
  }

  async function onTravelPdf(e: Event) {
    const f = (e.target as HTMLInputElement).files?.[0];
    if (!f) return;
    error = '';
    try {
      await uploadTravelPolicyPdf(f);
      await refresh();
      msg = 'Travel & Entertainment policy uploaded.';
    } catch (err) {
      error = err instanceof Error ? err.message : 'Upload failed';
    }
  }

  async function downloadTravel() {
    if (!travelPolicy?.uploaded) return;
    await downloadAuthenticated(
      '/api/expense-policies/document/download',
      travelPolicy.filename || 'travel-expense-policy.pdf'
    );
  }
</script>

<h1>Travel &amp; Entertainment</h1>
<p class="hint">
  Tenant Travel &amp; Entertainment policy PDF and the numeric expense limits used by the expense
  claim workflow. Regulatory policy PDFs (PDPA, ACRA, etc.) live on the
  <a href="/regulatory-policies">Regulatory Policies</a> page.
</p>

{#if error}<p class="err">{error}</p>{/if}
{#if msg}<p class="ok">{msg}</p>{/if}

<section class="card">
  <h2>Policy document (PDF)</h2>
  <p>Stored at <code>transactions/regulatory/travel-expense-policy.pdf</code> in Wasabi.</p>
  {#if travelPolicy?.uploaded}
    <ul class="meta-list">
      <li><strong>File:</strong> {travelPolicy.filename}</li>
      <li><strong>Uploaded:</strong> {formatDate(travelPolicy.uploaded_at)}</li>
      <li><strong>Size:</strong> {formatBytes(travelPolicy.file_size)}</li>
    </ul>
    <button type="button" on:click={downloadTravel}>Download</button>
  {:else}
    <p class="warn">No policy document uploaded yet.</p>
  {/if}
  <label class="upload-btn">
    {travelPolicy?.uploaded ? 'Replace PDF' : 'Upload PDF'}
    <input type="file" accept=".pdf,application/pdf" on:change={onTravelPdf} hidden />
  </label>
</section>

<section class="card">
  <h2>Expense limits (SGD)</h2>
  <p class="hint">Numeric limits used by the expense claim workflow.</p>
  <label>Meal limit / day <input type="number" step="0.01" bind:value={limits.meal_limit_per_day} /></label>
  <label>Transport / trip <input type="number" step="0.01" bind:value={limits.transport_limit_per_trip} /></label>
  <label>Accommodation / night <input type="number" step="0.01" bind:value={limits.accommodation_limit_per_night} /></label>
  <label>Per diem <input type="number" step="0.01" bind:value={limits.per_diem_rate} /></label>
  <label>Entertainment / occasion <input type="number" step="0.01" bind:value={limits.entertainment_limit_per_occasion} /></label>
  <button type="button" on:click={saveLimits}>Save limits</button>
</section>

<style>
  .card { background: #fff; border: 1px solid #e2e8f0; padding: 1rem; margin-bottom: 1rem; border-radius: 8px; }
  h2 { margin: 0 0 0.5rem; font-size: 1rem; }
  label { display: block; margin: 0.5rem 0; }
  input { width: 100%; max-width: 280px; padding: 0.4rem; box-sizing: border-box; }
  .upload-btn { display: inline-block; margin-top: 0.5rem; padding: 0.4rem 0.75rem; background: #1d4ed8; color: #fff; border-radius: 6px; cursor: pointer; font-size: 0.875rem; }
  .meta-list { list-style: none; padding: 0; margin: 0.5rem 0; font-size: 0.875rem; color: #475569; }
  .hint, code { font-size: 0.875rem; }
  .hint { color: #475569; }
  .warn { color: #b45309; }
  .err { color: #b91c1c; }
  .ok { color: #15803d; }
</style>
