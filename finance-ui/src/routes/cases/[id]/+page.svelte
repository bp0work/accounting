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
    respondToCaseEscalation,
    confirmParsing,
    rejectParsing,
    overrideGlPeriodPost,
    type CaseItem,
    type JournalEntryLineDetail,
    type ParsingConfirmationFields,
    type TimelineEntry,
  } from '$lib/api/cases';
  import {
    caseReasonCode,
    escalationActionConfig,
    hasPendingEscalation,
    shouldRetryViaEscalationRespond,
    isParsingIncompleteReasonCode,
    manualActionButtonClass,
    parsingIncompleteCommentLabel,
    normalizeEscalationDisplayCopy,
    showManualReviewPanel,
    type EscalationUiAction,
  } from '$lib/ap-escalation-actions';
  import {
    saveVendorExtractionHint,
    type VendorExtractionHintCreate,
  } from '$lib/api/vendor-hints';
  import {
    vendorHintDateFormatInputLabel,
    vendorHintExampleValueInputLabel,
    vendorHintFieldLabelInputLabel,
    vendorHintFieldLabelRequiredMessage,
  } from '$lib/vendor-hint-labels';
  import { listCoaAccounts, type CoaAccountItem } from '$lib/api/coa';
  import {
    caseStatusLabel,
    extractedFieldLabel,
    EXTRACTED_FIELD_DISPLAY_ORDER,
    submittedByDisplay,
  } from '$lib/case-labels';
  import { approve, escalateToCfo, reject } from '$lib/api/approvals';
  import { formatAmount, formatCount, formatExtractedFieldValue } from '$lib/format';
  import {
    hasExtractedGlAccountId,
    normalizeExtractedFields,
    trimExtractedOptional,
  } from '$lib/extracted-fields-display';
  import {
    isGstJournalLine,
    journalLineCoaOptionsForLine,
    journalLineCoaType,
    parseJournalMoney,
    resolveJournalLineAccountId,
  } from '$lib/journal-line-coa';
  import { hasPermission } from '$lib/permissions';
  import { sessionUser } from '$lib/stores/session';

  let item: CaseItem | null = null;
  let approvalNote = '';
  let approvalReason = '';
  let approvalLoadingAction: 'approve' | 'reject' | 'escalate' | null = null;
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
  let parsingLoadingAction: 'confirm' | 'reject' | null = null;
  let parsingMessage = '';
  let rejectParsingReason = '';
  let escalationComment = '';
  let manualLoadingAction: EscalationUiAction | null = null;
  let manualActionMessage = '';
  /** Last focused/clicked escalation action — drives comment label on parsing-incomplete panel. */
  let manualCommentFocusAction: EscalationUiAction | null = null;
  let expenseCoaAccounts: CoaAccountItem[] = [];
  let expenseCoaLoading = false;
  let liabilityCoaAccounts: CoaAccountItem[] = [];
  let journalCoaLoading = false;
  /** Per-line COA selection keyed by journal line_number */
  let journalLineAccountIds: Record<number, string> = {};
  /** Original account_id per line when journal loaded — used for approve diff only */
  let journalLineAccountDefaults: Record<number, string> = {};
  let journalAccountSyncKey = '';
  let journalCoaSyncKey = '';
  let reviewCoaAccounts: CoaAccountItem[] = [];

  const confirmParsingRoles = new Set([
    'accounts_manager',
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
    tax_amount: '',
    currency: 'SGD',
    exchange_rate: '',
    payment_terms: '',
    business_purpose: '',
    gl_account_id: '',
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
  let teachPanelExpanded = false;

  const DATE_FIELD_NAMES = new Set([
    'document_date',
    'invoice_date',
    'due_date',
    'payment_due_date',
  ]);

  const overrideRoles = new Set(['cfo', 'finance_manager']);
  const tier2Roles = new Set(['accounts_manager', 'finance_officer', 'finance_manager']);
  const executiveRoles = new Set(['cfo', 'finance_director']);

  function findCoaAccount(id: string, ...lists: CoaAccountItem[][]): CoaAccountItem | undefined {
    for (const list of lists) {
      const hit = list.find((a) => String(a.id) === id);
      if (hit) return hit;
    }
    return undefined;
  }

  function journalLineCoaOptions(type: 'expense' | 'liability'): CoaAccountItem[] {
    return type === 'expense' ? expenseCoaAccounts : liabilityCoaAccounts;
  }

  function setJournalLineAccountId(lineNumber: number, accountId: string) {
    journalLineAccountIds = { ...journalLineAccountIds, [lineNumber]: accountId };
  }

  $: role = ($sessionUser?.role_name ?? '').toLowerCase();
  $: bindingTier = item?.current_approval_tier ?? null;
  $: bindingEscalated = Boolean(item?.binding_escalated_to_cfo);
  const journalApprovalStatuses = new Set(['pending_approval', 'journal_pending_approval']);
  $: awaitingJournalApproval =
    !!item && journalApprovalStatuses.has(item.status);
  $: journalApproval = item?.journal_entry ?? null;

  $: displayedJournalLines = (() => {
    const base = journalApproval?.lines ?? [];
    if (base.length === 0) return [];
    return base.map((line) => {
      const coaType = journalLineCoaType(line);
      const selectedId = journalLineAccountIds[line.line_number];
      if (!coaType || !selectedId) return line;
      const acct = findCoaAccount(selectedId, journalLineCoaOptions(coaType));
      if (!acct) return line;
      return {
        ...line,
        account_id: String(acct.id),
        account_code: acct.account_code,
        account_name: acct.account_name,
      };
    });
  })();

  $: journalHeaderExGst = (() => {
    const expenseLine = displayedJournalLines.find((l) => l.line_number === 1 && l.debit);
    if (!expenseLine?.debit) return null;
    return formatAmount(parseJournalMoney(expenseLine.debit));
  })();

  $: journalHeaderGst = (() => {
    let sum = 0;
    let any = false;
    for (const line of displayedJournalLines) {
      if (isGstJournalLine(line) && line.debit) {
        sum += parseJournalMoney(line.debit);
        any = true;
      }
    }
    return any && sum > 0 ? formatAmount(sum) : null;
  })();

  $: journalHeaderTotal = (() => {
    let sum = 0;
    let any = false;
    for (const line of displayedJournalLines) {
      if (line.credit) {
        const v = parseJournalMoney(line.credit);
        if (v > 0) {
          sum += v;
          any = true;
        }
      }
    }
    return any ? formatAmount(sum) : null;
  })();
  $: showAccApprovalActions =
    awaitingJournalApproval &&
    tier2Roles.has(role) &&
    bindingTier === 2 &&
    !bindingEscalated &&
    !!item?.pending_approval_id;
  $: showCfoApprovalActions =
    awaitingJournalApproval &&
    executiveRoles.has(role) &&
    (bindingEscalated || (bindingTier != null && bindingTier >= 3)) &&
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
  const transientHermesStatuses = new Set(['on_hold', 'exception', 'manual_review']);
  const transientHermesCodes = new Set(['HERMES_TIMEOUT', 'HERMES_UNAVAILABLE']);

  /** Hermes timeout/unavailable — match metadata codes or API error_reason text. */
  function trimOptional(value: unknown): string | null {
    if (value == null) return null;
    const s = typeof value === 'string' ? value.trim() : String(value).trim();
    return s || null;
  }

  function transientHermesCode(caseItem: CaseItem): string | null {
    const meta = caseItem.workflow_metadata ?? {};
    for (const key of ['error_code', 'error_type', 'reason_code'] as const) {
      const code = String(meta[key] ?? '')
        .trim()
        .toUpperCase();
      if (transientHermesCodes.has(code)) return code;
    }
    const err = String(caseItem.error_reason ?? '').toUpperCase();
    if (err.includes('HERMES_TIMEOUT')) return 'HERMES_TIMEOUT';
    if (err.includes('HERMES_UNAVAILABLE')) return 'HERMES_UNAVAILABLE';
    return null;
  }

  function isTransientHermesCase(caseItem: CaseItem): boolean {
    if (!transientHermesStatuses.has(caseItem.status)) return false;
    return transientHermesCode(caseItem) !== null;
  }

  $: canRetryTransientHermes = item ? isTransientHermesCase(item) : false;
  $: showStandardRetry =
    item &&
    (retryableStatuses.has(item.status) || canRetryAfterReopen || canRetryTransientHermes) &&
    (!canRetryWithHints || canRetryTransientHermes);

  $: caseId = $page.params.id ?? '';

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
  $: coaLabelResolutionKey = `${expenseCoaAccounts.length}:${reviewCoaAccounts.length}:${liabilityCoaAccounts.length}`;
  $: showTeachPanel =
    (item?.status === 'manual_review' || item?.status === 'on_hold') &&
    reviewSnapshot.missing.length > 0 &&
    vendorName.length > 0 &&
    (item.type !== 'expense_claim' ||
      Boolean(item?.workflow_metadata?.parsing_confirmed_at));
  $: canRetryWithHints = showTeachPanel && savedHintFields.size > 0;
  $: isExpenseConfirm = item?.type === 'expense_claim';
  $: canWriteParsingConfirm = isExpenseConfirm
    ? hasPermission('expenses:write')
    : hasPermission('cases:write');
  $: canConfirmParsing =
    item?.status === 'pending_confirmation' &&
    confirmParsingRoles.has(role) &&
    canWriteParsingConfirm;
  $: parsingConfirmReadOnly =
    item?.status === 'pending_confirmation' &&
    confirmParsingRoles.has(role) &&
    !canWriteParsingConfirm &&
    (isExpenseConfirm
      ? hasPermission('expenses:read')
      : hasPermission('cases:read'));

  $: parsingAmountExTax = (() => {
    if (!isExpenseConfirm) return '';
    const total = Number(String(parsingForm.total_amount).replace(/,/g, ''));
    const tax = Number(String(parsingForm.tax_amount).replace(/,/g, ''));
    if (!Number.isFinite(total) || total === 0) return '';
    const ex = total - (Number.isFinite(tax) ? tax : 0);
    return formatAmount(ex);
  })();

  $: reasonCode = item ? caseReasonCode(item) : '';
  $: showActionRequiredPanel = item ? showManualReviewPanel(item, role) : false;
  $: manualActionConfig = item && showActionRequiredPanel ? escalationActionConfig(reasonCode, item) : null;
  $: isParsingIncompleteEscalation = isParsingIncompleteReasonCode(reasonCode);
  $: parsingIncompleteMissingFields = item ? manualReviewDetails(item).missing : [];
  $: pendingEscalation = item ? hasPendingEscalation(item) : false;
  $: showCounterpartyLink =
    reasonCode === 'AP_CONTRACT_MISSING' ||
    reasonCode === 'AP_VENDOR_INACTIVE' ||
    reasonCode === 'AP_VENDOR_NOT_FOUND' ||
    reasonCode === 'EXP_SUBMITTER_NOT_FOUND' ||
    reasonCode === 'EXP_SUBMITTER_INACTIVE';

  $: if (item?.status === 'pending_confirmation') {
    const raw = item.workflow_metadata?.extracted_fields;
    const key = `${item.id}:${JSON.stringify(raw ?? {})}`;
    if (key !== parsingFormKey && raw && typeof raw === 'object' && !Array.isArray(raw)) {
      parsingFormKey = key;
      const f = raw as Record<string, unknown>;
      parsingForm = {
        document_type: String(f.document_type ?? (isExpenseConfirm ? 'receipt' : 'invoice')),
        document_number: f.document_number != null ? String(f.document_number) : '',
        document_date: String(f.document_date ?? f.invoice_date ?? ''),
        due_date: f.due_date != null ? String(f.due_date) : '',
        vendor_name: String(f.vendor_name ?? f.merchant_name ?? ''),
        total_amount: f.total_amount != null ? String(f.total_amount) : '',
        tax_amount: String(f.tax_amount ?? f.gst_amount ?? ''),
        currency: String(f.currency ?? 'SGD'),
        exchange_rate: f.exchange_rate != null ? String(f.exchange_rate) : '',
        payment_terms: f.payment_terms != null ? String(f.payment_terms) : '',
        business_purpose: f.business_purpose != null ? String(f.business_purpose) : '',
        gl_account_id: f.gl_account_id != null ? String(f.gl_account_id) : '',
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

  async function loadReviewCoaAccounts() {
    try {
      reviewCoaAccounts = await listCoaAccounts({ is_active: true });
    } catch {
      reviewCoaAccounts = [];
    }
  }

  async function loadExpenseCoaAccounts() {
    expenseCoaLoading = true;
    try {
      expenseCoaAccounts = await listCoaAccounts({ account_type: 'expense', is_active: true });
    } catch {
      expenseCoaAccounts = [];
    } finally {
      expenseCoaLoading = false;
    }
  }

  async function loadJournalCoaAccounts() {
    journalCoaLoading = true;
    try {
      const [expense, liability] = await Promise.all([
        listCoaAccounts({ account_type: 'expense', is_active: true }),
        listCoaAccounts({ account_type: 'liability', is_active: true }),
      ]);
      expenseCoaAccounts = expense;
      liabilityCoaAccounts = liability;
    } catch {
      expenseCoaAccounts = [];
      liabilityCoaAccounts = [];
    } finally {
      journalCoaLoading = false;
      syncJournalLineAccountIds();
    }
  }

  function syncJournalLineAccountIds() {
    if (!journalApproval?.lines?.length) {
      journalLineAccountIds = {};
      journalLineAccountDefaults = {};
      return;
    }
    const next: Record<number, string> = {};
    const defaults: Record<number, string> = {};
    for (const line of journalApproval.lines) {
      const coaType = journalLineCoaType(line);
      if (!coaType) continue;
      const accountId = resolveJournalLineAccountId(
        line,
        coaType,
        expenseCoaAccounts,
        liabilityCoaAccounts,
        journalApproval,
      );
      if (!accountId) continue;
      next[line.line_number] = accountId;
      defaults[line.line_number] = accountId;
    }
    journalLineAccountIds = next;
    journalLineAccountDefaults = defaults;
  }

  $: if (journalApproval) {
    const syncKey = journalApproval.journal_entry_id ?? 'journal';
    if (syncKey !== journalAccountSyncKey) {
      journalAccountSyncKey = syncKey;
      syncJournalLineAccountIds();
    }
  }

  $: if (journalApproval && !journalCoaLoading) {
    const coaKey = `${journalApproval.journal_entry_id ?? 'journal'}:${expenseCoaAccounts.length}:${liabilityCoaAccounts.length}`;
    if (coaKey !== journalCoaSyncKey) {
      journalCoaSyncKey = coaKey;
      syncJournalLineAccountIds();
    }
  }

  async function load() {
    error = '';
    retryMessage = '';
    teachMessage = '';
    savedHintFields = new Set();
    teachFields = [];
    teachFieldsKey = '';
    try {
      [item, timeline] = await Promise.all([fetchCase(caseId), fetchCaseTimeline(caseId)]);
      const extractedForCoa = item
        ? normalizeExtractedFields(item.workflow_metadata?.extracted_fields)
        : {};
      const manualReviewNeedsCoa =
        item != null &&
        (item.status === 'manual_review' || item.status === 'on_hold') &&
        hasExtractedGlAccountId(extractedForCoa);

      if (item?.status === 'pending_confirmation' && item.type === 'expense_claim') {
        await loadExpenseCoaAccounts();
        reviewCoaAccounts = [];
      } else if (item && journalApprovalStatuses.has(item.status)) {
        await loadJournalCoaAccounts();
        reviewCoaAccounts = [];
      } else if (manualReviewNeedsCoa) {
        await loadReviewCoaAccounts();
        if (item.type === 'expense_claim') {
          await loadExpenseCoaAccounts();
        } else {
          expenseCoaAccounts = [];
          liabilityCoaAccounts = [];
        }
      } else {
        expenseCoaAccounts = [];
        liabilityCoaAccounts = [];
        reviewCoaAccounts = [];
      }
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
      teachMessage = vendorHintFieldLabelRequiredMessage(row.field_name);
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
      const result = await overrideGlPeriodPost(glPeriodId, caseId, reason);
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
    if (!item || parsingLoadingAction !== null || !canConfirmParsing) return;
    parsingLoadingAction = 'confirm';
    parsingMessage = '';
    error = '';
    try {
      const currency = trimOptional(parsingForm.currency)?.toUpperCase() ?? 'SGD';
      if (currency !== 'SGD' && !trimOptional(parsingForm.exchange_rate)) {
        error = `Exchange rate is required when currency is ${currency}.`;
        return;
      }
      const body: ParsingConfirmationFields = {
        ...parsingForm,
        document_number: trimOptional(parsingForm.document_number),
        document_date: trimOptional(parsingForm.document_date),
        due_date: trimOptional(parsingForm.due_date),
        vendor_name: trimOptional(parsingForm.vendor_name),
        total_amount: trimOptional(parsingForm.total_amount),
        tax_amount: trimOptional(parsingForm.tax_amount),
        exchange_rate: trimOptional(parsingForm.exchange_rate),
        payment_terms: trimOptional(parsingForm.payment_terms),
        business_purpose: trimOptional(parsingForm.business_purpose),
        gl_account_id: trimOptional(parsingForm.gl_account_id),
      };
      const result = await confirmParsing(caseId, body);
      parsingMessage = `Parsing confirmed (${result.correction_count} correction(s)) — case requeued.`;
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Confirm parsing failed';
    } finally {
      parsingLoadingAction = null;
    }
  }

  async function handleRejectParsing() {
    if (!item || parsingLoadingAction !== null || !canConfirmParsing) return;
    const reason = rejectParsingReason.trim();
    if (!reason) {
      error = 'Rejection reason is required.';
      return;
    }
    parsingLoadingAction = 'reject';
    parsingMessage = '';
    error = '';
    try {
      await rejectParsing(caseId, reason);
      parsingMessage = 'Parsing rejected — submitter notified.';
      rejectParsingReason = '';
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Reject parsing failed';
    } finally {
      parsingLoadingAction = null;
    }
  }

  async function requeueCaseForProcessing(): Promise<string> {
    if (!item) throw new Error('No case loaded');
    if (shouldRetryViaEscalationRespond(item)) {
      const result = await respondToCaseEscalation(caseId, {
        action: 'retry',
        comment: escalationComment.trim() || null,
      });
      return (
        result.message ??
        'Retry recorded. Case requeued for processing.'
      );
    }
    const result = await retryCase(caseId);
    return `Requeued as ${result.status} (was ${result.previous_status}).`;
  }

  async function handleRetry() {
    if (!item || retrying) return;
    retrying = true;
    retryMessage = '';
    error = '';
    try {
      retryMessage = await requeueCaseForProcessing();
      escalationComment = '';
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Retry failed';
    } finally {
      retrying = false;
    }
  }

  function focusManualComment(action: EscalationUiAction) {
    manualCommentFocusAction = action;
  }

  async function runManualAction(action: EscalationUiAction, label: string) {
    if (!item || manualLoadingAction !== null || retrying || !manualActionConfig) return;
    focusManualComment(action);
    if (action === 'retry') {
      manualLoadingAction = 'retry';
      manualActionMessage = '';
      error = '';
      try {
        manualActionMessage = await requeueCaseForProcessing();
        escalationComment = '';
        await load();
      } catch (e) {
        error = e instanceof Error ? e.message : 'Retry failed';
      } finally {
        manualLoadingAction = null;
      }
      return;
    }
    const comment = escalationComment.trim();
    if (action === 'approve' && manualActionConfig.commentRequiredForPrimary && !comment) {
      error = `A comment or value is required for ${label}.`;
      return;
    }
    if (action === 'request_info' && manualActionConfig.commentRequiredForPrimary && !comment) {
      error = 'Please provide the missing details or instructions.';
      return;
    }
    if (action === 'reject' && manualActionConfig.commentRequiredForReject && !comment) {
      error = 'Rejection reason is required.';
      return;
    }
    if (!pendingEscalation) {
      error = 'No pending escalation for this case — use Retry if the issue was fixed in setup.';
      return;
    }

    manualLoadingAction = action;
    manualActionMessage = '';
    error = '';
    try {
      const result = await respondToCaseEscalation(caseId, {
        action: action as 'approve' | 'reject' | 'request_info',
        comment: comment || null,
      });
      manualActionMessage = result.message ?? `${label} recorded.`;
      escalationComment = '';
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Action failed';
    } finally {
      manualLoadingAction = null;
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
      submitter_verified: 'Submitter verified',
      policy_checked: 'Policy checked',
      receipt_validated: 'Receipt validated',
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
    return formatAmount(value);
  }

  function resolveCoaAccountLabel(accountId: string): string {
    const id = trimExtractedOptional(accountId) ?? accountId;
    const acct = findCoaAccount(
      id,
      expenseCoaAccounts,
      reviewCoaAccounts,
      liabilityCoaAccounts,
    );
    return acct ? `${acct.account_code} — ${acct.account_name}` : id;
  }

  function getExtractedFieldValue(
    extracted: Record<string, string | null>,
    key: string,
  ): string | null {
    switch (key) {
      case 'vendor_name':
        return extracted.vendor_name ?? extracted.merchant_name ?? null;
      case 'document_date':
        return extracted.document_date ?? extracted.invoice_date ?? null;
      case 'document_number':
        return extracted.document_number ?? extracted.invoice_number ?? null;
      case 'tax_amount':
        return extracted.tax_amount ?? extracted.gst_amount ?? null;
      default:
        return extracted[key] ?? null;
    }
  }

  function orderedExtractedDisplayEntries(
    extracted: Record<string, string | null>,
    caseType?: string,
  ): Array<{ key: string; value: string | null }> {
    const entries: Array<{ key: string; value: string | null }> = [];
    for (const key of EXTRACTED_FIELD_DISPLAY_ORDER) {
      const value = getExtractedFieldValue(extracted, key);
      if (!showExtractedReviewField(key, value, extracted, caseType)) continue;
      entries.push({ key, value });
    }
    return entries;
  }

  function showExtractedReviewField(
    key: string,
    value: string | null,
    extracted: Record<string, string | null> = {},
    caseType?: string,
  ): boolean {
    if (
      caseType === 'expense_claim' &&
      (key === 'due_date' || key === 'payment_terms')
    ) {
      return false;
    }
    if (key === 'sgd_amount') {
      const currency = trimOptional(extracted.currency)?.toUpperCase() ?? 'SGD';
      if (currency === 'SGD') return false;
      return trimOptional(value) != null;
    }
    if (
      key === 'exchange_rate' ||
      key === 'tax_amount' ||
      key === 'gst_amount' ||
      key === 'gl_account_id'
    ) {
      return trimOptional(value) != null;
    }
    return true;
  }

  function formatExtractedReviewValue(key: string, value: string | null): string {
    if (key === 'gl_account_id') {
      const accountId = trimOptional(value);
      if (!accountId) return '—';
      return resolveCoaAccountLabel(accountId);
    }
    if (key === 'sender_validated') {
      const normalized = String(value ?? 'false').trim().toLowerCase();
      return normalized === 'true' || normalized === '1' || normalized === 'yes' ? 'Yes' : 'No';
    }
    if (key === 'document_type' && value) {
      return value.replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    }
    return formatExtractedFieldValue(key, value);
  }

  async function handleApprove() {
    if (!item?.pending_approval_id || approvalLoadingAction !== null) return;
    approvalLoadingAction = 'approve';
    approvalMessage = '';
    error = '';
    try {
      const line_account_updates: { line_number: number; account_id: string }[] = [];
      for (const line of journalApproval?.lines ?? []) {
        const coaType = journalLineCoaType(line);
        if (!coaType) continue;
        const selected = journalLineAccountIds[line.line_number];
        const baseline =
          journalLineAccountDefaults[line.line_number] ?? String(line.account_id ?? '');
        if (selected && baseline && selected !== baseline) {
          line_account_updates.push({ line_number: line.line_number, account_id: selected });
        }
      }
      await approve(item.pending_approval_id, {
        note: approvalNote || 'Approved',
        ...(line_account_updates.length ? { line_account_updates } : {}),
      });
      approvalMessage = 'Approved — journal posted.';
      approvalNote = '';
      await load();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Approve failed';
    } finally {
      approvalLoadingAction = null;
    }
  }

  async function handleReject() {
    if (!item?.pending_approval_id || approvalLoadingAction !== null) return;
    const reason = approvalReason.trim();
    if (!reason) {
      error = 'Rejection reason is required.';
      return;
    }
    approvalLoadingAction = 'reject';
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
      approvalLoadingAction = null;
    }
  }

  async function handleEscalate() {
    if (!item?.pending_approval_id || approvalLoadingAction !== null) return;
    approvalLoadingAction = 'escalate';
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
      approvalLoadingAction = null;
    }
  }
</script>

<a href="/approvals">← Cases & Approvals</a>
<h1>Case detail</h1>

{#if error}<p class="error">{error}</p>{/if}
{#if item}
  <div
    class="card"
    class:overdue={item.is_overdue}
    class:exception={item.status_group === 'attention' ||
      item.status === 'exception' ||
      item.status === 'manual_review'}
  >
    {#if item.is_overdue}<p class="badge warn">Overdue — past SLA threshold</p>{/if}
    {#if item.error_reason}
      <p class="badge error">Error: {normalizeEscalationDisplayCopy(item.error_reason)}</p>
    {/if}
    <p>
      <strong><a href="/cases/{item.id}/submission">{item.case_number}</a></strong> · {item.type}
    </p>
    <p class="case-state" title="System status: {item.status}">
      <span class="status-group status-group-{item.status_group ?? 'processing'}">
        {item.status_group_label ?? item.status}
      </span>
      <span class="state-sep">·</span>
      <strong class="status-label">{caseStatusLabel(item)}</strong>
    </p>
    {#if item.status_reason && !item.error_reason}
      <p class="hint">{normalizeEscalationDisplayCopy(item.status_reason)}</p>
    {/if}
    {#if showActionRequiredPanel && manualActionConfig}
      <section class="action-required-box">
        <h2>Action required</h2>
        {#if reasonCode}
          <p class="reason-code"><strong>Reason:</strong> {reasonCode.replaceAll('_', ' ')}</p>
        {/if}
        <p class="action-context">{manualActionConfig.contextMessage}</p>
        {#if isParsingIncompleteEscalation && parsingIncompleteMissingFields.length > 0}
          <p class="missing-fields-heading"><strong>Missing fields:</strong></p>
          <ul class="missing-fields-list">
            {#each parsingIncompleteMissingFields as field}
              <li>{extractedFieldLabel(field)}</li>
            {/each}
          </ul>
        {/if}
        {#if showCounterpartyLink}
          <p class="hint">
            <a href="/counterparty-accounts">Open Counterparty Accounts</a>
          </p>
        {/if}
        {#if !isParsingIncompleteEscalation && (manualActionConfig.primary?.action === 'retry' || manualActionConfig.retry || manualActionConfig.primary || manualActionConfig.secondary)}
          {#if manualActionConfig.commentRequiredForPrimary || manualActionConfig.commentRequiredForReject}
            <label class="escalation-comment">
              {manualActionConfig.commentRequiredForPrimary && reasonCode === 'AP_CURRENCY_CONVERSION_REQUIRED'
                ? 'Exchange rate or override reason'
                : 'Comment'}
              <textarea
                bind:value={escalationComment}
                rows="3"
                placeholder={manualActionConfig.commentRequiredForPrimary
                  ? 'Required for primary action'
                  : 'Required for reject'}
              ></textarea>
            </label>
          {:else}
            <label class="escalation-comment">
              Comment (optional)
              <textarea
                bind:value={escalationComment}
                rows="2"
                placeholder="Optional note for the audit log"
              ></textarea>
            </label>
          {/if}
        {/if}
        <div class="manual-action-buttons">
          {#if manualActionConfig.primary}
            {@const primaryAction = manualActionConfig.primary.action}
            <button
              type="button"
              class={manualActionButtonClass(primaryAction, manualActionConfig)}
              disabled={manualLoadingAction !== null || retrying}
              aria-busy={manualLoadingAction === primaryAction ||
                (primaryAction === 'retry' && retrying)}
              onfocus={() => focusManualComment(primaryAction)}
              onclick={() =>
                runManualAction(manualActionConfig.primary!.action, manualActionConfig.primary!.label)}
            >
              {manualLoadingAction === primaryAction || (primaryAction === 'retry' && retrying)
                ? 'Working…'
                : manualActionConfig.primary.label}
            </button>
          {/if}
          {#if manualActionConfig.retry}
            <button
              type="button"
              class={manualActionButtonClass('retry', manualActionConfig)}
              disabled={manualLoadingAction !== null || retrying}
              aria-busy={manualLoadingAction === 'retry'}
              onfocus={() => focusManualComment('retry')}
              onclick={() => runManualAction('retry', manualActionConfig.retry!.label)}
            >
              {manualLoadingAction === 'retry' ? 'Working…' : manualActionConfig.retry.label}
            </button>
          {/if}
          {#if manualActionConfig.secondary}
            {@const secondaryAction = manualActionConfig.secondary.action}
            <button
              type="button"
              class={manualActionButtonClass(secondaryAction, manualActionConfig)}
              disabled={manualLoadingAction !== null || retrying}
              aria-busy={manualLoadingAction === secondaryAction}
              onfocus={() => focusManualComment(secondaryAction)}
              onclick={() =>
                runManualAction(
                  manualActionConfig.secondary!.action,
                  manualActionConfig.secondary!.label
                )}
            >
              {manualLoadingAction === secondaryAction
                ? 'Working…'
                : manualActionConfig.secondary.label}
            </button>
          {/if}
          {#if manualActionConfig.tertiary}
            {@const tertiaryAction = manualActionConfig.tertiary.action}
            <button
              type="button"
              class={manualActionButtonClass(tertiaryAction, manualActionConfig)}
              disabled={manualLoadingAction !== null || retrying}
              aria-busy={manualLoadingAction === tertiaryAction}
              onfocus={() => focusManualComment(tertiaryAction)}
              onclick={() =>
                runManualAction(
                  manualActionConfig.tertiary!.action,
                  manualActionConfig.tertiary!.label
                )}
            >
              {manualLoadingAction === tertiaryAction
                ? 'Working…'
                : manualActionConfig.tertiary.label}
            </button>
          {/if}
        </div>
        {#if isParsingIncompleteEscalation}
          <label class="escalation-comment">
            {parsingIncompleteCommentLabel(manualCommentFocusAction)}
            <textarea
              bind:value={escalationComment}
              rows="3"
              placeholder={manualCommentFocusAction === 'reject'
                ? 'Required to reject this claim'
                : 'Optional message to the submitter'}
              onfocus={() => {
                if (manualCommentFocusAction == null) {
                  manualCommentFocusAction = 'request_info';
                }
              }}
            ></textarea>
          </label>
        {/if}
        {#if !shouldRetryViaEscalationRespond(item) && manualActionConfig.primary?.action !== 'retry' && !manualActionConfig.retry}
          <p class="hint">
            Email escalation is not pending — fix setup in Finance, then use Retry processing below.
          </p>
        {/if}
        {#if manualActionMessage}
          <p class="hint success">{manualActionMessage}</p>
        {/if}
      </section>
    {/if}
    {#if item.status === 'manual_review' || item.status === 'on_hold'}
      {@const review = manualReviewDetails(item)}
      {@const reviewExtractedRows = orderedExtractedDisplayEntries(review.extracted, item.type)}
      {#if review.missing.length > 0 || review.confidence != null || reviewExtractedRows.length > 0}
        <section class="review-box">
          <h2>Manual review details</h2>
          {#if review.confidence != null}
            <p><strong>Extraction confidence:</strong> {formatConfidence(review.confidence)}</p>
          {/if}
          {#if review.missing.length > 0 && !isParsingIncompleteEscalation}
            <p><strong>Missing fields:</strong></p>
            <ul>
              {#each review.missing as field}
                <li>{extractedFieldLabel(field)}</li>
              {/each}
            </ul>
          {/if}
          {#if reviewExtractedRows.length > 0}
            <p><strong>Extracted:</strong></p>
            {#key coaLabelResolutionKey}
              <dl class="extracted">
                {#each reviewExtractedRows as row (row.key)}
                  <dt>{extractedFieldLabel(row.key)}</dt>
                  <dd>{formatExtractedReviewValue(row.key, row.value)}</dd>
                {/each}
              </dl>
            {/key}
          {/if}
        </section>
      {/if}
      {#if showTeachPanel}
        <section class="teach-box teach-box-secondary">
          <h2>Vendor extraction hints</h2>
          <p class="hint teach-box-lead">
            Help the agent find these fields on future documents from this vendor. This is not
            the primary way to resolve a stuck case — use the parsing confirmation form when the
            case is awaiting confirmation.
          </p>
          <button
            type="button"
            class="teach-toggle"
            onclick={() => (teachPanelExpanded = !teachPanelExpanded)}
          >
            {teachPanelExpanded ? 'Hide hints' : 'Show hints for future documents'}
          </button>
          {#if teachPanelExpanded}
            <p class="hint">
              Vendor: <strong>{vendorName}</strong>. Map how each missing field appears on this
              vendor&apos;s documents.
            </p>
            {#each teachFields as row}
              <div class="teach-field">
                <h3>{row.field_name.replaceAll('_', ' ')}</h3>
                <label>
                  {vendorHintFieldLabelInputLabel(row.field_name)}
                  <input
                    type="text"
                    bind:value={row.field_label}
                    placeholder="e.g. Date and time"
                  />
                </label>
                <label>
                  {vendorHintExampleValueInputLabel(row.field_name)}
                  <input
                    type="text"
                    bind:value={row.example_value}
                    placeholder="e.g. 24 Apr 2025 07:42 PM"
                  />
                </label>
                {#if DATE_FIELD_NAMES.has(row.field_name)}
                  <label>
                    {vendorHintDateFormatInputLabel(row.field_name)}
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
            {:else if canRetryTransientHermes}
              <button type="button" class="retry" disabled={retrying} onclick={handleRetry}>
                {retrying ? 'Requeuing…' : 'Retry processing'}
              </button>
              <p class="hint">
                Hermes timed out or was temporarily unavailable. Retry requeues this case after
                Ollama is healthy.
              </p>
            {/if}
          {/if}
        </section>
      {/if}
    {/if}
    {#if item.status === 'pending_confirmation'}
      {@const parsingExtracted =
        item.workflow_metadata?.extracted_fields &&
        typeof item.workflow_metadata.extracted_fields === 'object' &&
        !Array.isArray(item.workflow_metadata.extracted_fields)
          ? (item.workflow_metadata.extracted_fields as Record<string, string | null>)
          : {}}
      {@const parsingExtractedRows = orderedExtractedDisplayEntries(parsingExtracted, item.type)}
      <section class="confirm-box">
        <h2>Confirm Parsing</h2>
        {#if parsingExtractedRows.length > 0}
          {#key coaLabelResolutionKey}
            <dl class="extracted">
              {#each parsingExtractedRows as row (row.key)}
                <dt>{extractedFieldLabel(row.key)}</dt>
                <dd>{formatExtractedReviewValue(row.key, row.value)}</dd>
              {/each}
            </dl>
          {/key}
        {/if}
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
            <label>
              Document type
              <select bind:value={parsingForm.document_type}>
                <option value="receipt">Receipt</option>
                <option value="invoice">Invoice</option>
                <option value="credit_card_statement">Credit card statement</option>
              </select>
            </label>
            <label>
              Document number (optional)
              <input type="text" bind:value={parsingForm.document_number} />
            </label>
            <label>
              Document date
              <input type="date" bind:value={parsingForm.document_date} />
            </label>
            <label>
              Vendor name
              <input type="text" bind:value={parsingForm.vendor_name} />
            </label>
            <label>
              Expense GL account
              <select bind:value={parsingForm.gl_account_id} disabled={expenseCoaLoading}>
                <option value="">
                  {expenseCoaLoading ? 'Loading accounts…' : 'Select account…'}
                </option>
                {#each expenseCoaAccounts as acct (acct.id)}
                  <option value={String(acct.id)}>{acct.account_code} — {acct.account_name}</option>
                {/each}
              </select>
            </label>
            <label>
              Business purpose
              <textarea rows="2" bind:value={parsingForm.business_purpose}></textarea>
            </label>
          {/if}
          {#if !isExpenseConfirm}
            <label>
              Vendor name
              <input type="text" bind:value={parsingForm.vendor_name} />
            </label>
          {/if}
          <label>
            {isExpenseConfirm ? 'Total amount (tax inclusive)' : 'Total amount'}
            <input type="number" step="0.01" bind:value={parsingForm.total_amount} />
          </label>
          {#if isExpenseConfirm}
            <label>
              Tax amount
              <input type="number" step="0.01" bind:value={parsingForm.tax_amount} />
            </label>
            <div class="derived-field">
              <span class="derived-label">Amount ex-tax</span>
              <output class="derived-value">{parsingAmountExTax || '—'}</output>
            </div>
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
            {#if parsingForm.currency !== 'SGD'}
              <label>
                Exchange rate (1 {parsingForm.currency} = ? SGD)
                <input
                  type="number"
                  step="0.000001"
                  min="0"
                  required
                  bind:value={parsingForm.exchange_rate}
                />
              </label>
            {/if}
            <label class="toggle-row">
              <input type="checkbox" bind:checked={parsingForm.sender_validated} />
              Document validated
            </label>
          {/if}
          {#if !isExpenseConfirm}
            <label>
              Tax amount
              <input type="number" step="0.01" bind:value={parsingForm.tax_amount} />
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
            {#if parsingForm.currency !== 'SGD'}
              <label>
                Exchange rate (1 {parsingForm.currency} = ? SGD)
                <input
                  type="number"
                  step="0.000001"
                  min="0"
                  required
                  bind:value={parsingForm.exchange_rate}
                />
              </label>
            {/if}
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
              Document validated
            </label>
          {/if}
          <div class="confirm-actions">
            <button
              type="button"
              class="approve"
              disabled={parsingLoadingAction !== null}
              aria-busy={parsingLoadingAction === 'confirm'}
              onclick={handleConfirmParsing}
            >
              {parsingLoadingAction === 'confirm' ? 'Working…' : 'Confirm & Continue'}
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
              disabled={parsingLoadingAction !== null}
              aria-busy={parsingLoadingAction === 'reject'}
              onclick={handleRejectParsing}
            >
              {parsingLoadingAction === 'reject' ? 'Working…' : 'Reject'}
            </button>
          </div>
        {:else if parsingConfirmReadOnly}
          <p class="hint">
            Extracted fields are read-only. You need {isExpenseConfirm ? 'expenses:write' : 'cases:write'}
            permission to confirm or reject.
          </p>
        {:else}
          <p class="hint">Awaiting confirmation by Accounts or Finance leadership.</p>
        {/if}
        {#if parsingMessage}
          <p class="hint success">{parsingMessage}</p>
        {/if}
      </section>
    {/if}
    <p>{item.subject}</p>
    <p>Submitted by: {submittedByDisplay(item)}</p>
    <p>
      Processing time: {item.processing_time_minutes != null
        ? `${formatCount(item.processing_time_minutes)} min`
        : '—'}
    </p>
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
    {#if showStandardRetry}
      <button type="button" class="retry" disabled={retrying} onclick={handleRetry}>
        {retrying ? 'Requeuing…' : 'Retry processing'}
      </button>
      {#if canRetryAfterReopen}
        <p class="hint">The GL period for this posting date has been reopened — you can reprocess without an override.</p>
      {:else if canRetryTransientHermes}
        <p class="hint">
          Hermes timed out or was temporarily unavailable. Retry requeues this case; ensure Hermes and Ollama are healthy on the server.
        </p>
      {/if}
    {/if}
    {#if retryMessage}
      <p class="hint success">{retryMessage}</p>
    {/if}
    {#if approvalMessage}
      <p class="hint success">{approvalMessage}</p>
    {/if}
    {#if awaitingJournalApproval}
      <section class="approval-box">
        <h2>Journal entry approval</h2>
        {#if bindingEscalated}
          <p class="hint">Escalated to CFO for final approval.</p>
        {/if}
        {#if journalApproval}
          <dl class="extracted journal-approval-fields">
            {#if journalApproval.vendor}
              <dt>Vendor</dt>
              <dd>{journalApproval.vendor}</dd>
            {/if}
            {#if journalApproval.document_number}
              <dt>Document number</dt>
              <dd>{journalApproval.document_number}</dd>
            {/if}
            {#if journalApproval.document_date}
              <dt>Document date</dt>
              <dd>{journalApproval.document_date}</dd>
            {/if}
            {#if journalApproval.document_type}
              <dt>Document type</dt>
              <dd>{journalApproval.document_type}</dd>
            {/if}
            {#if journalHeaderExGst}
              <dt>Amount (ex-GST)</dt>
              <dd>{journalHeaderExGst}</dd>
            {/if}
            {#if journalHeaderGst}
              <dt>GST</dt>
              <dd>{journalHeaderGst}</dd>
            {/if}
            {#if journalHeaderTotal}
              <dt>Total (inclusive)</dt>
              <dd>{journalHeaderTotal}</dd>
            {/if}
            {#if journalApproval.approval_tier_label}
              <dt>Approval tier</dt>
              <dd>{journalApproval.approval_tier_label}</dd>
            {:else if bindingTier != null}
              <dt>Approval tier</dt>
              <dd>Tier {bindingTier}</dd>
            {/if}
          </dl>
          {#if journalApproval.lines && journalApproval.lines.length > 0}
            <table class="journal-lines-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Account</th>
                  <th>Debit</th>
                  <th>Credit</th>
                </tr>
              </thead>
              <tbody>
                {#each journalApproval.lines as line (line.line_number)}
                  {@const coaType = journalLineCoaType(line)}
                  {@const lineAccountId = coaType
                    ? (journalLineAccountIds[line.line_number] ??
                      resolveJournalLineAccountId(
                        line,
                        coaType,
                        expenseCoaAccounts,
                        liabilityCoaAccounts,
                        journalApproval,
                      ))
                    : ''}
                  <tr>
                    <td>{line.line_number}</td>
                    <td>
                      {#if coaType && lineAccountId}
                        <select
                          class="journal-line-account-select"
                          value={lineAccountId}
                          disabled={journalCoaLoading}
                          onchange={(e) =>
                            setJournalLineAccountId(line.line_number, e.currentTarget.value)}
                        >
                          {#each journalLineCoaOptionsForLine(
                            line,
                            coaType,
                            expenseCoaAccounts,
                            liabilityCoaAccounts,
                            journalApproval,
                          ) as acct (acct.id)}
                            <option value={String(acct.id)}
                              >{acct.account_code} — {acct.account_name}</option
                            >
                          {/each}
                        </select>
                      {:else if isGstJournalLine(line) && line.account_code}
                        {line.account_code} — {line.account_name ?? ''}
                        <span class="hint-inline">(GST — not editable)</span>
                      {:else if line.account_code}
                        {line.account_code} — {line.account_name ?? ''}
                      {:else}
                        {line.account_name ?? line.account_id ?? '—'}
                      {/if}
                    </td>
                    <td>{formatAmount(line.debit)}</td>
                    <td>{formatAmount(line.credit)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}
        {:else if bindingTier != null}
          <p>Tier {bindingTier}</p>
        {/if}
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
            <button
              type="button"
              class="approve"
              disabled={approvalLoadingAction !== null}
              aria-busy={approvalLoadingAction === 'approve'}
              onclick={handleApprove}
            >
              {approvalLoadingAction === 'approve' ? 'Working…' : 'Approve'}
            </button>
            <button
              type="button"
              class="reject"
              disabled={approvalLoadingAction !== null}
              aria-busy={approvalLoadingAction === 'reject'}
              onclick={handleReject}
            >
              {approvalLoadingAction === 'reject' ? 'Working…' : 'Reject'}
            </button>
            {#if showAccApprovalActions}
              <button
                type="button"
                class="escalate"
                disabled={approvalLoadingAction !== null}
                aria-busy={approvalLoadingAction === 'escalate'}
                onclick={handleEscalate}
              >
                {approvalLoadingAction === 'escalate' ? 'Working…' : 'Escalate to CFO'}
              </button>
            {/if}
          </div>
        {:else if item.pending_approval_id}
          <p class="hint">This case is awaiting approval by another role.</p>
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
  .case-state {
    margin: 0.35rem 0;
  }
  .status-group {
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-size: 0.85rem;
    font-weight: 600;
    text-transform: none;
  }
  .status-group-processing {
    background: #e0f2fe;
    color: #0369a1;
  }
  .status-group-approval {
    background: #fef9c3;
    color: #854d0e;
  }
  .status-group-completed {
    background: #dcfce7;
    color: #166534;
  }
  .status-group-attention {
    background: #ffedd5;
    color: #9a3412;
  }
  .status-group-rejected {
    background: #fee2e2;
    color: #991b1b;
  }
  .state-sep {
    margin: 0 0.35rem;
    color: #94a3b8;
  }
  .status-label {
    font-weight: 600;
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
  .action-required-box {
    margin-top: 1rem;
    padding: 1rem;
    border: 2px solid #f97316;
    border-radius: 8px;
    background: #fff7ed;
  }
  .action-required-box h2 {
    margin: 0 0 0.5rem;
    font-size: 1.05rem;
    color: #9a3412;
  }
  .reason-code {
    font-size: 0.85rem;
    color: #7c2d12;
    margin: 0 0 0.5rem;
  }
  .action-context {
    margin: 0 0 0.75rem;
    line-height: 1.45;
  }
  .escalation-comment {
    display: block;
    margin-bottom: 0.75rem;
    font-size: 0.9rem;
  }
  .escalation-comment textarea {
    display: block;
    width: 100%;
    max-width: 480px;
    margin-top: 0.35rem;
    box-sizing: border-box;
  }
  .manual-action-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  .manual-action-buttons .secondary {
    padding: 0.5rem 1rem;
    border: 1px solid #64748b;
    border-radius: 6px;
    background: #f8fafc;
    color: #334155;
    font-weight: 600;
    cursor: pointer;
  }
  .manual-action-buttons .secondary:disabled {
    opacity: 0.6;
    cursor: not-allowed;
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
  .teach-box-secondary {
    margin-top: 1.5rem;
    border-color: #94a3b8;
    background: #f1f5f9;
  }
  .teach-box-lead {
    margin: 0.5rem 0 0.75rem;
    max-width: 42rem;
  }
  .teach-toggle {
    margin-bottom: 0.75rem;
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
  .journal-line-account-select {
    display: block;
    width: 100%;
    max-width: 22rem;
    padding: 0.35rem 0.5rem;
    box-sizing: border-box;
    font-size: 0.875rem;
  }

  .hint-inline {
    display: block;
    font-size: 0.75rem;
    color: #64748b;
    margin-top: 0.15rem;
  }

  .derived-field {
    margin: 0.25rem 0 0.75rem;
  }
  .derived-label {
    display: block;
    font-size: 0.875rem;
    color: #64748b;
    margin-bottom: 0.25rem;
  }
  .derived-value {
    display: block;
    padding: 0.35rem 0.5rem;
    background: #f8fafc;
    border-radius: 4px;
    font-variant-numeric: tabular-nums;
  }

  .journal-lines-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
    margin-top: 0.75rem;
  }

  .journal-lines-table th,
  .journal-lines-table td {
    text-align: left;
    padding: 0.45rem 0.5rem;
    border-bottom: 1px solid #e2e8f0;
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
