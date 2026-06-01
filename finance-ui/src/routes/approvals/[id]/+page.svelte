<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { approve, escalateToCfo, getApproval, reject, type ApprovalItem } from '$lib/api/approvals';
  import { sessionUser } from '$lib/stores/session';

  let item: ApprovalItem | null = null;
  let note = '';
  let reason = '';
  let message = '';
  let error = '';
  let loadingAction: 'approve' | 'reject' | 'escalate' | null = null;

  const tier2Roles = new Set(['accounts_clerk', 'finance_officer', 'finance_manager']);
  const executiveRoles = new Set(['cfo', 'finance_director']);

  $: id = $page.params.id;
  $: role = ($sessionUser?.role_name ?? '').toLowerCase();
  $: showAccActions =
    item?.status === 'pending' &&
    tier2Roles.has(role) &&
    item.tier === 2 &&
    !item.binding_escalated_to_cfo;
  $: showCfoActions =
    item?.status === 'pending' &&
    executiveRoles.has(role) &&
    (item.binding_escalated_to_cfo || item.tier >= 3);
  $: showActions = showAccActions || showCfoActions;

  onMount(load);

  async function load() {
    error = '';
    try {
      const token = await ensureValidAccessToken();
      if (!token) {
        const { goto } = await import('$app/navigation');
        await goto('/login');
        return;
      }
      item = await getApproval(id);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Not found';
    }
  }

  async function doApprove() {
    if (loadingAction !== null) return;
    message = '';
    loadingAction = 'approve';
    try {
      await approve(id, note || 'Approved');
      message = 'Approved';
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Approve failed';
    } finally {
      loadingAction = null;
    }
  }

  async function doReject() {
    if (loadingAction !== null) return;
    if (!reason.trim()) {
      error = 'Rejection reason is required.';
      return;
    }
    message = '';
    loadingAction = 'reject';
    try {
      await reject(id, reason);
      message = 'Rejected';
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Reject failed';
    } finally {
      loadingAction = null;
    }
  }

  async function doEscalate() {
    if (loadingAction !== null) return;
    message = '';
    loadingAction = 'escalate';
    try {
      await escalateToCfo(id, note || undefined);
      message = 'Escalated to CFO';
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Escalate failed';
    } finally {
      loadingAction = null;
    }
  }
</script>

<a href="/approvals">← Back</a>
<h1>Approval detail</h1>

{#if error}<p class="error">{error}</p>{/if}
{#if message}<p class="ok">{message}</p>{/if}

{#if item}
  <div class="card">
    <p><strong>{item.case_number}</strong> ({item.case_type}) · Tier {item.tier}</p>
    <p>{item.subject}</p>
    <p>Status: <strong>{item.status}</strong></p>
    {#if item.amount}
      <p>Amount: {item.amount.currency} {item.amount.value}</p>
    {/if}
    <p><a href={`/cases/${item.case_id}`}>View case</a></p>
  </div>

  {#if showActions}
    <div class="card">
      <h2>Actions</h2>
      <label>
        Note
        <textarea bind:value={note} placeholder="Optional for approve / escalate" rows="2"></textarea>
      </label>
      <label>
        Rejection reason
        <textarea bind:value={reason} placeholder="Required to reject" rows="2"></textarea>
      </label>
      <div class="actions">
        <button
          type="button"
          disabled={loadingAction !== null}
          aria-busy={loadingAction === 'approve'}
          on:click={doApprove}
        >
          {loadingAction === 'approve' ? 'Working…' : 'Approve'}
        </button>
        <button
          type="button"
          class="reject"
          disabled={loadingAction !== null}
          aria-busy={loadingAction === 'reject'}
          on:click={doReject}
        >
          {loadingAction === 'reject' ? 'Working…' : 'Reject'}
        </button>
        {#if showAccActions}
          <button
            type="button"
            class="escalate"
            disabled={loadingAction !== null}
            aria-busy={loadingAction === 'escalate'}
            on:click={doEscalate}
          >
            {loadingAction === 'escalate' ? 'Working…' : 'Escalate to CFO'}
          </button>
        {/if}
      </div>
    </div>
  {:else if item.status === 'pending'}
    <p class="hint">You do not have permission to act on this approval tier.</p>
  {/if}
{/if}

<style>
  .error {
    color: #b91c1c;
  }
  .ok {
    color: #15803d;
  }
  .hint {
    color: #64748b;
  }
  textarea {
    width: 100%;
    box-sizing: border-box;
    margin-top: 0.35rem;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 0.75rem;
  }
  .reject {
    border-color: #b91c1c;
    color: #991b1b;
  }
  .escalate {
    border-color: #1d4ed8;
    color: #1e40af;
  }
</style>
