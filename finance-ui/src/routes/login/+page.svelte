<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { setTokens } from '$lib/api/client';
  import { loginRequest, sessionUserFromLogin } from '$lib/api/auth';
  import { updateSessionUser } from '$lib/stores/session';
  import { APP_TITLE } from '$lib/branding';

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

<h1>Sign in</h1>
<p>{APP_TITLE}</p>

{#if error}<p style="color: #b91c1c;">{error}</p>{/if}

<form on:submit|preventDefault={login}>
  <div style="margin-bottom: 0.75rem;">
    <label for="username">Username</label><br />
    <input
      id="username"
      bind:value={username}
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
      required
      autocomplete="current-password"
      disabled={loading}
      style="width: 100%; padding: 0.5rem;"
    />
  </div>
  <div style="margin-bottom: 0.75rem;">
    <label for="totp">Authentication code (optional)</label><br />
    <input
      id="totp"
      type="text"
      bind:value={totpCode}
      autocomplete="one-time-code"
      maxlength="6"
      disabled={loading}
      style="width: 100%; padding: 0.5rem; letter-spacing: 0.2em;"
    />
    <p style="margin: 0.35rem 0 0; font-size: 0.875rem; color: #475569;">
      Leave blank if 2FA is not enabled.
    </p>
  </div>

  <button type="submit" disabled={loading}>
    {loading ? 'Signing in…' : 'Sign in'}
  </button>
</form>
