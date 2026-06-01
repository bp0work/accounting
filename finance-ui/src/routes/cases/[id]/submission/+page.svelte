<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import {
    fetchCase,
    fetchCaseAttachments,
    type CaseAttachmentItem,
    type CaseItem,
  } from '$lib/api/cases';
  import { listCoaAccounts, type CoaAccountItem } from '$lib/api/coa';
  import { submissionSubmittedByDisplay } from '$lib/case-labels';
  import {
    documentTypeTitleCase,
    formatDateOnly,
    isNonZeroAmount,
  } from '$lib/format';
  import {
    formatExchangeRateLabel,
    formatForeignAmountWithSgd,
    isForeignCurrency,
    normalizedCurrency,
  } from '$lib/fx-display';

  type DetailRow = { label: string; value: string };

  let item: CaseItem | null = null;
  let attachments: CaseAttachmentItem[] = [];
  let coaAccounts: CoaAccountItem[] = [];
  let error = '';
  let loading = true;

  $: caseId = $page.params.id;

  function extractedRecord(item: CaseItem | null): Record<string, string | null> {
    const raw = item?.workflow_metadata?.extracted_fields;
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
    const out: Record<string, string | null> = {};
    for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
      if (v == null) out[k] = null;
      else out[k] = String(v);
    }
    return out;
  }

  function trimOptional(value: string | null | undefined): string | null {
    if (value == null) return null;
    const t = String(value).trim();
    return t || null;
  }

  function resolveGlAccountLabel(accountId: string | null): string | null {
    if (!accountId) return null;
    const acct = coaAccounts.find((a) => String(a.id) === accountId);
    return acct ? `${acct.account_code} — ${acct.account_name}` : null;
  }

  function documentValidatedLabel(extracted: Record<string, string | null>): string {
    const raw = extracted.document_validated ?? extracted.sender_validated;
    const normalized = String(raw ?? 'false').trim().toLowerCase();
    return normalized === 'true' || normalized === '1' || normalized === 'yes' ? 'Yes' : 'No';
  }

  function primaryDocumentAttachment(
    list: CaseAttachmentItem[],
  ): CaseAttachmentItem | null {
    const withUrl = list.filter((a) => a.download_url);
    if (!withUrl.length) return null;
    const pdf = withUrl.find((a) => a.mime_type?.toLowerCase().includes('pdf'));
    return pdf ?? withUrl[0];
  }

  function buildDetailRows(
    caseItem: CaseItem,
    extracted: Record<string, string | null>,
  ): DetailRow[] {
    const rows: DetailRow[] = [];

    rows.push({ label: 'Case number', value: caseItem.case_number });
    rows.push({
      label: 'Submitted by',
      value: submissionSubmittedByDisplay(caseItem),
    });
    rows.push({
      label: 'Date submitted',
      value: formatDateOnly(caseItem.created_at),
    });

    const vendor =
      trimOptional(extracted.vendor_name) ?? trimOptional(extracted.merchant_name);
    rows.push({ label: 'Vendor name', value: vendor ?? '—' });

    rows.push({
      label: 'Document type',
      value: documentTypeTitleCase(extracted.document_type),
    });

    const docNumber =
      trimOptional(extracted.document_number) ?? trimOptional(extracted.invoice_number);
    if (docNumber) {
      rows.push({ label: 'Document number', value: docNumber });
    }

    const docDate =
      trimOptional(extracted.document_date) ?? trimOptional(extracted.invoice_date);
    rows.push({
      label: 'Document date',
      value: formatDateOnly(docDate),
    });

    const currency = normalizedCurrency(extracted.currency);
    rows.push({
      label: 'Currency',
      value: currency,
    });

    const tax = extracted.tax_amount ?? extracted.gst_amount ?? null;
    if (isNonZeroAmount(tax)) {
      rows.push({
        label: 'Tax amount',
        value: formatForeignAmountWithSgd(
          currency,
          tax,
          extracted.sgd_tax,
          extracted.exchange_rate,
        ),
      });
    }

    const total = extracted.total_amount ?? extracted.amount ?? null;
    rows.push({
      label: 'Total amount (incl. tax)',
      value: formatForeignAmountWithSgd(
        currency,
        total,
        extracted.sgd_amount,
        extracted.exchange_rate,
      ),
    });

    if (isForeignCurrency(currency)) {
      const rateLabel = formatExchangeRateLabel(currency, extracted.exchange_rate);
      if (rateLabel) {
        rows.push({ label: 'Exchange rate', value: rateLabel });
      }
    }

    const purpose = trimOptional(extracted.business_purpose);
    rows.push({ label: 'Business purpose', value: purpose ?? '—' });

    const glLabel = resolveGlAccountLabel(trimOptional(extracted.gl_account_id));
    if (glLabel) {
      rows.push({ label: 'GL account', value: glLabel });
    }

    rows.push({
      label: 'Document validated by submitter',
      value: documentValidatedLabel(extracted),
    });

    const doc = primaryDocumentAttachment(attachments);
    rows.push({
      label: 'Submitted document',
      value: doc?.download_url ? doc.filename : '—',
    });

    return rows;
  }

  $: extracted = extractedRecord(item);
  $: detailRows = item ? buildDetailRows(item, extracted) : [];
  $: documentLink = primaryDocumentAttachment(attachments);

  async function load() {
    loading = true;
    error = '';
    try {
      const [caseData, attachmentData, coa] = await Promise.all([
        fetchCase(caseId),
        fetchCaseAttachments(caseId),
        listCoaAccounts({ is_active: true }),
      ]);
      item = caseData;
      attachments = attachmentData.data ?? [];
      coaAccounts = coa;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load submission detail';
      item = null;
      attachments = [];
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<a href="/cases/{caseId}">← Back to case</a>
<h1>Submission detail</h1>
{#if item?.subject}
  <p class="subtitle">{item.subject}</p>
{/if}

{#if error}<p class="error">{error}</p>{/if}
{#if loading}
  <p class="hint">Loading…</p>
{:else if item}
  <section class="card">
    <dl class="extracted">
      {#each detailRows as row (row.label)}
        <dt>{row.label}</dt>
        <dd>
          {#if row.label === 'Submitted document' && documentLink?.download_url}
            <a
              href={documentLink.download_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {documentLink.filename}
            </a>
          {:else}
            {row.value}
          {/if}
        </dd>
      {/each}
    </dl>
  </section>
{/if}

<style>
  a {
    color: #1d4ed8;
  }
  h1 {
    margin: 0.75rem 0 0.25rem;
  }
  .subtitle {
    margin: 0 0 1rem;
    color: #475569;
    font-size: 1rem;
  }
  .hint {
    color: #64748b;
  }
  .error {
    color: #b91c1c;
  }
  .card {
    margin-top: 0.5rem;
    padding: 1rem 1.25rem;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background: #fff;
  }
  .extracted {
    display: grid;
    grid-template-columns: minmax(10rem, auto) 1fr;
    gap: 0.35rem 0.75rem;
    margin: 0;
  }
  .extracted dt {
    font-weight: 600;
    color: #475569;
  }
  .extracted dd {
    margin: 0;
  }
</style>
