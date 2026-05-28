<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { resolveNavDisplayName } from '$lib/displayUser';

  let username = '';

  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    username = await resolveNavDisplayName();
  });
</script>

<h1>Account security</h1>

<p class="hint">Signed in as <strong>{username || '…'}</strong></p>

<section class="card">
  <h2>Change password</h2>
  <p>
    Client Admin login passwords are managed by the <strong>platform administrator</strong>.
    Contact your platform admin to reset or change your password.
  </p>
</section>

<style>
  .hint {
    color: #64748b;
    margin-bottom: 1rem;
  }
  .card {
    border: 1px solid #e2e8f0;
    border-radius: 0.5rem;
    padding: 1.25rem;
    background: #fff;
  }
  .card h2 {
    margin: 0 0 0.75rem;
    font-size: 1rem;
  }
  .card p {
    margin: 0;
    line-height: 1.5;
  }
</style>
