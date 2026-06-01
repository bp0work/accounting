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
