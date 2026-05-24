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

export function documentTypeLabel(caseType: string): string {
  return DOCUMENT_TYPE_LABELS[caseType] ?? caseType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
