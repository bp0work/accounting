import { hasPendingEscalation } from '$lib/ap-escalation-actions';
import type { CaseItem } from '$lib/api/cases';

/** Human-readable labels for `case.type` values from the API. */
const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  ap_invoice: 'AP Invoice',
  ap_po_validation: 'PO Validation',
  ap_payment_proposal: 'Payment Proposal',
  ar_invoice: 'AR Invoice',
  ar_payment_advice: 'Payment Advice',
  ar_credit_note: 'AR Credit Note',
  ar_soa_request: 'SOA Request',
  expense_claim: 'Expense Claim',
  general_inquiry: 'General Inquiry',
  treasury_reconciliation: 'Treasury Reconciliation',
  treasury_fx: 'FX Transaction',
  treasury_suspense: 'Suspense Item',
};

const AP_CASE_TYPES = new Set(['ap_invoice', 'ap_po_validation', 'ap_payment_proposal']);

const AR_CASE_TYPES = new Set([
  'ar_invoice',
  'ar_payment_advice',
  'ar_statement',
  'ar_credit_note',
  'ar_soa_request',
]);

export function documentTypeLabel(caseType: string): string {
  return DOCUMENT_TYPE_LABELS[caseType] ?? caseType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Status column / case header — overrides API `status_label` for key workflow states. */
export function caseStatusLabel(
  item: Pick<CaseItem, 'status' | 'status_label' | 'workflow_metadata'>
): string {
  if (item.status === 'on_hold' && hasPendingEscalation(item)) {
    return 'On hold — action required';
  }
  if (item.status === 'pending_confirmation') {
    return 'Awaiting parsing confirmation';
  }
  if (item.status === 'manual_review') {
    return 'Manual review';
  }
  const fromApi = item.status_label?.trim();
  if (fromApi) return fromApi;
  return item.status.replace(/_/g, ' ');
}

/** Dashboard / list “State” column — prefer workflow status label when defined. */
export function caseStateColumnLabel(
  item: Pick<CaseItem, 'status' | 'status_label' | 'status_group_label' | 'workflow_metadata'>
): string {
  if (
    item.status === 'pending_confirmation' ||
    item.status === 'manual_review' ||
    (item.status === 'on_hold' && hasPendingEscalation(item))
  ) {
    return caseStatusLabel(item);
  }
  return item.status_group_label?.trim() || caseStatusLabel(item);
}

/** Client / Vendor column — AP shows extracted vendor; AR shows classified customer. */
/** Worker/agent label for dashboard "Action by" when state is Processing. */
export function processingAgentLabel(caseType: string): string {
  if (caseType.startsWith('treasury_')) return 'Treasury Agent';
  if (
    caseType === 'ap_invoice' ||
    caseType === 'ap_credit_note' ||
    caseType === 'ap_debit_note' ||
    caseType === 'ap_po_validation' ||
    caseType === 'ap_payment_proposal'
  ) {
    return 'AP Agent';
  }
  if (
    caseType === 'ar_invoice' ||
    caseType === 'ar_payment_advice' ||
    caseType === 'ar_credit_note'
  ) {
    return 'AR Agent';
  }
  if (caseType === 'expense_claim') return 'Expense Agent';
  if (caseType === 'general_inquiry') return 'Accounts Agent';
  return 'AI Agent';
}

const MS_24H = 24 * 60 * 60 * 1000;

/** Exclude from Recent Cases when shown under Overdue (SLA or stuck processing). */
export function isExcludedFromRecentCases(
  item: {
    id: string;
    is_overdue: boolean;
    status_group?: string | null;
    status_group_label?: string | null;
    last_activity_at?: string | null;
    created_at: string;
  },
  overdueCaseIds: ReadonlySet<string>,
): boolean {
  if (item.is_overdue || overdueCaseIds.has(item.id)) return true;
  const processing =
    item.status_group === 'processing' || item.status_group_label === 'Processing';
  if (!processing) return false;
  const ts = item.last_activity_at || item.created_at;
  if (!ts) return false;
  return Date.now() - new Date(ts).getTime() > MS_24H;
}

const EXTRACTED_FIELD_LABELS: Record<string, string> = {
  vendor_name: 'Vendor name',
  document_type: 'Document type',
  document_number: 'Document number',
  document_date: 'Document date',
  currency: 'Currency',
  tax_amount: 'Tax amount',
  total_amount: 'Total amount',
  sgd_amount: 'SGD amount',
  exchange_rate: 'Exchange rate',
  business_purpose: 'Business purpose',
  gl_account_id: 'GL account',
  sender_validated: 'Document validated',
  // Legacy metadata keys
  invoice_date: 'Document date',
  invoice_number: 'Document number',
  merchant_name: 'Vendor name',
  gst_amount: 'Tax amount',
};

/** Display order for parsing confirmation and manual review extracted fields. */
export const EXTRACTED_FIELD_DISPLAY_ORDER = [
  'vendor_name',
  'document_type',
  'document_number',
  'document_date',
  'currency',
  'tax_amount',
  'total_amount',
  'sgd_amount',
  'exchange_rate',
  'business_purpose',
  'gl_account_id',
  'sender_validated',
] as const;

/** Inbound submitter — API `submitted_by` (email from_name or from_address). */
/** Display label for extracted / review field keys from workflow metadata. */
export function extractedFieldLabel(fieldKey: string): string {
  return EXTRACTED_FIELD_LABELS[fieldKey] ?? toSentenceCaseFieldLabel(fieldKey);
}

function toSentenceCaseFieldLabel(fieldKey: string): string {
  const words = fieldKey.replaceAll('_', ' ').trim();
  if (!words) return fieldKey;
  return words.charAt(0).toUpperCase() + words.slice(1).toLowerCase();
}

export function submittedByDisplay(item: {
  submitted_by?: string | null;
  from_address?: string | null;
}): string {
  const label = item.submitted_by?.trim() || item.from_address?.trim();
  return label || '—';
}

/** Submission detail — counterparty name plus inbound email address. */
export function submissionSubmittedByDisplay(item: {
  counterparty_name?: string | null;
  from_address?: string | null;
}): string {
  const name = item.counterparty_name?.trim();
  const email = item.from_address?.trim();
  if (name && email) return `${name} (${email})`;
  if (name) return name;
  if (email) return email;
  return '—';
}

export function clientVendorColumnValue(item: {
  type: string;
  client_vendor_name?: string | null;
  counterparty_name?: string | null;
}): string {
  if (AP_CASE_TYPES.has(item.type)) {
    return item.client_vendor_name || item.counterparty_name || '—';
  }
  if (AR_CASE_TYPES.has(item.type)) {
    return item.counterparty_name || '—';
  }
  return item.client_vendor_name || item.counterparty_name || '—';
}
