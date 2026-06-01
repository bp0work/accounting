/** Shared display formatting for amounts, rates, and counts. */

export function formatAmount(v: number | string | null | undefined): string {
  if (v == null || v === '') return '—';
  const n = typeof v === 'string' ? parseFloat(String(v).replace(/,/g, '')) : v;
  if (Number.isNaN(n)) return '—';
  return n.toFixed(2);
}

export function formatRate(v: number | string | null | undefined): string {
  if (v == null || v === '') return '—';
  const n = typeof v === 'string' ? parseFloat(String(v).replace(/,/g, '')) : v;
  if (Number.isNaN(n)) return '—';
  return n.toFixed(4);
}

export function formatCount(v: number | string | null | undefined): string {
  if (v == null || v === '') return '—';
  const n = typeof v === 'string' ? parseFloat(String(v).replace(/,/g, '')) : v;
  if (Number.isNaN(n)) return '—';
  return String(Math.round(n));
}

export function formatCurrencyAmount(
  currency: string | null | undefined,
  value: number | string | null | undefined,
): string {
  const amt = formatAmount(value);
  if (amt === '—') return '—';
  const cur = (currency ?? '').trim() || 'SGD';
  return `${cur} ${amt}`;
}

export const EXTRACTED_AMOUNT_KEYS = new Set([
  'total_amount',
  'tax_amount',
  'gst_amount',
  'sgd_amount',
  'amount',
]);

export const EXTRACTED_RATE_KEYS = new Set(['exchange_rate']);

export function formatExtractedFieldValue(key: string, value: string | null): string {
  if (value == null || String(value).trim() === '') return '—';
  if (EXTRACTED_RATE_KEYS.has(key)) return formatRate(value);
  if (EXTRACTED_AMOUNT_KEYS.has(key)) return formatAmount(value);
  return value;
}

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  invoice: 'Invoice',
  receipt: 'Receipt',
  credit_card_statement: 'Credit Card Statement',
  credit_note: 'Credit note',
  debit_note: 'Debit note',
  expense_claim: 'Expense claim',
  ar_invoice: 'AR invoice',
  ap_invoice: 'AP invoice',
};

/** Title-case document type for submission detail (Receipt, Invoice, Credit Card Statement, …). */
export function documentTypeTitleCase(raw: string | null | undefined): string {
  if (raw == null || String(raw).trim() === '') return '—';
  const key = String(raw).trim().toLowerCase();
  if (DOCUMENT_TYPE_LABELS[key]) return DOCUMENT_TYPE_LABELS[key];
  return key.replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Format ISO or YYYY-MM-DD dates as DD/MM/YYYY. */
export function formatDateOnly(value: string | null | undefined): string {
  if (value == null || String(value).trim() === '') return '—';
  const s = String(value).trim();
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  if (dateOnly) {
    return `${dateOnly[3]}/${dateOnly[2]}/${dateOnly[1]}`;
  }
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return '—';
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  return `${day}/${month}/${year}`;
}

/** Trial balance debit/credit cells — null/zero → em dash. */
export function formatTrialBalanceAmount(value: string | null | undefined): string {
  if (value == null || value === '') return '—';
  return value;
}

export function isNonZeroAmount(value: string | number | null | undefined): boolean {
  if (value == null || value === '') return false;
  const n =
    typeof value === 'string' ? parseFloat(String(value).replace(/,/g, '')) : Number(value);
  return !Number.isNaN(n) && n !== 0;
}
