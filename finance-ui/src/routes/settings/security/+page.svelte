<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import QRCode from 'qrcode';
  import {
    disable2fa,
    setup2fa,
    verify2fa,
    type TwoFactorSetupResult,
  } from '$lib/api/auth';
  import { patchSessionUser } from '$lib/stores/session';
  import { getSessionUser } from '$lib/api/client';

  let twoFactorEnabled = false;
  let loading = true;
  let error = '';
  let success = '';

  let setupLoading = false;
  let verifyLoading = false;
  let disableLoading = false;
  let setup: TwoFactorSetupResult | null = null;
  let qrDataUrl = '';
  let totpCode = '';
  let disableCode = '';

  onMount(async () => {
    const user = getSessionUser();
    twoFactorEnabled = user?.two_factor_enabled ?? false;
    loading = false;
  });

  async function startSetup() {
    setupLoading = true;
    error = '';
    success = '';
    setup = null;
    qrDataUrl = '';
    totpCode = '';
    try {
      setup = await setup2fa();
      qrDataUrl = await QRCode.toDataURL(setup.qr_code_uri, { margin: 2, width: 256 });
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Setup failed';
      if (message.toLowerCase().includes('already enabled')) {
        twoFactorEnabled = true;
        patchSessionUser({ two_factor_enabled: true });
      }
      error = message;
    } finally {
      setupLoading = false;
    }
  }

  async function confirmSetup() {
    if (!setup || totpCode.length !== 6) return;
    verifyLoading = true;
    error = '';
    success = '';
    try {
      await verify2fa(totpCode, setup.secret);
      twoFactorEnabled = true;
      patchSessionUser({ two_factor_enabled: true });
      setup = null;
      qrDataUrl = '';
      totpCode = '';
      success = 'Two-factor authentication is now enabled.';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Verification failed';
    } finally {
      verifyLoading = false;
    }
  }

  async function disable() {
    if (disableCode.length !== 6) return;
    disableLoading = true;
    error = '';
    success = '';
    try {
      await disable2fa(disableCode);
      twoFactorEnabled = false;
      patchSessionUser({ two_factor_enabled: false });
      disableCode = '';
      success = 'Two-factor authentication has been disabled.';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Disable failed';
    } finally {
      disableLoading = false;
    }
  }

  function cancelSetup() {
    setup = null;
    qrDataUrl = '';
    totpCode = '';
    error = '';
  }
</script>

<h1>Security settings</h1>
<p class="hint">Manage two-factor authentication (TOTP) for your account.</p>

{#if loading}
  <p>Loading…</p>
{:else}
  <section class="card">
    <h2>Two-factor authentication</h2>
    <p>
      Status:
      <strong class:enabled={twoFactorEnabled} class:disabled={!twoFactorEnabled}>
        {twoFactorEnabled ? 'Enabled' : 'Disabled'}
      </strong>
    </p>

    {#if error}<p class="error">{error}</p>{/if}
    {#if success}<p class="success">{success}</p>{/if}

    {#if !twoFactorEnabled && !setup}
      <button type="button" class="primary" disabled={setupLoading} onclick={startSetup}>
        {setupLoading ? 'Starting setup…' : 'Enable 2FA'}
      </button>
    {/if}

    {#if setup}
      <div class="setup">
        <p>Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.).</p>
        {#if qrDataUrl}
          <img class="qr" src={qrDataUrl} alt="2FA QR code" width="256" height="256" />
        {/if}
        <p class="mono">Manual entry secret: <code>{setup.secret}</code></p>
        {#if setup.backup_codes.length > 0}
          <details>
            <summary>Backup codes (save securely)</summary>
            <ul class="backup-codes">
              {#each setup.backup_codes as code}
                <li><code>{code}</code></li>
              {/each}
            </ul>
          </details>
        {/if}
        <label class="field">
          <span>6-digit verification code</span>
          <input
            type="text"
            inputmode="numeric"
            maxlength="6"
            pattern="[0-9]*"
            autocomplete="one-time-code"
            bind:value={totpCode}
            placeholder="000000"
          />
        </label>
        <div class="actions">
          <button
            type="button"
            class="primary"
            disabled={verifyLoading || totpCode.length !== 6}
            onclick={confirmSetup}
          >
            {verifyLoading ? 'Verifying…' : 'Confirm and activate'}
          </button>
          <button type="button" class="secondary" disabled={verifyLoading} onclick={cancelSetup}>
            Cancel
          </button>
        </div>
      </div>
    {/if}

    {#if twoFactorEnabled}
      <div class="disable">
        <p>To disable 2FA, enter a current code from your authenticator app.</p>
        <label class="field">
          <span>6-digit code</span>
          <input
            type="text"
            inputmode="numeric"
            maxlength="6"
            pattern="[0-9]*"
            autocomplete="one-time-code"
            bind:value={disableCode}
            placeholder="000000"
          />
        </label>
        <button
          type="button"
          class="danger"
          disabled={disableLoading || disableCode.length !== 6}
          onclick={disable}
        >
          {disableLoading ? 'Disabling…' : 'Disable 2FA'}
        </button>
      </div>
    {/if}
  </section>
{/if}

<style>
  .hint {
    color: #64748b;
  }
  .error {
    color: #b91c1c;
  }
  .success {
    color: #15803d;
  }
  .enabled {
    color: #15803d;
  }
  .disabled {
    color: #c2410c;
  }
  h2 {
    margin-top: 0;
  }
  .setup,
  .disable {
    margin-top: 1rem;
  }
  .qr {
    display: block;
    margin: 1rem 0;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background: #fff;
  }
  .mono {
    font-family: ui-monospace, monospace;
    font-size: 0.85rem;
    word-break: break-all;
  }
  .backup-codes {
    columns: 2;
    font-family: ui-monospace, monospace;
    font-size: 0.85rem;
  }
  .field {
    display: block;
    margin: 1rem 0;
  }
  .field span {
    display: block;
    margin-bottom: 0.35rem;
    font-weight: 600;
  }
  .field input {
    width: 100%;
    max-width: 12rem;
    padding: 0.5rem;
    font-size: 1.1rem;
    letter-spacing: 0.15em;
    font-family: ui-monospace, monospace;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin-top: 0.75rem;
  }
  .primary {
    padding: 0.5rem 1rem;
    border: 1px solid #1d4ed8;
    border-radius: 6px;
    background: #1d4ed8;
    color: #fff;
    font-weight: 600;
  }
  .secondary {
    padding: 0.5rem 1rem;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    background: #fff;
    color: #334155;
  }
  .danger {
    padding: 0.5rem 1rem;
    border: 1px solid #b91c1c;
    border-radius: 6px;
    background: #fef2f2;
    color: #b91c1c;
    font-weight: 600;
  }
  button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
</style>
