/** Manual review / on_hold action panel — mirrors AP escalation email labels and actions. */

import type { CaseItem } from './api/cases';

export type EscalationUiAction = 'approve' | 'reject' | 'request_info' | 'retry';

export type EscalationActionConfig = {
  primary: { label: string; action: EscalationUiAction } | null;
  secondary: { label: string; action: EscalationUiAction } | null;
  commentRequiredForPrimary: boolean;
  commentRequiredForReject: boolean;
  contextMessage: string;
};

const MANUAL_REVIEW_ROLES = new Set(['accounts_clerk', 'finance_manager', 'cfo']);

export function canUseManualReviewActions(roleName: string | undefined | null): boolean {
  return MANUAL_REVIEW_ROLES.has((roleName ?? '').toLowerCase());
}

export function caseReasonCode(caseItem: CaseItem): string {
  const meta = caseItem.workflow_metadata ?? {};
  for (const key of ['reason_code', 'error_type', 'error_code'] as const) {
    const code = String(meta[key] ?? '').trim().toUpperCase();
    if (code) return code;
  }
  const err = String(caseItem.error_reason ?? '').toUpperCase();
  if (err.includes('HERMES_TIMEOUT')) return 'HERMES_TIMEOUT';
  if (err.includes('HERMES_UNAVAILABLE')) return 'HERMES_UNAVAILABLE';
  return '';
}

export function hasPendingEscalation(caseItem: CaseItem): boolean {
  const meta = caseItem.workflow_metadata ?? {};
  return Boolean(meta.escalation_pending && meta.escalation_id);
}

function vendorLabel(caseItem: CaseItem): string {
  const meta = caseItem.workflow_metadata ?? {};
  const extracted = meta.extracted_fields;
  if (extracted && typeof extracted === 'object' && !Array.isArray(extracted)) {
    const vendor = (extracted as Record<string, unknown>).vendor_name;
    if (vendor != null && String(vendor).trim()) return String(vendor).trim();
  }
  return (caseItem.counterparty_name ?? caseItem.client_vendor_name ?? 'this vendor').trim();
}

function contextForCode(code: string, caseItem: CaseItem): string {
  const vendor = vendorLabel(caseItem);
  const caseNum = caseItem.case_number;
  const summary = String(caseItem.status_reason ?? caseItem.error_reason ?? '').trim();

  switch (code) {
    case 'AP_CONTRACT_MISSING':
      return `Contract missing for ${vendor}. Please fix the contract details in Counterparty Accounts and click Resubmit.`;
    case 'AP_VENDOR_INACTIVE':
      return `Vendor ${vendor} is inactive. Reactivate the vendor in Counterparty Accounts, then click Reactivate & Resubmit.`;
    case 'AP_VENDOR_NOT_FOUND':
      return `Vendor ${vendor} is not set up. Register the vendor in Counterparty Accounts, then use Retry — or Reject to notify the sender.`;
    case 'AP_PAYMENT_TERMS_MISMATCH':
      return `Payment terms on the invoice do not match the contract for ${vendor}. Accept to continue with an override reason, or Reject.`;
    case 'AP_SENDER_NOT_VALIDATED':
      return `Sender validation is required for ${vendor}. Accept to continue after confirming the document, or Reject to ask for a resubmit.`;
    case 'AP_COA_NOT_FOUND':
      return `GL account could not be matched for ${vendor}. Confirm the correct account in Chart of Accounts setup, then continue.`;
    case 'AP_CURRENCY_CONVERSION_REQUIRED':
      return `Foreign currency on this invoice requires an exchange rate (e.g. 1 USD = 1.35 SGD). Enter the rate in the comment field and click Apply Rate & Continue.`;
    case 'AP_PARSING_INCOMPLETE':
      return (
        summary ||
        `Parsing is incomplete for case ${caseNum}. Provide missing details to reprocess, or ask the sender to resubmit.`
      );
    case 'AP_DUPLICATE_FOUND':
      return `A possible duplicate invoice was detected. Reject if this is a duplicate submission.`;
    case 'EXP_SUBMITTER_NOT_FOUND':
      return (
        'Submitter email is not registered as Staff in Counterparty Accounts. Add a Staff ' +
        'counterparty with matching contact email, then use Retry — or Reject to notify the submitter.'
      );
    case 'EXP_SUBMITTER_INACTIVE':
      return 'Staff submitter is inactive. Reactivate in Counterparty Accounts, then Resubmit — or Reject.';
    case 'EXP_POLICY_EXCEEDED':
      return `Expense exceeds T&E policy limits. Accept with an override reason in the comment field, or Reject.`;
    case 'EXP_RECEIPT_INVALID':
      return `Receipt is invalid or older than 90 days. Accept with override reason, or Reject and ask for a new receipt quoting Case ID ${caseNum}.`;
    case 'EXP_CURRENCY_CONVERSION_REQUIRED':
      return `Foreign currency receipt — enter exchange rate in the comment (e.g. 1 USD = 1.35 SGD) and click Apply Rate & Continue.`;
    case 'EXP_COA_NOT_FOUND':
      return 'Expense GL account could not be mapped. Confirm Chart of Accounts setup, then continue.';
    case 'EXP_PARSING_INCOMPLETE':
      return summary || `Expense parsing incomplete for case ${caseNum}. Provide details or reject.`;
    case 'EXP_DUPLICATE':
      return `Possible duplicate expense claim. Reject if this is a duplicate submission.`;
    case 'HERMES_TIMEOUT':
    case 'HERMES_UNAVAILABLE':
      return `Document extraction timed out or Hermes was unavailable. Retry requeues processing when Ollama is healthy.`;
    default:
      return summary || `Action required for case ${caseNum}.`;
  }
}

