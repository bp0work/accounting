<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import {
    bindingQueueForRole,
    listApprovals,
    type ApprovalItem,
  } from '$lib/api/approvals';
  import { listCases, type CaseItem } from '$lib/api/cases';
  import {
    canUseManualReviewActions,
    caseReasonCode,
    isManualReviewQueueCase,
  } from '$lib/ap-escalation-actions';
  import {
    caseStatusLabel,
    clientVendorColumnValue,
    documentTypeLabel,
  } from '$lib/case-labels';
  import { formatCount, formatCurrencyAmount } from '$lib/format';
  import { sessionUser } from '$lib/stores/session';

  let tab: 'queue' | 'history' | 'cases' = 'queue';
  let pending: ApprovalItem[] = [];
  let history: ApprovalItem[] = [];
  let cases: CaseItem[] = [];
  let error = '';
  let loading = true;

  $: role = ($sessionUser?.role_name ?? '').toLowerCase();
  $: queueLabel =
    role === 'cfo' || role === 'finance_director'
      ? 'Tier 3 and escalated Tier 2'
      : role === 'accounts_manager' || role === 'finance_officer' || role === 'finance_manager'
        ? 'Tier 2 pending'
        : 'Pending approvals';

  $: showManualReviewQueue = canUseManualReviewActions(role);
  $: manualReviewCases = showManualReviewQueue
    ? cases
        .filter((c) => isManualReviewQueueCase(c, role))
        .sort(
          (a, b) =>
            new Date(b.last_activity_at || b.created_at).getTime() -
            new Date(a.last_activity_at || a.created_at).getTime()
        )
    : [];

  onMount(() => {
    void loadAll();
  });

  async function loadAll() {
    error = '';
    loading = true;
    try {
      const token = await ensureValidAccessToken();
      if (!token) {
        const { goto } = await import('$app/navigation');
        await goto('/login');
        return;
      }
      const bindingQueue = bindingQueueForRole($sessionUser?.role_name);
      const [pendingRes, approvedRes, rejectedRes, casesRes] = await Promise.all([
        listApprovals({ status: 'pending', bindingQueue }),
        listApprovals({ status: 'approved' }),
        listApprovals({ status: 'rejected' }),
        listCases(200),
      ]);
      pending = pendingRes.data;
      const seen = new Set<string>();
      history = [];
      for (const row of [...approvedRes.data, ...rejectedRes.data]) {
        if (seen.has(row.id)) continue;
        seen.add(row.id);
        history.push(row);
      }
      history.sort(
        (a, b) =>
          new Date(b.responded_at || b.created_at || 0).getTime() -
          new Date(a.responded_at || a.created_at || 0).getTime()
      );
      cases = casesRes.data;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load';
    } finally {
      loading = false;
    }
  }

  function formatApprovalAmount(a?: ApprovalItem['amount']) {
    if (!a) return '—';
    return formatCurrencyAmount(a.currency, a.value);
  }

  function formatCaseAmount(c: CaseItem) {
    return formatCurrencyAmount(c.amount_currency, c.amount_value);
  }

  function formatActivity(c: CaseItem) {
    const ts = c.last_activity_at || c.created_at;
    return new Date(ts).toLocaleString();
  }

  function tierLabel(tier: number) {
    return `Tier ${tier}`;
  }
</script>

<h1>Cases & Approvals</h1>

<div class="tabs">
  <button type="button" class:active={tab === 'queue'} on:click={() => (tab = 'queue')}>My queue</button>
  <button type="button" class:active={tab === 'history'} on:click={() => (tab = 'history')}>History</button>
  <button type="button" class:active={tab === 'cases'} on:click={() => (tab = 'cases')}>All cases</button>
</div>

