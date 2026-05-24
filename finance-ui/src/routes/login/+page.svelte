<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { setTokens } from '$lib/api/client';
  import {
    isLoginTotpRequired,
    loginRequest,
    sessionUserFromLogin,
  } from '$lib/api/auth';
  import { updateSessionUser } from '$lib/stores/session';
  import { APP_TITLE } from '$lib/branding';

  let username = '';
  let password = '';
  let totpCode = '';
  let needsTotp = false;
  let loading = false;
  let error = '';

  function resetTotpStep() {
    needsTotp = false;
    totpCode = '';
  }

  function onCredentialsInput() {
    if (needsTotp) {
      resetTotpStep();
      error = '';
    }
  }

  async function login() {
    error = '';
    loading = true;
    try {
      const result = await loginRequest({
        username,
        password,
        totp_code: needsTotp ? totpCode : undefined,
      });

      if (!result.ok) {
        if (isLoginTotpRequired(result.error.code) && !needsTotp) {
          needsTotp = true;
          error =
            result.error.message ||
            'Two-factor authentication is enabled. Enter your 6-digit code.';
          return;
        }
        throw new Error(result.error.message);
      }

      setTokens(result.data.access_token, result.data.refresh_token);
      if (result.data.user) {
        updateSessionUser(sessionUserFromLogin(result.data.user));
      }
      const { goto } = await import('$app/navigation');
      await goto('/dashboard');
    } catch (e) {
      error = e instanceof Error ? e.message : 'Login failed';
    } finally {
      loading = false;
    }
  }
</script>

<h1>Sign in</h1>
<p>{APP_TITLE}</p>

{#if error}<p style="color: #b91c1c;">{error}</p>{/if}

<form on:submit|preventDefault={login}>
  <div style="margin-bottom: 0.75rem;">
    <label for="username">Username</label><br />
    <input
      id="username"
      bind:value={username}
      on:input={onCredentialsInput}
      required
      autocomplete="username"
      disabled={loading}
      style="width: 100%; padding: 0.5rem;"
    />
  </div>
  <div style="margin-bottom: 0.75rem;">
    <label for="password">Password</label><br />
    <input
      id="password"
      type="password"
      bind:value={password}
      on:input={onCredentialsInput}
      required
      autocomplete="current-password"
      disabled={loading}
      style="width: 100%; padding: 0.5rem;"
    />
  </div>

  {#if needsTotp}
    <div style="margin-bottom: 0.75rem;">
      <label for="totp">Authentication code</label><br />
      <input
        id="totp"
        bind:value={totpCode}
        inputmode="numeric"
        autocomplete="one-time-code"
        maxlength="6"
        pattern="[0-9]{6}"
        required
        disabled={loading}
        style="width: 100%; padding: 0.5rem; letter-spacing: 0.2em;"
      />
      <p style="margin: 0.35rem 0 0; font-size: 0.875rem; color: #475569;">
        Enter the 6-digit code from your authenticator app.
      </p>
    </div>
  {/if}

  <button type="submit" disabled={loading || (needsTotp && totpCode.length !== 6)}>
    {loading ? 'Signing in…' : 'Sign in'}
  </button>
</form>