export function escalationActionConfig(
  reasonCode: string,
  caseItem: CaseItem
): EscalationActionConfig {
  const contextMessage = contextForCode(reasonCode, caseItem);

  switch (reasonCode) {
    case 'AP_CONTRACT_MISSING':
    case 'AP_VENDOR_INACTIVE':
      return {
        primary: { label: 'Resubmit', action: 'approve' },
        secondary: { label: 'Reject', action: 'reject' },
        commentRequiredForPrimary: false,
        commentRequiredForReject: true,
        contextMessage,
      };
    case 'AP_PAYMENT_TERMS_MISMATCH':
    case 'AP_SENDER_NOT_VALIDATED':
      return {
        primary: { label: 'Accept & Continue', action: 'approve' },
        secondary: { label: 'Reject', action: 'reject' },
        commentRequiredForPrimary: true,
        commentRequiredForReject: true,
        contextMessage,
      };
    case 'AP_COA_NOT_FOUND':
      return {
        primary: { label: 'Confirm Account & Continue', action: 'approve' },
        secondary: { label: 'Reject', action: 'reject' },
        commentRequiredForPrimary: false,
        commentRequiredForReject: true,
        contextMessage,
      };
    case 'AP_CURRENCY_CONVERSION_REQUIRED':
      return {
        primary: { label: 'Apply Rate & Continue', action: 'approve' },
        secondary: { label: 'Reject', action: 'reject' },
        commentRequiredForPrimary: true,
        commentRequiredForReject: true,
        contextMessage,
      };
    case 'AP_VENDOR_NOT_FOUND':
    case 'AP_DUPLICATE_FOUND':
      return {
        primary: null,
        secondary: { label: 'Reject', action: 'reject' },
        commentRequiredForPrimary: false,
        commentRequiredForReject: true,
        contextMessage,
      };
    case 'AP_PARSING_INCOMPLETE':
      return {
        primary: { label: 'Provide Details', action: 'request_info' },
        secondary: { label: 'Ask sender to resubmit', action: 'reject' },
        commentRequiredForPrimary: true,
        commentRequiredForReject: true,
        contextMessage,
      };
    case 'EXP_SUBMITTER_INACTIVE':
      return {
        primary: { label: 'Resubmit', action: 'approve' },
        secondary: { label: 'Reject', action: 'reject' },
        commentRequiredForPrimary: false,
        commentRequiredForReject: true,
        contextMessage,
      };
    case 'EXP_POLICY_EXCEEDED':
    case 'EXP_RECEIPT_INVALID':
      return {
        primary: { label: 'Accept & Continue', action: 'approve' },
        secondary: { label: 'Reject', action: 'reject' },
        commentRequiredForPrimary: true,
        commentRequiredForReject: true,
        contextMessage,
      };
    case 'EXP_CURRENCY_CONVERSION_REQUIRED':
      return {
        primary: { label: 'Apply Rate & Continue', action: 'approve' },
        secondary: { label: 'Reject', action: 'reject' },
        commentRequiredForPrimary: true,
        commentRequiredForReject: true,
        contextMessage,
      };
    case 'EXP_COA_NOT_FOUND':
      return {
        primary: { label: 'Confirm Account & Continue', action: 'approve' },
        secondary: { label: 'Reject', action: 'reject' },
        commentRequiredForPrimary: false,
        commentRequiredForReject: true,
        contextMessage,
      };
    case 'EXP_SUBMITTER_NOT_FOUND':
    case 'EXP_DUPLICATE':
      return {
        primary: null,
        secondary: { label: 'Reject', action: 'reject' },
        commentRequiredForPrimary: false,
        commentRequiredForReject: true,
        contextMessage,
      };
    case 'EXP_PARSING_INCOMPLETE':
      return {
        primary: { label: 'Provide Details', action: 'request_info' },
        secondary: { label: 'Ask sender to resubmit', action: 'reject' },
        commentRequiredForPrimary: true,
        commentRequiredForReject: true,
        contextMessage,
      };
    case 'HERMES_TIMEOUT':
    case 'HERMES_UNAVAILABLE':
      return {
        primary: { label: 'Retry', action: 'retry' },
        secondary: null,
        commentRequiredForPrimary: false,
        commentRequiredForReject: false,
        contextMessage,
      };
    default:
      return {
        primary: { label: 'Approve', action: 'approve' },
        secondary: { label: 'Reject', action: 'reject' },
        commentRequiredForPrimary: false,
        commentRequiredForReject: true,
        contextMessage,
      };
  }
}

export function showManualReviewPanel(caseItem: CaseItem, roleName: string | undefined | null): boolean {
  if (!canUseManualReviewActions(roleName)) return false;
  if (caseItem.status !== 'manual_review' && caseItem.status !== 'on_hold') return false;
  const code = caseReasonCode(caseItem);
  if (code === 'HERMES_TIMEOUT' || code === 'HERMES_UNAVAILABLE') return true;
  if (hasPendingEscalation(caseItem)) return true;
  if (code.startsWith('AP_') || code.startsWith('EXP_')) return true;
  return Boolean(caseItem.error_reason || caseItem.status_reason);
}
