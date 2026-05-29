<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import {
    createCounterparty,
    createCounterpartyAccount,
    createPaymentTerm,
    createTaxCode,
    listCounterparties,
    listCounterpartyAccounts,
    listPaymentTerms,
    listTaxCodes,
    patchCounterparty,
    patchCounterpartyAccount,
  } from '$lib/api/finance-setup';

  type Tab = 'subaccounts' | 'terms' | 'tax';

  let tab = $state<Tab>('subaccounts');
  let error = $state('');
  let msg = $state('');

  let counterparties = $state<Array<Record<string, unknown>>>([]);
  let subaccounts = $state<Array<Record<string, unknown>>>([]);
  let terms = $state<Array<Record<string, unknown>>>([]);
  let taxCodes = $state<Array<Record<string, unknown>>>([]);

  let cpName = $state('');
  let cpType = $state('vendor');
  let cpCode = $state('');
  let cpHasContract = $state(false);
  let cpContractReference = $state('');
  let cpContractStartDate = $state('');
  let cpContractExpiryDate = $state('');
  let cpSupplierOwner = $state('');
  let cpContractWarningDays = $state(30);
  let cpContactEmail = $state('');

  let saCounterpartyId = $state('');
  let saCode = $state('');
  let saName = $state('');
  let saTermId = $state('');
  let saCreditLimit = $state('');
  let saCreditCurrency = $state('SGD');

  let editingId = $state<string | null>(null);
  let editTermId = $state('');
  let editCreditLimit = $state('');
  let editCreditCurrency = $state('SGD');

  let editingCpId = $state<string | null>(null);
  let editCpHasContract = $state(false);
  let editCpContractReference = $state('');
  let editCpContractStartDate = $state('');
  let editCpContractExpiryDate = $state('');
  let editCpSupplierOwner = $state('');
  let editCpContractWarningDays = $state(30);

  let termCode = $state('');
  let termLabel = $state('');
  let termDays = $state(30);

  let taxCode = $state('GST9');
  let taxDesc = $state('Standard-rated GST 9%');
  let taxRate = $state('0.09');
  let taxDirection = $state('both');
  let taxOutputGl = $state('');
  let taxInputGl = $state('');

  async function loadAll() {
    counterparties = await listCounterparties();
    subaccounts = await listCounterpartyAccounts();
    terms = await listPaymentTerms();
    taxCodes = await listTaxCodes();
    if (!saCounterpartyId && counterparties.length) {
      saCounterpartyId = String(counterparties[0].id);
    }
  }

  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    try {
      await loadAll();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    }
  });

  async function addCounterparty() {
    error = '';
    msg = '';
    const name = cpName.trim();
    if (!name) {
      error = 'Enter a legal name before adding a counterparty.';
      return;
    }
    try {
      const isVendor = isVendorType(cpType);
      const contractFields = isVendor
        ? vendorContractPayload(
            cpHasContract,
            cpContractReference,
            cpContractStartDate,
            cpContractExpiryDate,
            cpSupplierOwner,
            cpContractWarningDays
          )
        : {
            has_contract: false,
            contract_reference: null,
            contract_start_date: null,
            contract_expiry_date: null,
            supplier_owner: null,
            contract_warning_days: 30,
          };
      await createCounterparty({
        name,
        type: isVendor ? 'vendor' : cpType,
        code: cpCode || null,
        contact_email: cpContactEmail.trim() || null,
        ...contractFields,
      });
      cpName = '';
      cpCode = '';
      cpHasContract = false;
      cpContractReference = '';
      cpContractStartDate = '';
      cpContractExpiryDate = '';
      cpSupplierOwner = '';
      cpContractWarningDays = 30;
      cpContactEmail = '';
      msg = 'Counterparty created';
      await loadAll();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Create failed';
    }
  }

  function displayCounterpartyType(value: unknown): string {
    const t = String(value ?? '').toLowerCase();
    if (t === 'supplier') return 'vendor';
    if (t === 'staff') return 'Staff';
    return t || '—';
  }

  function isVendorType(value: unknown): boolean {
    const t = String(value ?? '').toLowerCase();
    return t === 'vendor' || t === 'supplier';
  }

  /** Set has_contract when checkbox is on or any contract field is filled. */
  function vendorContractPayload(
    hasContractCheckbox: boolean,
    reference: string,
    startDate: string,
    expiryDate: string,
    supplierOwner: string,
    warningDays: number
  ) {
    const contract_reference = reference.trim() || null;
    const contract_start_date = startDate || null;
    const contract_expiry_date = expiryDate || null;
    const hasAny = Boolean(contract_reference || contract_start_date || contract_expiry_date);
    const has_contract = hasContractCheckbox || hasAny;
    return {
      has_contract,
      contract_reference: has_contract ? contract_reference : null,
      contract_start_date: has_contract ? contract_start_date : null,
      contract_expiry_date: has_contract ? contract_expiry_date : null,
      supplier_owner: supplierOwner.trim() || null,
      contract_warning_days: warningDays,
    };
  }

  function counterpartyById(id: unknown): Record<string, unknown> | undefined {
    return counterparties.find((cp) => String(cp.id) === String(id));
  }

  function formatContractDate(value: unknown): string {
    if (!value) return '—';
    const d = String(value).slice(0, 10);
    return d || '—';
  }

  function formatContractSummary(cp: Record<string, unknown> | undefined): string {
    if (!cp || !isVendorType(cp.type)) return '—';
    if (!cp.has_contract && !cp.contract_reference && !cp.contract_expiry_date) return '—';
    const ref = cp.contract_reference ? String(cp.contract_reference) : '—';
    const start = formatContractDate(cp.contract_start_date);
    const end = formatContractDate(cp.contract_expiry_date);
    return `${ref} · ${start} → ${end}`;
  }

  function contractExpiringSoon(cp: Record<string, unknown>): boolean {
    const t = String(cp.type ?? '').toLowerCase();
    const isVendor = t === 'vendor' || t === 'supplier';
    if (!isVendor) return false;
    if (!cp.contract_expiry_date) return false;
    const expiry = new Date(String(cp.contract_expiry_date));
    if (Number.isNaN(expiry.getTime())) return false;
    const warn = Number(cp.contract_warning_days ?? 30);
    const warnDays = Number.isFinite(warn) ? warn : 30;
    const now = new Date();
    const diffDays = Math.ceil((expiry.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    return diffDays >= 0 && diffDays <= warnDays;
  }

  function formatCredit(row: Record<string, unknown>) {
    const amt = row.credit_limit_amount;
    if (amt == null || amt === '') return '—';
    const cur = String(row.credit_limit_currency ?? 'SGD');
    const n = Number(amt);
    return Number.isFinite(n) ? `${n.toLocaleString()} ${cur}` : `${amt} ${cur}`;
  }

  async function addSubaccount() {
    error = '';
    msg = '';
    try {
      const creditTrim = saCreditLimit.trim();
      await createCounterpartyAccount({
        counterparty_id: saCounterpartyId,
        account_code: saCode,
        display_name: saName,
        payment_term_id: saTermId || null,
        credit_limit_amount: creditTrim ? creditTrim : null,
        credit_limit_currency: creditTrim ? saCreditCurrency || 'SGD' : null,
      });
      saCode = '';
      saName = '';
      saCreditLimit = '';
      msg = 'Subaccount created';
      await loadAll();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Create failed';
    }
  }

  function startEditSub(row: Record<string, unknown>) {
    editingId = String(row.id);
    editTermId = row.payment_term_id ? String(row.payment_term_id) : '';
    const amt = row.credit_limit_amount;
    editCreditLimit = amt != null && amt !== '' ? String(amt) : '';
    editCreditCurrency = String(row.credit_limit_currency ?? 'SGD');
    error = '';
    msg = '';
  }

  function cancelEditSub() {
    editingId = null;
  }

  async function saveEditSub(id: string) {
    error = '';
    msg = '';
    try {
      const creditTrim = editCreditLimit.trim();
      await patchCounterpartyAccount(id, {
        payment_term_id: editTermId || null,
        credit_limit_amount: creditTrim ? creditTrim : null,
        credit_limit_currency: creditTrim ? editCreditCurrency || 'SGD' : null,
      });
      editingId = null;
      msg = 'Subaccount updated';
      await loadAll();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Update failed';
    }
  }

  async function deactivateSub(id: string) {
    error = '';
    try {
      await patchCounterpartyAccount(id, { is_active: false });
      editingId = null;
      await loadAll();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Deactivate failed';
    }
  }

  async function reactivateSub(id: string) {
    error = '';
    try {
      await patchCounterpartyAccount(id, { is_active: true });
      editingId = null;
      msg = 'Subaccount reactivated';
      await loadAll();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Reactivate failed';
    }
  }

  function startEditCounterparty(cp: Record<string, unknown>) {
    editingCpId = String(cp.id);
    editCpHasContract = Boolean(cp.has_contract);
    editCpContractReference = cp.contract_reference ? String(cp.contract_reference) : '';
    editCpContractStartDate = cp.contract_start_date
      ? String(cp.contract_start_date).slice(0, 10)
      : '';
    editCpContractExpiryDate = cp.contract_expiry_date
      ? String(cp.contract_expiry_date).slice(0, 10)
      : '';
    editCpSupplierOwner = cp.supplier_owner ? String(cp.supplier_owner) : '';
    editCpContractWarningDays = Number(cp.contract_warning_days ?? 30);
    error = '';
    msg = '';
  }

  function cancelEditCounterparty() {
    editingCpId = null;
  }

  async function saveEditCounterparty(id: string) {
    error = '';
    msg = '';
    const cp = counterpartyById(id);
    if (!cp || !isVendorType(cp.type)) {
      error = 'Contract fields apply to vendors only';
      return;
    }
    try {
      await patchCounterparty(id, vendorContractPayload(
        editCpHasContract,
        editCpContractReference,
        editCpContractStartDate,
        editCpContractExpiryDate,
        editCpSupplierOwner,
        editCpContractWarningDays
      ));
      editingCpId = null;
      msg = 'Counterparty contract saved';
      await loadAll();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Save failed';
    }
  }

  async function addTerm() {
    error = '';
    msg = '';
    try {
      await createPaymentTerm({
        code: termCode,
        label: termLabel,
        due_days: termDays,
      });
      termCode = '';
      termLabel = '';
      msg = 'Payment term created';
      await loadAll();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Create failed';
    }
  }

  async function addTax() {
    error = '';
    msg = '';
    try {
      await createTaxCode({
        code: taxCode,
        description: taxDesc,
        rate: taxRate,
        direction: taxDirection,
        output_gl_account_code: taxOutputGl || null,
        input_gl_account_code: taxInputGl || null,
      });
      msg = 'Tax code created';
      await loadAll();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Create failed';
    }
  }
</script>

<h1>Counterparty accounts</h1>
<p class="hint">
  Subaccounts, payment terms (due days), and GST mapping (`0.14.8`). Subaccount codes are not COA accounts.
  <strong>Credit limits</strong> are set per customer/supplier subaccount (Subaccounts tab), not on the payment-terms catalog.
</p>

{#if error}<p class="error">{error}</p>{/if}
{#if msg}<p class="msg">{msg}</p>{/if}

<div class="tabs">
  <button type="button" class:active={tab === 'subaccounts'} onclick={() => (tab = 'subaccounts')}>Subaccounts</button>
  <button type="button" class:active={tab === 'terms'} onclick={() => (tab = 'terms')}>Payment terms</button>
  <button type="button" class:active={tab === 'tax'} onclick={() => (tab = 'tax')}>Tax codes</button>
</div>

{#if tab === 'subaccounts'}
  <section>
    <h2>Parent counterparties</h2>
    <div class="row">
      <input bind:value={cpName} placeholder="Legal name" />
      <select bind:value={cpType}>
        <option value="customer">Customer</option>
        <option value="vendor">Vendor</option>
        <option value="staff">Staff</option>
      </select>
      <input bind:value={cpCode} placeholder="Code (optional)" />
      <input
        bind:value={cpContactEmail}
        type="email"
        placeholder="Contact email (required for staff)"
      />
      <button type="button" disabled={!cpName.trim()} onclick={addCounterparty}>
        Add counterparty
      </button>
    </div>
    {#if cpType === 'vendor'}
      <div class="row wrap vendor-contract">
        <label class="inline">
          <input type="checkbox" bind:checked={cpHasContract} />
          Contract in place
        </label>
        <input bind:value={cpContractReference} placeholder="Contract reference (optional)" maxlength="255" />
        <input type="date" bind:value={cpContractStartDate} title="Contract start date" />
        <input type="date" bind:value={cpContractExpiryDate} title="Contract expiry date" />
        <input bind:value={cpSupplierOwner} placeholder="Vendor owner (optional)" />
        <input
          type="number"
          min="0"
          bind:value={cpContractWarningDays}
          title="Days before expiry to show warning"
          placeholder="Warning days"
        />
      </div>
    {/if}
    <ul class="cp-list">
      {#each counterparties as cp}
        <li class:editing={editingCpId === String(cp.id)}>
          <div class="cp-row">
            <span>
              {cp.name} ({displayCounterpartyType(cp.type)}) — {cp.code ?? 'no code'}
              {#if isVendorType(cp.type) && (cp.has_contract || cp.contract_reference)}
                <span class="contract-inline">
                  — {formatContractSummary(cp)}
                </span>
              {/if}
              {#if contractExpiringSoon(cp)}
                <span class="warn" title="Contract expiring soon">⚠️</span>
              {/if}
            </span>
            {#if isVendorType(cp.type)}
              {#if editingCpId === String(cp.id)}
                <button type="button" onclick={() => saveEditCounterparty(String(cp.id))}>Save contract</button>
                <button type="button" class="secondary" onclick={cancelEditCounterparty}>Cancel</button>
              {:else}
                <button type="button" onclick={() => startEditCounterparty(cp)}>Edit contract</button>
              {/if}
            {/if}
          </div>
          {#if editingCpId === String(cp.id) && isVendorType(cp.type)}
            <div class="row wrap vendor-contract cp-edit">
              <label class="inline">
                <input type="checkbox" bind:checked={editCpHasContract} />
                Contract in place
              </label>
              <input bind:value={editCpContractReference} placeholder="Contract reference" maxlength="255" />
              <input type="date" bind:value={editCpContractStartDate} title="Contract start date" />
              <input type="date" bind:value={editCpContractExpiryDate} title="Contract expiry date" />
              <input bind:value={editCpSupplierOwner} placeholder="Vendor owner (optional)" />
              <input
                type="number"
                min="0"
                bind:value={editCpContractWarningDays}
                title="Days before expiry to show warning"
                placeholder="Warning days"
              />
            </div>
          {/if}
        </li>
      {/each}
    </ul>
  </section>

  <section>
    <h2>Subaccounts</h2>
    <p class="hint">Due days come from the payment-terms catalog; maximum credit exposure is set here per subaccount.</p>
    <div class="row">
      <select bind:value={saCounterpartyId}>
        {#each counterparties as cp}
          <option value={String(cp.id)}>{cp.name}</option>
        {/each}
      </select>
      <input bind:value={saCode} placeholder="Account code" maxlength="50" />
      <input bind:value={saName} placeholder="Display name" />
      <select bind:value={saTermId} title="Due days (NET30, etc.)">
        <option value="">Payment terms</option>
        {#each terms as t}
          <option value={String(t.id)}>{t.code} ({t.due_days} days)</option>
        {/each}
      </select>
      <input
        bind:value={saCreditLimit}
        placeholder="Credit limit amount"
        inputmode="decimal"
        title="Maximum outstanding amount allowed for this customer/supplier"
      />
      <select bind:value={saCreditCurrency} title="Credit limit currency">
        <option value="SGD">SGD</option>
        <option value="USD">USD</option>
        <option value="EUR">EUR</option>
        <option value="MYR">MYR</option>
      </select>
      <button type="button" onclick={addSubaccount}>Add subaccount</button>
    </div>
    {#if saCounterpartyId}
      {@const selectedCp = counterpartyById(saCounterpartyId)}
      {#if selectedCp && isVendorType(selectedCp.type)}
        <p class="contract-panel">
          <strong>Contract ({selectedCp.name}):</strong>
          {#if selectedCp.has_contract || selectedCp.contract_reference || selectedCp.contract_expiry_date}
            Ref {selectedCp.contract_reference ?? '—'} · Start {formatContractDate(selectedCp.contract_start_date)}
            · Expiry {formatContractDate(selectedCp.contract_expiry_date)}
            {#if selectedCp.supplier_owner}
              · Owner {selectedCp.supplier_owner}
            {/if}
          {:else}
            No contract on file — use <strong>Edit contract</strong> in Parent counterparties.
          {/if}
        </p>
      {/if}
    {/if}
    <table>
      <thead>
        <tr>
          <th>Code</th>
          <th>Name</th>
          <th>Parent</th>
          <th>Contract ref</th>
          <th>Contract start</th>
          <th>Contract expiry</th>
          <th>Terms</th>
          <th>Credit limit</th>
          <th>Active</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {#each subaccounts as row}
          {@const parentCp = counterpartyById(row.counterparty_id)}
          <tr class:editing={editingId === String(row.id)}>
            <td>{row.account_code}</td>
            <td>{row.display_name}</td>
            <td>{row.counterparty_name}</td>
            <td>{parentCp?.contract_reference ?? '—'}</td>
            <td>{formatContractDate(parentCp?.contract_start_date)}</td>
            <td>{formatContractDate(parentCp?.contract_expiry_date)}</td>
            <td>
              {#if editingId === String(row.id)}
                <select bind:value={editTermId} class="cell-input">
                  <option value="">None</option>
                  {#each terms.filter((t) => t.is_active !== false) as t}
                    <option value={String(t.id)}>{t.code} ({t.due_days}d)</option>
                  {/each}
                </select>
              {:else}
                {row.payment_term_code ?? '—'}
              {/if}
            </td>
            <td>
              {#if editingId === String(row.id)}
                <div class="credit-edit">
                  <input
                    bind:value={editCreditLimit}
                    placeholder="Amount"
                    inputmode="decimal"
                    class="cell-input"
                  />
                  <select bind:value={editCreditCurrency} class="cell-input narrow">
                    <option value="SGD">SGD</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                    <option value="MYR">MYR</option>
                  </select>
                </div>
              {:else}
                {formatCredit(row)}
              {/if}
            </td>
            <td>{row.is_active ? 'Yes' : 'No'}</td>
            <td class="actions">
              {#if row.is_active}
                {#if editingId === String(row.id)}
                  <button type="button" onclick={() => saveEditSub(String(row.id))}>Save</button>
                  <button type="button" class="secondary" onclick={cancelEditSub}>Cancel</button>
                {:else}
                  <button type="button" onclick={() => startEditSub(row)}>Edit</button>
                  <button type="button" class="secondary" onclick={() => deactivateSub(String(row.id))}>
                    Deactivate
                  </button>
                {/if}
              {:else}
                <button type="button" onclick={() => reactivateSub(String(row.id))}>Reactivate</button>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </section>
{:else if tab === 'terms'}
  <section>
    <h2>Payment terms catalog</h2>
    <p class="hint">
      Defines <strong>due days</strong> (and optional discounts) for invoices. To set how much credit a
      <strong>customer</strong> may run up to, use the Subaccounts tab — credit limit is per subaccount, not per term code.
    </p>
    <div class="row">
      <input bind:value={termCode} placeholder="Code e.g. NET45" />
      <input bind:value={termLabel} placeholder="Label" />
      <input type="number" bind:value={termDays} min="0" />
      <button type="button" onclick={addTerm}>Add term</button>
    </div>
    <table>
      <thead><tr><th>Code</th><th>Label</th><th>Due days</th><th>Active</th></tr></thead>
      <tbody>
        {#each terms as t}
          <tr>
            <td>{t.code}</td>
            <td>{t.label}</td>
            <td>{t.due_days}</td>
            <td>{t.is_active ? 'Yes' : 'No'}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </section>
{:else}
  <section>
    <h2>Tenant tax codes</h2>
    <p class="hint">GL codes must exist in your imported chart of accounts.</p>
    <div class="row wrap">
      <input bind:value={taxCode} placeholder="Code e.g. GST9" />
      <input bind:value={taxDesc} placeholder="Description" />
      <input bind:value={taxRate} placeholder="Rate 0.09" />
      <select bind:value={taxDirection}>
        <option value="output">Output</option>
        <option value="input">Input</option>
        <option value="both">Both</option>
      </select>
      <input bind:value={taxOutputGl} placeholder="Output GL code" />
      <input bind:value={taxInputGl} placeholder="Input GL code" />
      <button type="button" onclick={addTax}>Add tax code</button>
    </div>
    <table>
      <thead><tr><th>Code</th><th>Rate</th><th>Direction</th><th>Output GL</th><th>Input GL</th></tr></thead>
      <tbody>
        {#each taxCodes as row}
          <tr>
            <td>{row.code}</td>
            <td>{row.rate}</td>
            <td>{row.direction}</td>
            <td>{row.output_gl_account_code ?? '—'}</td>
            <td>{row.input_gl_account_code ?? '—'}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </section>
{/if}

<style>
  .hint { color: #555; font-size: 0.9rem; }
  .error { color: #b00020; }
  .msg { color: #006400; }
  .tabs { display: flex; gap: 0.5rem; margin: 1rem 0; }
  .tabs button { padding: 0.4rem 0.8rem; border: 1px solid #ccc; background: #f5f5f5; cursor: pointer; }
  .tabs button.active { background: #003366; color: #fff; border-color: #003366; }
  section { margin-bottom: 2rem; }
  .row { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem; align-items: center; }
  .wrap { flex-wrap: wrap; }
  table { width: 100%; border-collapse: collapse; }
  th, td { border: 1px solid #ddd; padding: 0.4rem; text-align: left; vertical-align: middle; }
  tr.editing { background: #f0f7ff; }
  .cell-input { max-width: 10rem; padding: 0.25rem; }
  .cell-input.narrow { max-width: 5rem; }
  .credit-edit { display: flex; flex-wrap: wrap; gap: 0.25rem; align-items: center; }
  .actions { white-space: nowrap; }
  .actions button { margin-right: 0.25rem; }
  button.secondary { background: #eee; color: #333; border: 1px solid #ccc; }
  .warn { margin-left: 0.5rem; }
  .vendor-contract input { min-width: 12rem; }
  label.inline { display: inline-flex; gap: 0.35rem; align-items: center; }
  .cp-list { list-style: none; padding: 0; }
  .cp-list li { margin-bottom: 0.75rem; padding: 0.5rem; border: 1px solid #eee; border-radius: 4px; }
  .cp-list li.editing { background: #f0f7ff; }
  .cp-row { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; justify-content: space-between; }
  .contract-inline { color: #555; font-size: 0.9rem; }
  .cp-edit { margin-top: 0.5rem; }
  .contract-panel {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    padding: 0.5rem 0.75rem;
    border-radius: 4px;
    font-size: 0.9rem;
    margin-bottom: 0.75rem;
  }
</style>