{#if error}<p class="error">{error}</p>{/if}

{#if loading}
  <p>Loading…</p>
{:else if tab === 'queue'}
  <section class="queue-section">
    <h2 class="section-heading">
      Pending approvals
        <span class="count-badge">{formatCount(pending.length)}</span>
    </h2>
    <p class="subtitle">{queueLabel}</p>
    {#if pending.length === 0}
      <p class="empty-hint">No pending approvals in your queue.</p>
    {:else}
      <div class="table-wrap card">
        <table>
          <thead>
            <tr>
              <th>Case</th>
              <th>Type</th>
              <th>Tier</th>
              <th>Subject</th>
              <th>Amount</th>
              <th>SLA</th>
            </tr>
          </thead>
          <tbody>
            {#each pending as item}
              <tr>
                <td><a href={`/cases/${item.case_id}`}>{item.case_number}</a></td>
                <td>{item.case_type}</td>
                <td>{tierLabel(item.tier)}</td>
                <td>{item.subject || '—'}</td>
                <td>{formatApprovalAmount(item.amount)}</td>
                <td>
                  {item.sla_deadline ? new Date(item.sla_deadline).toLocaleString() : '—'}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </section>

  {#if showManualReviewQueue}
    <section class="queue-section manual-review-section">
      <h2 class="section-heading">
        Manual review required
        <span class="count-badge attention">{formatCount(manualReviewCases.length)}</span>
      </h2>
      <p class="subtitle">
        Cases on hold or in manual review with a pending manager escalation — use Take action to
        approve, reject, or retry from the case detail panel.
      </p>
      {#if manualReviewCases.length === 0}
        <p class="empty-hint">No cases need manual review right now.</p>
      {:else}
        <div class="table-wrap card">
          <table>
            <thead>
              <tr>
                <th>Case</th>
                <th>Type</th>
                <th>Status</th>
                <th>Reason</th>
                <th>Client / Vendor</th>
                <th>Last activity</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {#each manualReviewCases as item}
                <tr class:overdue={item.is_overdue}>
                  <td><a href={`/cases/${item.id}`}>{item.case_number}</a></td>
                  <td>{documentTypeLabel(item.type)}</td>
                  <td>{caseStatusLabel(item)}</td>
                  <td>{caseReasonCode(item).replaceAll('_', ' ') || '—'}</td>
                  <td>{clientVendorColumnValue(item)}</td>
                  <td>{formatActivity(item)}</td>
                  <td><a href={`/cases/${item.id}`}>Take action</a></td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </section>
  {/if}
{:else if tab === 'history'}
  <p class="subtitle">Completed approvals (approved or rejected).</p>
  {#if history.length === 0}
    <p>No completed approvals yet.</p>
  {:else}
    <div class="table-wrap card">
      <table>
        <thead>
          <tr>
            <th>Case</th>
            <th>Tier</th>
            <th>Status</th>
            <th>Responded</th>
            <th>Note</th>
          </tr>
        </thead>
        <tbody>
          {#each history as item}
            <tr>
              <td><a href={`/cases/${item.case_id}`}>{item.case_number}</a></td>
              <td>{tierLabel(item.tier)}</td>
              <td>{item.status}</td>
              <td>
                {item.responded_at
                  ? new Date(item.responded_at).toLocaleString()
                  : '—'}
              </td>
              <td>{item.response_note || '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
{:else}
  <p class="subtitle">Monitoring view — all cases.</p>
  {#if cases.length === 0}
    <p>No cases found.</p>
  {:else}
    <div class="table-wrap card">
      <table>
        <thead>
          <tr>
            <th></th>
            <th>Case</th>
            <th>Document Type</th>
            <th>State</th>
            <th>Status</th>
            <th>Submitted By</th>
            <th>Client / Vendor</th>
            <th>Amount</th>
            <th>Last Activity</th>
          </tr>
        </thead>
        <tbody>
          {#each cases as item}
            <tr class:overdue={item.is_overdue}>
              <td class="indicator">{item.is_overdue ? '⚠' : '·'}</td>
              <td><a href={`/cases/${item.id}`}>{item.case_number}</a></td>
              <td>{documentTypeLabel(item.type)}</td>
              <td>{caseStateColumnLabel(item)}</td>
              <td>{caseStatusLabel(item)}</td>
              <td>{item.from_address || '—'}</td>
              <td>{clientVendorColumnValue(item)}</td>
              <td>{formatCaseAmount(item)}</td>
              <td>{formatActivity(item)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
{/if}

<style>
  .tabs {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }
  .tabs button {
    padding: 0.4rem 0.75rem;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    background: #fff;
    cursor: pointer;
  }
  .tabs button.active {
    background: #eff6ff;
    border-color: #1d4ed8;
    color: #1e40af;
    font-weight: 600;
  }
  .queue-section {
    margin-bottom: 2rem;
  }
  .manual-review-section {
    padding-top: 1.25rem;
    border-top: 1px solid #e2e8f0;
  }
  .section-heading {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 0 0 0.35rem;
    font-size: 1.1rem;
    font-weight: 600;
  }
  .count-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.5rem;
    padding: 0.1rem 0.45rem;
    border-radius: 999px;
    background: #dbeafe;
    color: #1e40af;
    font-size: 0.8rem;
    font-weight: 700;
  }
  .count-badge.attention {
    background: #ffedd5;
    color: #9a3412;
  }
  .empty-hint {
    color: #64748b;
    margin: 0.5rem 0 0;
  }
  .subtitle {
    color: #64748b;
    margin-bottom: 0.75rem;
  }
  .error {
    color: #b91c1c;
  }
  .table-wrap {
    overflow-x: auto;
    padding: 0;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }
  th,
  td {
    text-align: left;
    padding: 0.6rem 0.75rem;
    border-bottom: 1px solid #e2e8f0;
  }
  tr.overdue {
    background: #fef2f2;
  }
  .indicator {
    width: 2rem;
    text-align: center;
  }
</style>
