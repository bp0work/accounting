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
    patchCounterpartyAccount,
  } from '$lib/api/admin';

  type Tab = 'subaccounts' | 'terms' | 'tax';

  let tab = $state<Tab>('subaccounts');
  let error = $state('');
  let msg = $state('');

  let counterparties = $state<Array<Record<string, unknown>>>([]);
  let subaccounts = $state<Array<Record<string, unknown>>>([]);
  let terms = $state<Array<Record<string, unknown>>>([]);
  let taxCodes = $state<Array<Record<string, unknown>>>([]);

  let cpName = $state('');
  let cpType = $state('supplier');
  let cpCode = $state('');

  let saCounterpartyId = $state('');
  let saCode = $state('');
  let saName = $state('');
  let saTermId = $state('');

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
    try {
      await createCounterparty({
        name: cpName,
        type: cpType,
        code: cpCode || null,
      });
      cpName = '';
      cpCode = '';
      msg = 'Counterparty created';
      await loadAll();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Create failed';
    }
  }

  async function addSubaccount() {
    error = '';
    msg = '';
    try {
      await createCounterpartyAccount({
        counterparty_id: saCounterpartyId,
        account_code: saCode,
        display_name: saName,
        payment_term_id: saTermId || null,
      });
      saCode = '';
      saName = '';
      msg = 'Subaccount created';
      await loadAll();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Create failed';
    }
  }

  async function deactivateSub(id: string) {
    error = '';
    try {
      await patchCounterpartyAccount(id, { is_active: false });
      await loadAll();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Deactivate failed';
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
<p class="hint">Subaccounts, payment terms, and GST mapping (`0.14.8`). Subaccount codes are not COA accounts.</p>

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
        <option value="supplier">Supplier</option>
      </select>
      <input bind:value={cpCode} placeholder="Code (optional)" />
      <button type="button" onclick={addCounterparty}>Add counterparty</button>
    </div>
    <ul>
      {#each counterparties as cp}
        <li>{cp.name} ({cp.type}) — {cp.code ?? 'no code'}</li>
      {/each}
    </ul>
  </section>

  <section>
    <h2>Subaccounts</h2>
    <div class="row">
      <select bind:value={saCounterpartyId}>
        {#each counterparties as cp}
          <option value={String(cp.id)}>{cp.name}</option>
        {/each}
      </select>
      <input bind:value={saCode} placeholder="Account code" maxlength="50" />
      <input bind:value={saName} placeholder="Display name" />
      <select bind:value={saTermId}>
        <option value="">Default terms</option>
        {#each terms as t}
          <option value={String(t.id)}>{t.code} ({t.due_days}d)</option>
        {/each}
      </select>
      <button type="button" onclick={addSubaccount}>Add subaccount</button>
    </div>
    <table>
      <thead>
        <tr><th>Code</th><th>Name</th><th>Parent</th><th>Terms</th><th>Active</th><th></th></tr>
      </thead>
      <tbody>
        {#each subaccounts as row}
          <tr>
            <td>{row.account_code}</td>
            <td>{row.display_name}</td>
            <td>{row.counterparty_name}</td>
            <td>{row.payment_term_code ?? '—'}</td>
            <td>{row.is_active ? 'Yes' : 'No'}</td>
            <td>
              {#if row.is_active}
                <button type="button" onclick={() => deactivateSub(String(row.id))}>Deactivate</button>
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
  th, td { border: 1px solid #ddd; padding: 0.4rem; text-align: left; }
</style>
