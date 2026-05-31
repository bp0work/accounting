/** Canonical counterparty types stored in the database. */
export const COUNTERPARTY_TYPES = [
  'customer',
  'supplier',
  'employee',
  'bank',
  'other',
] as const;

export type CounterpartyType = (typeof COUNTERPARTY_TYPES)[number];

const TYPE_LABELS: Record<CounterpartyType, string> = {
  customer: 'Customer',
  supplier: 'Supplier',
  employee: 'Employee',
  bank: 'Bank',
  other: 'Other',
};

/** Display label for a counterparty type (maps legacy vendor/staff to canonical labels). */
export function counterpartyTypeLabel(value: unknown): string {
  const t = String(value ?? '').toLowerCase();
  if (t === 'vendor') return TYPE_LABELS.supplier;
  if (t === 'staff') return TYPE_LABELS.employee;
  if (t in TYPE_LABELS) return TYPE_LABELS[t as CounterpartyType];
  return t || '—';
}

/** Contract fields apply to supplier counterparties (incl. legacy vendor records). */
export function isSupplierType(value: unknown): boolean {
  const t = String(value ?? '').toLowerCase();
  return t === 'supplier' || t === 'vendor';
}
