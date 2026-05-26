<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { fetchTenantProfile, patchTenantProfile } from '$lib/api/admin';

  let loading = $state(true);
  let p = $state<Record<string, unknown>>({});
  let msg = $state('');
  let error = $state('');
  let showPreview = $state(false);

  const sampleBodyHtml =
    '<p>Thank you for your email. We have received your message and will review it shortly.</p>';
  const sampleBodyPlain =
    'Thank you for your email. We have received your message and will review it shortly.';

  const signatureHtml = $derived(String(p.email_signature_html ?? '').trim());
  const signaturePlain = $derived(String(p.email_signature_plain ?? '').trim());
  const previewHtml = $derived(
    signatureHtml
      ? `${sampleBodyHtml}<hr style="margin-top:2rem;border:none;border-top:1px solid #e2e8f0;"><div style="color:#6b7280;font-size:0.875rem;">${signatureHtml}</div>`
      : sampleBodyHtml
  );
  const previewPlain = $derived(
    signaturePlain ? `${sampleBodyPlain}\n\n--\n${signaturePlain}` : sampleBodyPlain
  );

  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    try {
      p = await fetchTenantProfile();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    } finally {
      loading = false;
    }
  });

  async function save() {
    msg = '';
    error = '';
    try {
      p = await patchTenantProfile(p);
      msg = 'Saved.';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Save failed';
    }
  }
</script>
<h1>Company profile</h1>
<p>Legal details and outbound email signature (appended to all tenant mailbox emails).</p>
{#if error}<p class="err">{error}</p>{/if}
{#if msg}<p class="ok">{msg}</p>{/if}
{#if loading}
  <p class="hint">Loading company profile…</p>
{:else}
<form onsubmit={(e) => { e.preventDefault(); save(); }} class="card">
  <h2>Company details</h2>
  <label>Legal name <input bind:value={p.legal_name} required /></label>
  <label>Trading name <input bind:value={p.trading_name} /></label>
  <label>UEN <input bind:value={p.uen} /></label>
  <label>GST registration <input bind:value={p.gst_registration_number} /></label>
  <label>Registered address <textarea bind:value={p.registered_address} rows="3"></textarea></label>
  <label>Contact email <input type="email" bind:value={p.contact_email} /></label>
  <label>Phone <input bind:value={p.contact_phone} /></label>
  <label>Website <input bind:value={p.website} /></label>

  <h2>Email signature</h2>
  <p class="hint">Used as the footer on all outbound emails from tenant mailboxes.</p>
  <label>HTML signature
    <textarea bind:value={p.email_signature_html} rows="6" placeholder="<p>Regards,<br/>MMLOGISTIX PTE. LTD.</p>"></textarea>
  </label>
  <label>Plain text signature
    <textarea bind:value={p.email_signature_plain} rows="4" placeholder="Regards,&#10;MMLOGISTIX PTE. LTD."></textarea>
  </label>
  <button type="button" class="preview-btn" onclick={() => (showPreview = !showPreview)}>
    {showPreview ? 'Hide preview' : 'Preview signature in email'}
  </button>
  {#if showPreview}
    <section class="preview">
      <h3>Email preview</h3>
      <p class="hint">Sample acknowledgement body with your signature appended as recipients will see it.</p>
      <div class="preview-pane html-preview">
        <h4>HTML</h4>
        <!-- eslint-disable-next-line svelte/no-at-html-tags -->
        {@html previewHtml}
      </div>
      <div class="preview-pane">
        <h4>Plain text</h4>
        <pre>{previewPlain}</pre>
      </div>
    </section>
  {/if}
  <button type="submit">Save</button>
</form>
{/if}
<style>
  label { display: block; margin-bottom: 0.75rem; }
  input, textarea { width: 100%; padding: 0.5rem; box-sizing: border-box; }
  .card { background: #fff; border: 1px solid #e2e8f0; padding: 1rem; border-radius: 8px; }
  h2 { margin: 1.25rem 0 0.5rem; font-size: 1rem; }
  h2:first-child { margin-top: 0; }
  .hint { font-size: 0.875rem; color: #64748b; }
  .err { color: #b91c1c; } .ok { color: #15803d; }
  .preview-btn { margin: 0.5rem 0 1rem; padding: 0.45rem 0.75rem; cursor: pointer; }
  .preview { margin: 1rem 0; padding: 1rem; border: 1px solid #e2e8f0; border-radius: 8px; background: #f8fafc; }
  .preview h3 { margin: 0 0 0.35rem; font-size: 1rem; }
  .preview-pane { margin-top: 0.75rem; }
  .preview-pane h4 { margin: 0 0 0.35rem; font-size: 0.875rem; color: #475569; }
  .html-preview { background: #fff; padding: 0.75rem; border: 1px solid #e2e8f0; border-radius: 6px; }
  .preview pre { white-space: pre-wrap; margin: 0; font-size: 0.875rem; background: #fff; padding: 0.75rem; border: 1px solid #e2e8f0; border-radius: 6px; }
</style>
