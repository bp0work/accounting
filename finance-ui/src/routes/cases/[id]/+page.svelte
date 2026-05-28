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
    overrideGlPeriodPost,
    type CaseItem,
    type TimelineEntry,
  } from '$lib/api/cases';
  import {
    saveVendorExtractionHint,
    type VendorExtractionHintCreate,
  } from '$lib/api/vendor-hints';
  import { clientVendorColumnValue } from '$lib/case-labels';
  import { approve, escalateToCfo, reject } from '$lib/api/approvals';
  import { sessionUser } from '$lib/stores/session';

  let item: CaseItem | null = null;
  let approvalNote = '';
  let approvalReason = '';
  let approvalBusy = false;
  let approvalMessage = '';
  let timeline: TimelineEntry[] = [];
  let error = '';
  let retrying = false;
  let retryMessage = '';
  let showOverrideModal = false;
  let overrideReason = '';
  let overrideSubmitting = false;
  let savedHintFields = new Set<string>();
  let teachMessage = '';

  type TeachFieldForm = {
    field_name: string;
    field_label: string;
    example_value: string;
    date_format: string;
    saving: boolean;
  };

  let teachFields: TeachFieldForm[] = [];
  let teachFieldsKey = '';

  const DATE_FIELD_NAMES = new Set(['invoice_date', 'due_date', 'payment_due_date']);

  const overrideRoles = new Set(['cfo', 'finance_manager']);
  const tier2Roles = new Set(['accounts_clerk', 'finance_officer']);
  const executiveRoles = new Set(['cfo', 'finance_manager']);

  $: role = ($sessionUser?.role_name ?? '').toLowerCase();
  $: bindingTier = item?.current_approval_tier ?? null;
  $: bindingEscalated = Boolean(item?.binding_escalated_to_cfo);
  $: showAccApprovalActions =
    item?.status === 'pending_approval' &&
    tier2Roles.has(role) &&
    bindingTier === 2 &&
    !bindingEscalated &&
    !!item?.pending_approval_id;
  $: showCfoApprovalActions =
    item?.status === 'pending_approval' &&
    executiveRoles.has(role) &&
    bindingTier != null &&
    bindingTier >= 2 &&
    !!item?.pending_approval_id;

  $: periodClosedHold =
    item &&
    item.status === 'on_hold' &&
    (item.workflow_metadata?.reason_code === 'PERIOD_CLOSED' ||
      item.workflow_metadata?.error_type === 'PERIOD_CLOSED');
  $: glPeriodStillClosed = item?.linked_gl_period_status === 'closed';
  $: canOverrideGl =
    overrideRoles.has(($sessionUser?.role_name ?? '').toLowerCase()) &&
    periodClosedHold &&
    glPeriodStillClosed;
  $: canRetryAfterReopen =
    periodClosedHold && item?.linked_gl_period_status != null && !glPeriodStillClosed;
  $: glPeriodId = item?.workflow_metadata?.gl_period_id
    ? String(item.workflow_metadata.gl_period_id)
    : '';

  const retryableStatuses = new Set(['exception', 'manual_review']);

  $: id = $page.params.id;

  function resolveVendorName(caseItem: CaseItem): string {
    const meta = caseItem.workflow_metadata ?? {};
    const extracted = meta.extracted_fields;
    if (extracted && typeof extracted === 'object' && !Array.isArray(extracted)) {
      const vendor = (extracted as Record<string, unknown>).vendor_name;
      if (vendor != null && String(vendor).trim()) return String(vendor).trim();
    }
    return (caseItem.counterparty_name ?? caseItem.client_vendor_name ?? '').trim();
  }

  $: vendorName = item ? resolveVendorName(item) : '';
  $: reviewSnapshot = item ? manualReviewDetails(item) : { missing: [], confidence: null, extracted: {} };
  $: showTeachPanel =
    (item?.status === 'manual_review' || item?.status === 'on_hold') &&
    reviewSnapshot.missing.length > 0 &&
    vendorName.length > 0;
  $: canRetryWithHints = showTeachPanel && savedHintFields.size > 0;

  $: if (item && showTeachPanel) {
    const names = reviewSnapshot.missing;
    const key = `${item.id}:${names.join(',')}`;
    if (key !== teachFieldsKey) {
      teachFieldsKey = key;
      teachFields = names.map((field_name) => ({
        field_name,
        field_label: '',
        example_value: '',
        date_format: '',
        saving: false,
      }));
    }
  }

  onMount(load);

  async function load() {
    error = '';
    retryMessage = '';
    teachMessage = '';
    savedHintFields = new Set();
    teachFields = [];
    teachFieldsKey = '';
    try {
      [item, timeline] = await Promise.all([fetchCase(id), fetchCaseTimeline(id)]);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Not found';
    }
  }

  function setTeachRowSaving(fieldName: string, saving: boolean) {
    teachFields = teachFields.map((r) =>
      r.field_name === fieldName ? { ...r, saving } : r
    );
  }

  async function saveHint(row: TeachFieldForm) {
    if (!item || !vendorName || row.saving) return;
    const field_label = row.field_label.trim();
    if (!field_label) {
      teachMessage = 'Field label on document is required.';
      return;
    }
    setTeachRowSaving(row.field_name, true);
    teachMessage = '';
    error = '';
    const body: VendorExtractionHintCreate = {
      vendor_name: vendorName,
      field_name: row.field_name,
      field_label,
      example_value: row.example_value.trim() || null,
      date_format: DATE_FIELD_NAMES.has(row.field_name)
        ? row.date_format.trim() || null
        : null,
    };
    try {
      await saveVendorExtractionHint(body);
      savedHintFields = new Set([...savedHintFields, row.field_name]);
      teachMessage = `Saved hint for ${row.field_name.replaceAll('_', ' ')}. You can retry processing with hints below.`;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Could not save hint';
    } finally {
      setTeachRowSaving(row.field_name, false);
    }
  }

  async function handleOverridePost() {
    if (!item || !glPeriodId || overrideSubmitting) return;
    const reason = overrideReason.trim();
    if (!reason) {
      error = 'Override reason is required.';
      return;
    }
    overrideSubmitting = true;
    error = '';
    try {
      const result = await overrideGlPeriodPost(glPeriodId, id, reason);
      retryMessage = `Override authorized — case requeued (${result.status}).`;
      showOverrideModal = false;
      overrideReason = '';
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Override failed';
    } finally {
      overrideSubmitting = false;
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

  function manualReviewDetails(caseItem: CaseItem) {
    const meta = caseItem.workflow_metadata ?? {};
    const missing = meta.missing_fields;
    const extracted = meta.extracted_fields;
    return {
      missing: Array.isArray(missing) ? missing.map(String) : [],
      confidence:
        typeof meta.extraction_confidence === 'number'
          ? meta.extraction_confidence
          : meta.extraction_confidence != null
            ? Number(meta.extraction_confidence)
            : null,
      extracted:
        extracted && typeof extracted === 'object' && !Array.isArray(extracted)
          ? (extracted as Record<string, string | null>)
          : {},
    };
  }

  function formatConfidence(value: number): string {
    if (Number.isNaN(value)) return '—';
    return value.toFixed(2);
  }

  async function handleApprove() {
    if (!item?.pending_approval_id || approvalBusy) return;
    approvalBusy = true;
    approvalMessage = '';
    error = '';
    try {
      await approve(item.pending_approval_id, approvalNote || 'Approved');
      approvalMessage = 'Approved — journal posted.';
      approvalNote = '';
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Approve failed';
    } finally {
      approvalBusy = false;
    }
  }

  async function handleReject() {
    if (!item?.pending_approval_id || approvalBusy) return;
    const reason = approvalReason.trim();
    if (!reason) {
      error = 'Rejection reason is required.';
      return;
    }
    approvalBusy = true;
    approvalMessage = '';
    error = '';
    try {
      await reject(item.pending_approval_id, reason);
      approvalMessage = 'Rejected — submitter notified.';
      approvalReason = '';
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Reject failed';
    } finally {
      approvalBusy = false;
    }
  }

  async function handleEscalate() {
    if (!item?.pending_approval_id || approvalBusy) return;
    approvalBusy = true;
    approvalMessage = '';
    error = '';
    try {
      await escalateToCfo(item.pending_approval_id, approvalNote || undefined);
      approvalMessage = 'Escalated to CFO.';
      approvalNote = '';
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Escalate failed';
    } finally {
      approvalBusy = false;
    }
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
    {#if item.status === 'manual_review' || item.status === 'on_hold'}
      {@const review = manualReviewDetails(item)}
      {#if review.missing.length > 0 || review.confidence != null || Object.keys(review.extracted).length > 0}
        <section class="review-box">
          <h2>Manual review details</h2>
          {#if review.confidence != null}
            <p><strong>Extraction confidence:</strong> {formatConfidence(review.confidence)}</p>
          {/if}
          {#if review.missing.length > 0}
            <p><strong>Missing fields:</strong></p>
            <ul>
              {#each review.missing as field}
                <li>{field.replaceAll('_', ' ')}</li>
              {/each}
            </ul>
          {/if}
          {#if Object.keys(review.extracted).length > 0}
            <p><strong>Extracted:</strong></p>
            <dl class="extracted">
              {#each Object.entries(review.extracted) as [key, value]}
                <dt>{key.replaceAll('_', ' ')}</dt>
                <dd>{value ?? '—'}</dd>
              {/each}
            </dl>
          {/if}
        </section>
      {/if}
      {#if showTeachPanel}
        <section class="teach-box">
          <h2>Teach the Agent</h2>
          <p class="hint">
            Document vendor: <strong>{vendorName}</strong>. Tell the extractor how each missing
            field appears on this vendor&apos;s documents.
          </p>
          {#each teachFields as row}
            <div class="teach-field">
              <h3>{row.field_name.replaceAll('_', ' ')}</h3>
              <label>
                Field label on document
                <input
                  type="text"
                  bind:value={row.field_label}
                  placeholder="e.g. Date and time"
                />
              </label>
              <label>
                Example value
                <input
                  type="text"
                  bind:value={row.example_value}
                  placeholder="e.g. 24 Apr 2025 07:42 PM"
                />
              </label>
              {#if DATE_FIELD_NAMES.has(row.field_name)}
                <label>
                  Date format
                  <input
                    type="text"
                    bind:value={row.date_format}
                    placeholder="e.g. DD Mon YYYY HH:MM AM/PM"
                  />
                </label>
              {/if}
              <button
                type="button"
                class="save-hint"
                disabled={row.saving}
                onclick={() => saveHint(row)}
              >
                {row.saving ? 'Saving…' : 'Save hint'}
              </button>
            </div>
          {/each}
          {#if teachMessage}
            <p class="hint success">{teachMessage}</p>
          {/if}
          {#if canRetryWithHints}
            <button type="button" class="retry" disabled={retrying} onclick={handleRetry}>
              {retrying ? 'Requeuing…' : 'Retry with hints'}
            </button>
          {/if}
        </section>
      {/if}
    {/if}
    <p>{item.subject}</p>
    <p>Client / Vendor: {clientVendorColumnValue(item)}</p>
    <p>Processing time: {item.processing_time_minutes != null ? `${item.processing_time_minutes} min` : '—'}</p>
    <p>Created: {new Date(item.created_at).toLocaleString()}</p>
    {#if item.last_activity_at}
      <p>Last activity: {new Date(item.last_activity_at).toLocaleString()}</p>
    {/if}
    {#if item.sla_deadline}
      <p>SLA deadline: {new Date(item.sla_deadline).toLocaleString()}</p>
    {/if}
    {#if canOverrideGl}
      <button type="button" class="override" onclick={() => (showOverrideModal = true)}>
        Override &amp; post
      </button>
      <p class="hint">This case is blocked because the posting date falls in a closed GL period.</p>
    {/if}
    {#if (retryableStatuses.has(item.status) || canRetryAfterReopen) && !canRetryWithHints}
      <button type="button" class="retry" disabled={retrying} onclick={handleRetry}>
        {retrying ? 'Requeuing…' : 'Retry processing'}
      </button>
      {#if canRetryAfterReopen}
        <p class="hint">The GL period for this posting date has been reopened — you can reprocess without an override.</p>
      {/if}
    {/if}
    {#if retryMessage}
      <p class="hint success">{retryMessage}</p>
    {/if}
    {#if approvalMessage}
      <p class="hint success">{approvalMessage}</p>
    {/if}
    {#if item.status === 'pending_approval' && bindingTier != null}
      <section class="approval-box">
        <h2>Binding authority approval</h2>
        <p>
          Tier {bindingTier}
          {#if bindingEscalated}
            · escalated to CFO
          {/if}
        </p>
        {#if showAccApprovalActions || showCfoApprovalActions}
          <label>
            Note (optional for approve / escalate)
            <textarea bind:value={approvalNote} rows="2" placeholder="Approval note"></textarea>
          </label>
          <label>
            Rejection reason
            <textarea bind:value={approvalReason} rows="2" placeholder="Required to reject"></textarea>
          </label>
          <div class="approval-actions">
            <button type="button" class="approve" disabled={approvalBusy} onclick={handleApprove}>
              {approvalBusy ? 'Working…' : 'Approve'}
            </button>
            <button type="button" class="reject" disabled={approvalBusy} onclick={handleReject}>
              Reject
            </button>
            {#if showAccApprovalActions}
              <button type="button" class="escalate" disabled={approvalBusy} onclick={handleEscalate}>
                Escalate to CFO
              </button>
            {/if}
          </div>
        {:else if item.pending_approval_id}
          <p class="hint">
            This case is awaiting approval by another role.
            <a href={`/approvals/${item.pending_approval_id}`}>Open approval</a>
          </p>
        {/if}
      </section>
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

{#if showOverrideModal}
  <div class="modal-backdrop" role="presentation">
    <div class="modal card">
      <h2>Override &amp; post to closed period</h2>
      <p>Provide a reason for retroactive posting. This is recorded in the audit log.</p>
      <label>
        Override reason
        <textarea bind:value={overrideReason} rows="4" placeholder="e.g. Year-end adjustment approved by CFO"></textarea>
      </label>
      <div class="modal-actions">
        <button type="button" disabled={overrideSubmitting} onclick={handleOverridePost}>
          {overrideSubmitting ? 'Submitting…' : 'Confirm override'}
        </button>
        <button type="button" class="muted" onclick={() => (showOverrideModal = false)}>Cancel</button>
      </div>
    </div>
  </div>
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
  .override {
    margin-top: 0.75rem;
    margin-right: 0.5rem;
    padding: 0.5rem 1rem;
    border: 1px solid #1d4ed8;
    border-radius: 6px;
    background: #eff6ff;
    color: #1e40af;
    font-weight: 600;
    cursor: pointer;
  }
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 50;
  }
  .modal {
    max-width: 440px;
    width: 90%;
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1rem;
  }
  .modal textarea {
    width: 100%;
    box-sizing: border-box;
    margin-top: 0.35rem;
  }
  .modal-actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 1rem;
  }
  .muted {
    background: #f1f5f9;
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
  .review-box {
    margin-top: 1rem;
    padding: 0.75rem 1rem;
    border: 1px solid #fdba74;
    border-radius: 6px;
    background: #fffbeb;
  }
  .review-box h2 {
    margin: 0 0 0.5rem;
    font-size: 1rem;
  }
  .teach-box {
    margin-top: 1rem;
    padding: 1rem;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    background: #eff6ff;
  }
  .teach-box h2 {
    margin-top: 0;
    font-size: 1rem;
  }
  .teach-field {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid #dbeafe;
  }
  .teach-field h3 {
    margin: 0 0 0.5rem;
    font-size: 0.95rem;
    text-transform: capitalize;
  }
  .teach-field label {
    display: block;
    margin-bottom: 0.5rem;
    font-size: 0.875rem;
  }
  .teach-field input {
    display: block;
    width: 100%;
    box-sizing: border-box;
    margin-top: 0.25rem;
    padding: 0.4rem 0.5rem;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
  }
  .save-hint {
    margin-top: 0.25rem;
    padding: 0.4rem 0.75rem;
    border: 1px solid #2563eb;
    border-radius: 6px;
    background: #fff;
    color: #1d4ed8;
    font-weight: 600;
    cursor: pointer;
  }
  .save-hint:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  .review-box ul {
    margin: 0.25rem 0 0.75rem;
    padding-left: 1.25rem;
  }
  .extracted {
    display: grid;
    grid-template-columns: minmax(8rem, auto) 1fr;
    gap: 0.25rem 0.75rem;
    margin: 0.25rem 0 0;
  }
  .extracted dt {
    font-weight: 600;
    color: #475569;
  }
  .extracted dd {
    margin: 0;
  }
  .approval-box {
    margin-top: 1rem;
    padding: 0.75rem 1rem;
    border: 1px solid #93c5fd;
    border-radius: 6px;
    background: #eff6ff;
  }
  .approval-box h2 {
    margin: 0 0 0.5rem;
    font-size: 1rem;
  }
  .approval-box textarea {
    width: 100%;
    box-sizing: border-box;
    margin-top: 0.35rem;
  }
  .approval-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 0.75rem;
  }
  .approve {
    padding: 0.5rem 1rem;
    border: 1px solid #15803d;
    border-radius: 6px;
    background: #f0fdf4;
    color: #166534;
    font-weight: 600;
    cursor: pointer;
  }
  .reject {
    padding: 0.5rem 1rem;
    border: 1px solid #b91c1c;
    border-radius: 6px;
    background: #fef2f2;
    color: #991b1b;
    font-weight: 600;
    cursor: pointer;
  }
  .escalate {
    padding: 0.5rem 1rem;
    border: 1px solid #1d4ed8;
    border-radius: 6px;
    background: #fff;
    color: #1e40af;
    font-weight: 600;
    cursor: pointer;
  }
</style>
