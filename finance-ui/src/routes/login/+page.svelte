<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { setTokens } from '$lib/api/client';
  import { loginRequest, sessionUserFromLogin } from '$lib/api/auth';
  import { updateSessionUser } from '$lib/stores/session';
  import { APP_TITLE, BP0_LOGO } from '$lib/branding';

  let username = '';
  let password = '';
  let totpCode = '';
  let loading = false;
  let error = '';

  async function login() {
    error = '';
    loading = true;
    try {
      const trimmedTotp = totpCode.trim();
      const result = await loginRequest({
        username,
        password,
        totp_code: trimmedTotp.length > 0 ? trimmedTotp : undefined,
      });

      if (!result.ok) {
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

<div class="login-page">
  <img
    class="login-logo"
    src={BP0_LOGO.src}
    alt={BP0_LOGO.alt}
    width={BP0_LOGO.loginWidth}
    height={BP0_LOGO.loginHeight}
    decoding="async"
  />
  <h1>Sign in</h1>
  <p class="app-title">{APP_TITLE}</p>

  {#if error}<p class="error">{error}</p>{/if}

  <form on:submit|preventDefault={login}>
    <div class="field">
      <label for="username">Username</label>
      <input
        id="username"
        bind:value={username}
        required
        autocomplete="username"
        disabled={loading}
      />
    </div>
    <div class="field">
      <label for="password">Password</label>
      <input
        id="password"
        type="password"
        bind:value={password}
        required
        autocomplete="current-password"
        disabled={loading}
      />
    </div>
    <div class="field">
      <label for="totp">Authentication code (optional)</label>
      <input
        id="totp"
        type="text"
        bind:value={totpCode}
        autocomplete="one-time-code"
        maxlength="6"
        disabled={loading}
        class="totp"
      />
      <p class="hint">Leave blank if 2FA is not enabled.</p>
    </div>

    <button type="submit" disabled={loading}>
      {loading ? 'Signing in…' : 'Sign in'}
    </button>
  </form>
</div>

<style>
  .login-page {
    max-width: 24rem;
    margin: 0 auto;
  }

  .login-logo {
    display: block;
    width: 384px;
    max-width: 100%;
    height: auto;
    object-fit: contain;
    margin: 0 auto 1.25rem;
  }

  h1 {
    margin: 0 0 0.35rem;
    text-align: center;
  }

  .app-title {
    text-align: center;
    color: #64748b;
    margin: 0 0 1.25rem;
  }

  .error {
    color: #b91c1c;
  }

  .field {
    margin-bottom: 0.75rem;
  }

  .field label {
    display: block;
    margin-bottom: 0.25rem;
  }

  .field input {
    width: 100%;
    padding: 0.5rem;
    box-sizing: border-box;
  }

  .field input.totp {
    letter-spacing: 0.2em;
  }

  .hint {
    margin: 0.35rem 0 0;
    font-size: 0.875rem;
    color: #475569;
  }

  button[type='submit'] {
    margin-top: 0.25rem;
  }
</style>
