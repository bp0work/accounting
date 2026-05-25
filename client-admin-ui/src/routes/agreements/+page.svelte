<script module lang="ts">
  export const ssr = false;
</script>
<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import { listRentalAgreements, createRentalAgreement, listDirectorAgreements, createDirectorAgreement } from '$lib/api/admin';
  let tab: 'rental' | 'director' = 'rental';
  let rental: Array<Record<string, unknown>> = [];
  let director: Array<Record<string, unknown>> = [];
  let r = { property_address: '', monthly_rent_sgd: '', business_use_percent: '100', effective_date: '', landlord_name: '' };
  let d = { director_name: '', director_email: '', authorised_expense_types: 'home office,meals', monthly_limit_sgd: '', effective_date: '' };
  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    rental = await listRentalAgreements();
    director = await listDirectorAgreements();
  });
  async function addRental() {
    await createRentalAgreement({ ...r, monthly_rent_sgd: Number(r.monthly_rent_sgd), business_use_percent: Number(r.business_use_percent) });
    rental = await listRentalAgreements();
  }
  async function addDirector() {
    await createDirectorAgreement({
      ...d,
      authorised_expense_types: d.authorised_expense_types.split(',').map((s) => s.trim()),
      monthly_limit_sgd: d.monthly_limit_sgd ? Number(d.monthly_limit_sgd) : null,
    });
    director = await listDirectorAgreements();
  }
</script>
<h1>Agreements</h1>
<div class="tabs">
  <button type="button" class:active={tab === 'rental'} on:click={() => (tab = 'rental')}>Rental</button>
  <button type="button" class:active={tab === 'director'} on:click={() => (tab = 'director')}>Director expense</button>
</div>
{#if tab === 'rental'}
  <div class="card">
    <input placeholder="Property address" bind:value={r.property_address} />
    <input placeholder="Monthly rent SGD" bind:value={r.monthly_rent_sgd} />
    <input placeholder="Business %" bind:value={r.business_use_percent} />
    <input type="date" bind:value={r.effective_date} />
    <button type="button" on:click={addRental}>Add rental</button>
  </div>
  <ul>{#each rental as x}<li>{x.property_address} — ${x.monthly_rent_sgd}/mo</li>{/each}</ul>
{:else}
  <div class="card">
    <input placeholder="Director name" bind:value={d.director_name} />
    <input placeholder="Email" bind:value={d.director_email} />
    <input placeholder="Types (comma-separated)" bind:value={d.authorised_expense_types} />
    <input placeholder="Monthly limit" bind:value={d.monthly_limit_sgd} />
    <input type="date" bind:value={d.effective_date} />
    <button type="button" on:click={addDirector}>Add agreement</button>
  </div>
  <ul>{#each director as x}<li>{x.director_name} — {x.director_email}</li>{/each}</ul>
{/if}
