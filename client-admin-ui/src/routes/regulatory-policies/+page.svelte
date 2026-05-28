<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import {
    listRegulatoryCatalog,
    uploadRegulatoryPdf,
    downloadAuthenticated,
  } from '$lib/api/admin';

  let catalog: Awaited<ReturnType<typeof listRegulatoryCatalog>> = [];
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
    catalog = await listRegulatoryCatalog();
  }

  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    try {
      await refresh();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    }
  });

  async function onRegPdf(key: string, e: Event) {
    const f = (e.target as HTMLInputElement).files?.[0];
    if (!f) return;
    error = '';
    try {
      await uploadRegulatoryPdf(key, f);
      await refresh();
      msg = 'Regulatory document uploaded.';
    } catch (err) {
      error = err instanceof Error ? err.message : 'Upload failed';
    }
  }

  async function downloadReg(item: { download_url?: string; filename?: string }) {
    if (!item.download_url) return;
    await downloadAuthenticated(item.download_url, item.filename || 'document.pdf');
  }
</script>

<h1>Regulatory Policies</h1>
<p class="hint">
  Compliance PDFs (PDPA, ACRA, MAS TRM, etc.) uploaded to
  <code>transactions/regulatory/</code> in Wasabi. Each document type has a fixed storage path.
  The tenant Travel &amp; Entertainment policy lives on the
  <a href="/policies">Travel &amp; Entertainment</a> page.
</p>

{#if error}<p class="err">{error}</p>{/if}
{#if msg}<p class="ok">{msg}</p>{/if}

{#if catalog.length === 0}
  <p class="empty">Regulatory catalog is empty.</p>
{:else}
  {#each catalog as item (item.document_key)}
    <div class="card">
      <strong>{item.label}</strong>
      {#if item.uploaded}
        <ul class="meta-list">
          <li><strong>File:</strong> {item.filename}</li>
          <li><strong>Uploaded:</strong> {formatDate(item.uploaded_at)}</li>
          <li><strong>Size:</strong> {formatBytes(item.file_size)}</li>
        </ul>
        <button type="button" on:click={() => downloadReg(item)}>Download</button>
      {:else}
        <p class="warn">Not uploaded</p>
      {/if}
      <label class="upload-btn">
        {item.uploaded ? 'Replace PDF' : 'Upload PDF'}
        <input type="file" accept=".pdf,application/pdf" on:change={(e) => onRegPdf(item.document_key, e)} hidden />
      </label>
    </div>
  {/each}
{/if}

<style>
  .card { background: #fff; border: 1px solid #e2e8f0; padding: 1rem; margin-bottom: 1rem; border-radius: 8px; }
  .upload-btn { display: inline-block; margin-top: 0.5rem; padding: 0.4rem 0.75rem; background: #1d4ed8; color: #fff; border-radius: 6px; cursor: pointer; font-size: 0.875rem; }
  .meta-list { list-style: none; padding: 0; margin: 0.5rem 0; font-size: 0.875rem; color: #475569; }
  .hint, code { font-size: 0.875rem; }
  .hint { color: #475569; }
  .empty { color: #64748b; font-size: 0.875rem; font-style: italic; }
  .warn { color: #b45309; }
  .err { color: #b91c1c; }
  .ok { color: #15803d; }
</style>
