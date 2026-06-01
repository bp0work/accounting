/** Dual-currency labels for foreign expense/AP submissions (SGD journal amounts). */

import { formatAmount, formatCurrencyAmount, formatRate } from '$lib/format';

export function normalizedCurrency(currency: string | null | undefined): string {
  const c = (currency ?? '').trim().toUpperCase();
  return c || 'SGD';
}

export function isForeignCurrency(currency: string | null | undefined): boolean {
  return normalizedCurrency(currency) !== 'SGD';
}

function parseMoney(value: string | null | undefined): number | null {
  if (value == null || value === '') return null;
  const n = parseFloat(String(value).replace(/,/g, ''));
  return Number.isNaN(n) ? null : n;
}

/** Prefer persisted SGD; otherwise foreign × exchange_rate (2 dp). */
export function resolveSgdAmountString(
  foreignAmount: string | null | undefined,
  sgdOverride: string | null | undefined,
  exchangeRate: string | null | undefined,
): string | null {
  const persisted = parseMoney(sgdOverride);
  if (persisted != null) return formatAmount(persisted);
  const foreign = parseMoney(foreignAmount);
  const rate = parseMoney(exchangeRate);
  if (foreign != null && rate != null) return formatAmount(foreign * rate);
  return null;
}

/** e.g. `USD 1.80 (SGD 2.45)` when currency is foreign; otherwise `SGD 1.80`. */
export function formatForeignAmountWithSgd(
  currency: string | null | undefined,
  foreignAmount: string | null | undefined,
  sgdOverride: string | null | undefined,
  exchangeRate: string | null | undefined,
): string {
  const cur = normalizedCurrency(currency);
  if (!isForeignCurrency(cur)) {
    return formatCurrencyAmount('SGD', foreignAmount);
  }
  const foreign = formatCurrencyAmount(cur, foreignAmount);
  const sgd = resolveSgdAmountString(foreignAmount, sgdOverride, exchangeRate);
  if (sgd == null || sgd === '—') return foreign;
  return `${foreign} (SGD ${sgd})`;
}

/** e.g. `1 USD = 1.3600 SGD` — null when SGD or rate missing. */
export function formatExchangeRateLabel(
  currency: string | null | undefined,
  exchangeRate: string | null | undefined,
): string | null {
  const cur = normalizedCurrency(currency);
  if (!isForeignCurrency(cur)) return null;
  const rate = formatRate(exchangeRate);
  if (rate === '—') return null;
  return `1 ${cur} = ${rate} SGD`;
}

export type JournalFxExtracted = {
  currency: string;
  exchangeRateLabel: string | null;
  exGstForeign: string | null;
  gstForeign: string | null;
  totalForeign: string | null;
};

export function journalFxFromExtracted(
  extracted: Record<string, string | null>,
): JournalFxExtracted | null {
  const currency = normalizedCurrency(extracted.currency);
  if (!isForeignCurrency(currency)) return null;

  const totalRaw = extracted.total_amount ?? extracted.amount ?? null;
  const taxRaw = extracted.tax_amount ?? extracted.gst_amount ?? null;
  const total = parseMoney(totalRaw);
  const tax = parseMoney(taxRaw) ?? 0;

  let exGstForeign: string | null = null;
  if (total != null) {
    exGstForeign = formatAmount(total - tax);
  }

  return {
    currency,
    exchangeRateLabel: formatExchangeRateLabel(currency, extracted.exchange_rate),
    exGstForeign,
    gstForeign: taxRaw && parseMoney(taxRaw) != null ? formatAmount(taxRaw) : null,
    totalForeign: totalRaw ? formatAmount(totalRaw) : null,
  };
}

/** Parenthetical foreign amount for journal header, e.g. `USD 21.80`. */
export function formatJournalHeaderForeignLine(
  fx: JournalFxExtracted | null,
  kind: 'exGst' | 'gst' | 'total',
): string | null {
  if (!fx) return null;
  const amount =
    kind === 'exGst' ? fx.exGstForeign : kind === 'gst' ? fx.gstForeign : fx.totalForeign;
  if (amount == null || amount === '—') return null;
  return formatCurrencyAmount(fx.currency, amount);
}
