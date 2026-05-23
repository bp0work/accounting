<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import {
    fetchCase,
    fetchCaseTimeline,
    retryCase,
    type CaseItem,
    type TimelineEntry,
  } from '$lib/api/cases';

  let item: CaseItem | null = null;
  let timeline: TimelineEntry[] = [];
  let error = '';
  let retrying = false;
  let retryMessage = '';

  const retryableStatuses = new Set(['exception', 'manual_review']);

  $: id = $page.params.id;

  onMount(load);

  async function load() {
    error = '';
    retryMessage = '';
    try {
      [item, timeline] = await Promise.all([fetchCase(id), fetchCaseTimeline(id)]);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Not found';
    }
  }

  async function handleRetry() {
    if (!item || retrying) return;
    retrying = true;
    retryMessage = '';
    error = '';
    try {
      const result = await retryCase(id);
      retryMessage = `Requeued as ${result.status} (was ${result.previous_status}).`;
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Retry failed';
    } finally {
      retrying = false;
    }
  }

  function formatMeta(meta: Record<string, unknown> | undefined): string {
    if (!meta || Object.keys(meta).length === 0) return '';
    const parts: string[] = [];
    const keys = [
      'from_address',
      'subject',
      'confidence',
      'invoice_number',
      'total_amount',
      'currency',
      'vendor',
      'policy_action',
      'policy_tier',
      'debit_account',
      'credit_account',
      'amount',
      'journal_entry_id',
      'target_email',
      'reason_code',
      'missing_fields',
    ];
    for (const key of keys) {
      if (meta[key] != null && meta[key] !== '') {
        parts.push(`${key}: ${JSON.stringify(meta[key])}`);
      }
    }
    return parts.join(' · ');
  }

  function eventLabel(entry: TimelineEntry): string {
    const labels: Record<string, string> = {
      created: 'Email received',
      classification: 'Classification',
      processing_started: 'Processing started',
      processing_completed: 'Processing completed',
      status_change: 'Status / policy / extraction',
      exception_raised: 'Escalation / exception',
      case_retry: 'Manual retry',
      journal_linked: 'Journal posted',
      approval_requested: 'Approval requested',
    };
    return labels[entry.event_type] || entry.event_type;
  }
</script>

<a href="/approvals">← Cases & Approvals</a>
<h1>Case detail</h1>

{#if error}<p class="error">{error}</p>{/if}
{#if item}
  <div class="card" class:overdue={item.is_overdue} class:exception={item.status === 'exception' || item.status === 'manual_review'}>
    {#if item.is_overdue}<p class="badge warn">Overdue — past SLA threshold</p>{/if}
    {#if item.error_reason}
      <p class="badge error">Error: {item.error_reason}</p>
    {/if}
    <p><strong>{item.case_number}</strong> · {item.type}</p>
    <p>Status: <strong>{item.status}</strong>{#if item.processing_stage} · Stage: {item.processing_stage}{/if}</p>
    {#if item.status_reason && !item.error_reason}
      <p class="hint">{item.status_reason}</p>
    {/if}
    <p>{item.subject}</p>
    <p>Counterparty: {item.counterparty_name || '—'}</p>
    <p>Processing time: {item.processing_time_minutes != null ? `${item.processing_time_minutes} min` : '—'}</p>
    <p>Created: {new Date(item.created_at).toLocaleString()}</p>
    {#if item.last_activity_at}
      <p>Last activity: {new Date(item.last_activity_at).toLocaleString()}</p>
    {/if}
    {#if item.sla_deadline}
      <p>SLA deadline: {new Date(item.sla_deadline).toLocaleString()}</p>
    {/if}
    {#if retryableStatuses.has(item.status)}
      <button type="button" class="retry" disabled={retrying} onclick={handleRetry}>
        {retrying ? 'Requeuing…' : 'Retry processing'}
      </button>
      {#if retryMessage}
        <p class="hint success">{retryMessage}</p>
      {/if}
    {/if}
  </div>

  <section class="card timeline">
    <h2>Processing timeline</h2>
    {#if timeline.length === 0}
      <p>No timeline entries yet.</p>
    {:else}
      <ol>
        {#each timeline as entry}
          <li>
            <div class="time">{new Date(entry.created_at).toLocaleString()}</div>
            <div class="event">
              <strong>{eventLabel(entry)}</strong>
              {#if entry.description}
                <span> — {entry.description}</span>
              {/if}
            </div>
            <div class="meta">
              {entry.actor}
              {#if entry.from_status || entry.to_status}
                · {entry.from_status || '—'} → {entry.to_status || '—'}
              {/if}
            </div>
            {#if formatMeta(entry.metadata)}
              <div class="meta detail">{formatMeta(entry.metadata)}</div>
            {/if}
          </li>
        {/each}
      </ol>
    {/if}
  </section>
{/if}

<style>
  .error {
    color: #b91c1c;
  }
  .overdue {
    border-color: #fecaca;
    background: #fef2f2;
  }
  .exception {
    border-color: #fed7aa;
    background: #fff7ed;
  }
  .badge {
    font-weight: 600;
    margin-top: 0;
  }
  .badge.warn {
    color: #b91c1c;
  }
  .badge.error {
    color: #c2410c;
    background: #ffedd5;
    padding: 0.35rem 0.5rem;
    border-radius: 4px;
  }
  .hint {
    color: #64748b;
  }
  .hint.success {
    color: #15803d;
  }
  .retry {
    margin-top: 0.75rem;
    padding: 0.5rem 1rem;
    border: 1px solid #ea580c;
    border-radius: 6px;
    background: #fff7ed;
    color: #c2410c;
    font-weight: 600;
    cursor: pointer;
  }
  .retry:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  .timeline h2 {
    margin-top: 0;
  }
  .timeline ol {
    list-style: none;
    padding: 0;
    margin: 0;
  }
  .timeline li {
    border-left: 3px solid #cbd5e1;
    padding: 0.75rem 0 0.75rem 1rem;
    margin-bottom: 0.25rem;
  }
  .time {
    font-size: 0.8rem;
    color: #64748b;
  }
  .event {
    margin: 0.25rem 0;
  }
  .meta {
    font-size: 0.85rem;
    color: #475569;
  }
  .meta.detail {
    margin-top: 0.25rem;
    font-family: ui-monospace, monospace;
    font-size: 0.8rem;
  }
</style>
