<script lang="ts">
  import { setToken } from '$lib/api/client';

  let username = '';
  let password = '';
  let error = '';

  async function login() {
    error = '';
    try {
      const res = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error?.message || 'Login failed');
      setToken(data.access_token);
      window.location.href = '/approvals';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Login failed';
    }
  }
</script>

<h1>Sign in</h1>
<p>Approval UI — Phase 9</p>

{#if error}<p style="color: #b91c1c;">{error}</p>{/if}

<form on:submit|preventDefault={login}>
  <div style="margin-bottom: 0.75rem;">
    <label>Username</label><br />
    <input bind:value={username} required style="width: 100%; padding: 0.5rem;" />
  </div>
  <div style="margin-bottom: 0.75rem;">
    <label>Password</label><br />
    <input type="password" bind:value={password} required style="width: 100%; padding: 0.5rem;" />
  </div>
  <button type="submit">Sign in</button>
</form>
