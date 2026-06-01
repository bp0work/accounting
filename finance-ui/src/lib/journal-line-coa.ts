import type { CoaAccountItem } from '$lib/api/coa';
import type { JournalEntryApprovalDetail, JournalEntryLineDetail } from '$lib/api/cases';

export function parseJournalMoney(value: string | null | undefined): number {
  if (value == null || value === '') return 0;
  const n = Number(String(value).replace(/,/g, ''));
  return Number.isFinite(n) ? n : 0;
}

export function isGstJournalLine(line: Pick<JournalEntryLineDetail, 'account_code'>): boolean {
  return line.account_code === '2011';
}

/** Expense debit line or payable credit line; GST 2011 is not editable. */
export function journalLineCoaType(
  line: Pick<JournalEntryLineDetail, 'account_code' | 'debit' | 'credit'>,
): 'expense' | 'liability' | null {
  if (line.account_code === '2011') return null;
  if (parseJournalMoney(line.debit) > 0) return 'expense';
  if (parseJournalMoney(line.credit) > 0) return 'liability';
  return null;
}

function normalizeAccountId(raw: string | null | undefined): string {
  if (raw == null) return '';
  const id = String(raw).trim();
  if (!id || id === 'undefined' || id === 'null') return '';
  return id;
}

/**
 * Resolve COA UUID for a journal line — prefer account_id, then account_code, then header ids.
 */
export function resolveJournalLineAccountId(
  line: JournalEntryLineDetail,
  type: 'expense' | 'liability',
  expenseAccounts: CoaAccountItem[],
  liabilityAccounts: CoaAccountItem[],
  header?: Pick<JournalEntryApprovalDetail, 'expense_account_id' | 'payable_account_id'> | null,
): string {
  const list = type === 'expense' ? expenseAccounts : liabilityAccounts;
  const fromId = normalizeAccountId(line.account_id);
  if (fromId) {
    const match = list.find((a) => String(a.id) === fromId);
    if (match) return String(match.id);
  }
  const code = line.account_code?.trim();
  if (code) {
    const byCode = list.find((a) => a.account_code === code);
    if (byCode) return String(byCode.id);
  }
  if (type === 'expense' && header?.expense_account_id) {
    const hid = normalizeAccountId(header.expense_account_id);
    if (hid && list.some((a) => String(a.id) === hid)) return hid;
  }
  if (type === 'liability' && header?.payable_account_id) {
    const hid = normalizeAccountId(header.payable_account_id);
    if (hid && list.some((a) => String(a.id) === hid)) return hid;
  }
  return fromId;
}

export function journalLineCoaOptionsForLine(
  line: JournalEntryLineDetail,
  type: 'expense' | 'liability',
  expenseAccounts: CoaAccountItem[],
  liabilityAccounts: CoaAccountItem[],
  header?: Pick<JournalEntryApprovalDetail, 'expense_account_id' | 'payable_account_id'> | null,
): CoaAccountItem[] {
  const list = type === 'expense' ? expenseAccounts : liabilityAccounts;
  const resolvedId = resolveJournalLineAccountId(line, type, expenseAccounts, liabilityAccounts, header);
  if (!resolvedId) return list;
  if (list.some((a) => String(a.id) === resolvedId)) return list;
  if (line.account_code && line.account_name) {
    return [
      {
        id: resolvedId,
        account_code: line.account_code,
        account_name: line.account_name,
      },
      ...list,
    ];
  }
  return list;
}
