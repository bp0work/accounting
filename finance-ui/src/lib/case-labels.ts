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

/** Client / Vendor column — AP shows extracted vendor; AR shows classified customer. */
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
