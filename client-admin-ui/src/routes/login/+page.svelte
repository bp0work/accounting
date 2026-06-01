<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { loginRequest, completeLogin } from '$lib/api/auth';
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
      const t = totpCode.trim();
      const data = await loginRequest(username, password, t || undefined);
      completeLogin(data);
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

  {#if error}<p class="err">{error}</p>{/if}

  <form on:submit|preventDefault={login}>
    <label>
      Username<br />
      <input bind:value={username} required disabled={loading} />
    </label>
    <label>
      Password<br />
      <input type="password" bind:value={password} required disabled={loading} />
    </label>
    <label>
      Authentication code (optional)<br />
      <input bind:value={totpCode} maxlength="6" disabled={loading} class="totp" />
      <span class="hint">Leave blank if 2FA is not enabled.</span>
    </label>
    <button type="submit" disabled={loading}>{loading ? 'Signing in…' : 'Sign in'}</button>
  </form>
  <p class="portal-link">
    <a href="https://finance.mmlogistix.bp0.work" target="_blank" rel="noopener noreferrer">
      Finance portal → finance.mmlogistix.bp0.work
    </a>
  </p>
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

  form label {
    display: block;
    margin-bottom: 0.75rem;
  }

  input {
    width: 100%;
    padding: 0.5rem;
    box-sizing: border-box;
  }

  input.totp {
    letter-spacing: 0.2em;
  }

  .err {
    color: #b91c1c;
  }

  .hint {
    font-size: 0.875rem;
    color: #64748b;
    display: block;
    margin-top: 0.25rem;
  }

  .portal-link {
    margin: 1rem 0 0;
    text-align: center;
    font-size: 0.875rem;
  }

  .portal-link a {
    color: #64748b;
    text-decoration: none;
  }

  .portal-link a:hover {
    color: #475569;
    text-decoration: underline;
  }
</style>
