<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { afterNavigate } from '$app/navigation';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { fetchTenantProfile, patchTenantProfile } from '$lib/api/admin';

  let loading = $state(true);
  let formKey = $state(0);
  let legal_name = $state('');
  let trading_name = $state('');
  let uen = $state('');
  let gst_registration_number = $state('');
  let registered_address = $state('');
  let contact_email = $state('');
  let contact_phone = $state('');
  let website = $state('');
  let email_signature_html = $state('');
  let email_signature_plain = $state('');
  let msg = $state('');
  let error = $state('');
  let showPreview = $state(false);

  const sampleBodyHtml =
    '<p>Thank you for your email. We have received your message and will review it shortly.</p>';
  const sampleBodyPlain =
    'Thank you for your email. We have received your message and will review it shortly.';

  const signatureHtml = $derived(email_signature_html.trim());
  const signaturePlain = $derived(email_signature_plain.trim());
  const previewHtml = $derived(
    signatureHtml
      ? `${sampleBodyHtml}<hr style="margin-top:2rem;border:none;border-top:1px solid #e2e8f0;"><div style="color:#6b7280;font-size:0.875rem;">${signatureHtml}</div>`
      : sampleBodyHtml
  );
  const previewPlain = $derived(
    signaturePlain ? `${sampleBodyPlain}\n\n--\n${signaturePlain}` : sampleBodyPlain
  );

  function applyProfile(data: Record<string, unknown>) {
    legal_name = String(data.legal_name ?? '');
    trading_name = String(data.trading_name ?? '');
    uen = String(data.uen ?? '');
    gst_registration_number = String(data.gst_registration_number ?? '');
    registered_address = String(data.registered_address ?? '');
    contact_email = String(data.contact_email ?? '');
    contact_phone = String(data.contact_phone ?? '');
    website = String(data.website ?? '');
    email_signature_html = String(data.email_signature_html ?? '');
    email_signature_plain = String(data.email_signature_plain ?? '');
    formKey += 1;
  }

  function profilePayload(): Record<string, unknown> {
    return {
      legal_name,
      trading_name,
      uen,
      gst_registration_number,
      registered_address,
      contact_email,
      contact_phone,
      website,
      email_signature_html,
      email_signature_plain,
    };
  }

  async function loadProfile() {
    msg = '';
    error = '';
    loading = true;
    if (!(await ensureValidAccessToken())) {
      loading = false;
      error = 'Not signed in';
      return;
    }
    try {
      applyProfile(await fetchTenantProfile());
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    } finally {
      loading = false;
    }
  }

  afterNavigate(({ to }) => {
    if (to?.url.pathname === '/company') {
      void loadProfile();
    }
  });

  async function save() {
    msg = '';
    error = '';
    try {
      applyProfile(await patchTenantProfile(profilePayload()));
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
  {#key formKey}
    <form onsubmit={(e) => { e.preventDefault(); save(); }} class="card">
      <h2>Company details</h2>
      <label>Legal name <input bind:value={legal_name} required /></label>
      <label>Trading name <input bind:value={trading_name} /></label>
      <label>UEN <input bind:value={uen} /></label>
      <label>GST registration <input bind:value={gst_registration_number} /></label>
      <label>Registered address <textarea bind:value={registered_address} rows="3"></textarea></label>
      <label>Contact email <input type="email" bind:value={contact_email} /></label>
      <label>Phone <input bind:value={contact_phone} /></label>
      <label>Website <input bind:value={website} /></label>

      <h2>Email signature</h2>
      <p class="hint">Used as the footer on all outbound emails from tenant mailboxes.</p>
      <label>HTML signature
        <textarea bind:value={email_signature_html} rows="6" placeholder="<p>Regards,<br/>MMLOGISTIX PTE. LTD.</p>"></textarea>
      </label>
      <label>Plain text signature
        <textarea bind:value={email_signature_plain} rows="4" placeholder="Regards,&#10;MMLOGISTIX PTE. LTD."></textarea>
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
  {/key}
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
