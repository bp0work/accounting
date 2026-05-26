<script module lang="ts">
  export const ssr = false;
</script>

<script lang="ts">
  import { onMount } from 'svelte';
  import { ensureValidAccessToken } from '$lib/api/client';
  import {
    getBindingAuthority,
    patchBindingAuthority,
    type BindingAuthorityConfig,
    type BindingAuthorityThresholds,
  } from '$lib/api/admin';

  type DocKey = 'ap_invoice' | 'ar_invoice' | 'expense_claim';
  type PolicyField =
    | 'ap_approval_thresholds'
    | 'ar_approval_thresholds'
    | 'expense_approval_thresholds';

  const sections: { docKey: DocKey; policyField: PolicyField }[] = [
    { docKey: 'ap_invoice', policyField: 'ap_approval_thresholds' },
    { docKey: 'ar_invoice', policyField: 'ar_approval_thresholds' },
    { docKey: 'expense_claim', policyField: 'expense_approval_thresholds' },
  ];

  const fieldMeta: { key: keyof BindingAuthorityThresholds; label: string; hint: string; step?: string }[] = [
    {
      key: 'tier_1_ceiling',
      label: 'Tier 1 ceiling (SGD)',
      hint: 'Agent auto-posts without human approval',
    },
    {
      key: 'tier_2_ceiling',
      label: 'Tier 2 ceiling (SGD)',
      hint: 'Accounts Manager (acc) approval required',
    },
    {
      key: 'tier_3_threshold',
      label: 'Tier 3 threshold (SGD)',
      hint: 'CFO/FD approval required (≥ this amount)',
    },
    {
      key: 'stp_confidence_minimum',
      label: 'STP confidence minimum',
      hint: 'Minimum extraction confidence for Tier 1 auto-post',
      step: '0.01',
    },
    {
      key: 'tier_2_sla_hours',
      label: 'Tier 2 SLA (hours)',
      hint: 'Hours before auto-escalation to CFO',
      step: '1',
    },
    {
      key: 'tier_3_sla_hours',
      label: 'Tier 3 SLA (hours)',
      hint: 'Hours before auto-escalation to CEO',
      step: '1',
    },
  ];

  let config: BindingAuthorityConfig | null = null;
  let drafts: Record<DocKey, BindingAuthorityThresholds> = {
    ap_invoice: emptyThresholds(),
    ar_invoice: emptyThresholds(),
    expense_claim: emptyThresholds(),
  };
  let error = '';
  let msg = '';
  let saving: DocKey | null = null;

  function emptyThresholds(): BindingAuthorityThresholds {
    return {
      tier_1_ceiling: 3000,
      tier_2_ceiling: 10000,
      tier_3_threshold: 10000,
      stp_confidence_minimum: 0.9,
      tier_2_sla_hours: 4,
      tier_3_sla_hours: 8,
    };
  }

  function syncDrafts(data: BindingAuthorityConfig) {
    for (const { docKey } of sections) {
      drafts[docKey] = { ...data[docKey].thresholds };
    }
    drafts = drafts;
  }

  onMount(async () => {
    if (!(await ensureValidAccessToken())) return;
    try {
      config = await getBindingAuthority();
      syncDrafts(config);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    }
  });

  async function saveSection(docKey: DocKey, policyField: PolicyField) {
    error = '';
    msg = '';
    saving = docKey;
    try {
      config = await patchBindingAuthority({
        [policyField]: { ...drafts[docKey] },
      });
      syncDrafts(config);
      msg = `${config[docKey].label} thresholds saved.`;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Save failed';
    } finally {
      saving = null;
    }
  }
</script>

<h1>Binding Authority</h1>
<p class="intro">
  Configure approval tiers for AP invoices, AR invoices, and expense claims. Amounts are in SGD.
</p>

{#if error}<p class="err">{error}</p>{/if}
{#if msg}<p class="ok">{msg}</p>{/if}

{#if config}
  {#each sections as { docKey, policyField }}
    {@const doc = config[docKey]}
    <section class="card">
      <h2>{doc.label}</h2>
      <div class="grid">
        {#each fieldMeta as field}
          <label>
            <span class="label">{field.label}</span>
            <span class="hint">{field.hint}</span>
            <input
              type="number"
              step={field.step ?? '1'}
              min="0"
              bind:value={drafts[docKey][field.key]}
            />
          </label>
        {/each}
      </div>
      <button
        type="button"
        disabled={saving === docKey}
        on:click={() => saveSection(docKey, policyField)}
      >
        {saving === docKey ? 'Saving…' : 'Save'}
      </button>
    </section>
  {/each}
{:else if !error}
  <p>Loading…</p>
{/if}

<style>
  .intro {
    color: #475569;
    margin-bottom: 1.25rem;
  }
  .card {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin-bottom: 1.25rem;
    background: #fff;
  }
  .card h2 {
    margin-top: 0;
  }
  .grid {
    display: grid;
    gap: 1rem;
    margin-bottom: 1rem;
  }
  @media (min-width: 640px) {
    .grid {
      grid-template-columns: 1fr 1fr;
    }
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .label {
    font-weight: 600;
    font-size: 0.9rem;
  }
  .hint {
    font-size: 0.8rem;
    color: #64748b;
  }
  input {
    padding: 0.4rem 0.5rem;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
  }
  .err {
    color: #b91c1c;
  }
  .ok {
    color: #15803d;
  }
</style>
