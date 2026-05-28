<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { changePassword } from '$lib/api/auth';

  let currentPassword = '';
  let newPassword = '';
  let confirmPassword = '';
  let loading = false;
  let error = '';
  let success = '';

  function resetForm() {
    currentPassword = '';
    newPassword = '';
    confirmPassword = '';
  }

  async function save() {
    error = '';
    success = '';

    if (!currentPassword || !newPassword || !confirmPassword) {
      error = 'All fields are required.';
      return;
    }
    if (newPassword !== confirmPassword) {
      error = 'New password and confirmation do not match.';
      return;
    }

    loading = true;
    try {
      await changePassword(currentPassword, newPassword);
      success = 'Password updated. Please sign in again.';
      resetForm();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Unable to change password';
    } finally {
      loading = false;
    }
  }
</script>

<h1>Change password</h1>
<p class="hint">Update your account password.</p>

{#if error}<p class="error">{error}</p>{/if}
{#if success}<p class="success">{success}</p>{/if}

<section class="card">
  <label>
    Current password
    <input type="password" bind:value={currentPassword} autocomplete="current-password" />
  </label>

  <label>
    New password
    <input type="password" bind:value={newPassword} autocomplete="new-password" />
  </label>

  <label>
    Confirm new password
    <input type="password" bind:value={confirmPassword} autocomplete="new-password" />
  </label>

  <button type="button" class="primary" disabled={loading} on:click={save}>
    {loading ? 'Saving…' : 'Save'}
  </button>
</section>

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
  .card {
    max-width: 34rem;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1rem;
    display: grid;
    gap: 0.9rem;
  }
  label {
    display: grid;
    gap: 0.3rem;
    font-weight: 600;
  }
  input {
    padding: 0.5rem;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
  }
  .primary {
    width: fit-content;
    padding: 0.55rem 1rem;
    border: 1px solid #1d4ed8;
    border-radius: 6px;
    background: #1d4ed8;
    color: #fff;
    font-weight: 600;
  }
  .primary:disabled {
    opacity: 0.65;
  }
</style>
