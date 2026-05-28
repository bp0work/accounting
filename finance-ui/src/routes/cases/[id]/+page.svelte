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
    confirmParsing,
    rejectParsing,
    overrideGlPeriodPost,
    type CaseItem,
    type ParsingConfirmationFields,
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
  let parsingBusy = false;
  let parsingMessage = '';
  let rejectParsingReason = '';

  const confirmParsingRoles = new Set([
    'accounts_clerk',
    'finance_manager',
    'cfo',
    'finance_director',
  ]);

  let parsingFormKey = '';
  let parsingForm: ParsingConfirmationFields = {
    document_type: 'invoice',
    document_number: '',
    document_date: '',
    due_date: '',
    vendor_name: '',
    total_amount: '',
    gst_amount: '',
    currency: 'SGD',
    payment_terms: '',
    sender_validated: false,
  };

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
  $: canConfirmParsing =
    item?.status === 'pending_confirmation' && confirmParsingRoles.has(role);
  $: isExpenseConfirm = item?.type === 'expense_claim';

  $: if (item?.status === 'pending_confirmation') {
    const raw = item.workflow_metadata?.extracted_fields;
    const key = `${item.id}:${JSON.stringify(raw ?? {})}`;
    if (key !== parsingFormKey && raw && typeof raw === 'object' && !Array.isArray(raw)) {
      parsingFormKey = key;
      const f = raw as Record<string, unknown>;
      parsingForm = {
        document_type: String(f.document_type ?? 'invoice'),
        document_number: f.document_number != null ? String(f.document_number) : '',
        document_date: String(f.document_date ?? f.invoice_date ?? ''),
        due_date: f.due_date != null ? String(f.due_date) : '',
        vendor_name: f.vendor_name != null ? String(f.vendor_name) : '',
        total_amount: f.total_amount != null ? String(f.total_amount) : '',
        gst_amount: String(f.gst_amount ?? f.tax_amount ?? ''),
        currency: String(f.currency ?? 'SGD'),
        payment_terms: f.payment_terms != null ? String(f.payment_terms) : '',
        sender_validated:
          String(f.sender_validated ?? 'false').toLowerCase() === 'true',
      };
    }
  }

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

  async function handleConfirmParsing() {
    if (!item || parsingBusy || !canConfirmParsing) return;
    parsingBusy = true;
    parsingMessage = '';
    error = '';
    try {
      const body: ParsingConfirmationFields = {
        ...parsingForm,
        document_number: parsingForm.document_number?.trim() || null,
        document_date: parsingForm.document_date?.trim() || null,
        due_date: parsingForm.due_date?.trim() || null,
        vendor_name: parsingForm.vendor_name?.trim() || null,
        total_amount: parsingForm.total_amount?.trim() || null,
        gst_amount: parsingForm.gst_amount?.trim() || null,
        payment_terms: parsingForm.payment_terms?.trim() || null,
      };
      const result = await confirmParsing(id, body);
      parsingMessage = `Parsing confirmed (${result.correction_count} correction(s)) — case requeued.`;
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Confirm parsing failed';
    } finally {
      parsingBusy = false;
    }
  }

  async function handleRejectParsing() {
    if (!item || parsingBusy || !canConfirmParsing) return;
    const reason = rejectParsingReason.trim();
    if (!reason) {
      error = 'Rejection reason is required.';
      return;
    }
    parsingBusy = true;
    parsingMessage = '';
    error = '';
    try {
      await rejectParsing(id, reason);
      parsingMessage = 'Parsing rejected — submitter notified.';
      rejectParsingReason = '';
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Reject parsing failed';
    } finally {
      parsingBusy = false;
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
      parsing_completed: 'Parsing completed',
      parsing_awaiting_confirmation: 'Awaiting parsing confirmation',
      parsing_confirmed: 'Parsing confirmed',
      parsing_rejected: 'Parsing rejected',
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
    {#if item.status === 'pending_confirmation'}
      <section class="confirm-box">
        <h2>Confirm Parsing</h2>
        {#if canConfirmParsing}
          <p class="hint">
            Review extracted fields before duplicate check and validation continue.
          </p>
          {#if !isExpenseConfirm}
            <label>
              Document type
              <select bind:value={parsingForm.document_type}>
                <option value="invoice">Invoice</option>
                <option value="credit_note">Credit note</option>
                <option value="debit_note">Debit note</option>
              </select>
            </label>
            <label>
              Document number
              <input type="text" bind:value={parsingForm.document_number} />
            </label>
            <label>
              Document date
              <input type="date" bind:value={parsingForm.document_date} />
            </label>
            <label>
              Due date
              <input type="date" bind:value={parsingForm.due_date} />
            </label>
          {:else}
            <p class="hint">Expense claim — confirm totals and claimant below.</p>
          {/if}
          <label>
            {isExpenseConfirm ? 'Claimant' : 'Vendor name'}
            <input type="text" bind:value={parsingForm.vendor_name} />
          </label>
          <label>
            Total amount
            <input type="number" step="0.01" bind:value={parsingForm.total_amount} />
          </label>
          {#if !isExpenseConfirm}
            <label>
              GST amount
              <input type="number" step="0.01" bind:value={parsingForm.gst_amount} />
            </label>
            <label>
              Currency
              <select bind:value={parsingForm.currency}>
                <option value="SGD">SGD</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="GBP">GBP</option>
                <option value="AUD">AUD</option>
              </select>
            </label>
            <label>
              Payment terms
              <select bind:value={parsingForm.payment_terms}>
                <option value="">—</option>
                <option value="immediate">Immediate</option>
                <option value="net_7">Net 7</option>
                <option value="net_14">Net 14</option>
                <option value="net_30">Net 30</option>
                <option value="net_60">Net 60</option>
                <option value="net_90">Net 90</option>
              </select>
            </label>
            <label class="toggle-row">
              <input type="checkbox" bind:checked={parsingForm.sender_validated} />
              Validated by sender
            </label>
          {/if}
          <div class="confirm-actions">
            <button
              type="button"
              class="approve"
              disabled={parsingBusy}
              onclick={handleConfirmParsing}
            >
              {parsingBusy ? 'Working…' : 'Confirm & Continue'}
            </button>
            <label class="reject-reason">
              Rejection reason
              <textarea
                bind:value={rejectParsingReason}
                rows="2"
                placeholder="Required to reject"
              ></textarea>
            </label>
            <button
              type="button"
              class="reject"
              disabled={parsingBusy}
              onclick={handleRejectParsing}
            >
              Reject
            </button>
          </div>
        {:else}
          <p class="hint">Awaiting confirmation by Accounts or Finance leadership.</p>
        {/if}
        {#if parsingMessage}
          <p class="hint success">{parsingMessage}</p>
        {/if}
      </section>
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
  .confirm-box {
    margin-top: 1rem;
    padding: 1rem;
    border: 1px solid #93c5fd;
    border-radius: 8px;
    background: #eff6ff;
  }
  .confirm-box h2 {
    margin-top: 0;
  }
  .confirm-box label {
    display: block;
    margin-top: 0.65rem;
    font-size: 0.9rem;
  }
  .confirm-box input,
  .confirm-box select,
  .confirm-box textarea {
    display: block;
    width: 100%;
    max-width: 320px;
    margin-top: 0.25rem;
    box-sizing: border-box;
  }
  .confirm-actions {
    margin-top: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    align-items: flex-start;
  }
  .confirm-actions .approve {
    padding: 0.5rem 1rem;
    border-radius: 6px;
    border: 1px solid #15803d;
    background: #dcfce7;
    color: #166534;
    font-weight: 600;
    cursor: pointer;
  }
  .confirm-actions .reject {
    padding: 0.5rem 1rem;
    border-radius: 6px;
    border: 1px solid #b91c1c;
    background: #fee2e2;
    color: #991b1b;
    font-weight: 600;
    cursor: pointer;
  }
  .toggle-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
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
