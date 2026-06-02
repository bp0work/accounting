<script lang="ts">
  import { onDestroy } from 'svelte';
  import { fetchVendorSuggestions, type VendorSuggestion } from '$lib/api/vendor-suggestions';

  export let value: string = '';
  export let onSelect: (name: string) => void;
  export let placeholder: string = 'Type vendor name...';
  export let disabled: boolean = false;

  let rootEl: HTMLDivElement;
  let open = false;
  let loading = false;
  let suggestions: VendorSuggestion[] = [];
  let activeIndex = -1;
  let debounceTimer: ReturnType<typeof setTimeout> | null = null;
  let listId = `vendor-suggestions-${Math.random().toString(36).slice(2, 9)}`;

  $: counterpartySuggestions = suggestions.filter((row) => row.source === 'counterparty');
  $: historySuggestions = suggestions.filter((row) => row.source === 'case_history');
  $: flatSuggestions = [...counterpartySuggestions, ...historySuggestions];

  function counterpartyBadge(type: string | null): string {
    if (type === 'employee' || type === 'staff') return 'Employee';
    if (type === 'supplier') return 'Supplier';
    return type ? type.charAt(0).toUpperCase() + type.slice(1) : 'Counterparty';
  }

  function scheduleFetch(query: string) {
    if (debounceTimer) clearTimeout(debounceTimer);
    if (query.trim().length < 2) {
      suggestions = [];
      open = false;
      activeIndex = -1;
      loading = false;
      return;
    }
    debounceTimer = setTimeout(() => {
      void loadSuggestions(query.trim());
    }, 300);
  }

  async function loadSuggestions(query: string) {
    loading = true;
    try {
      suggestions = await fetchVendorSuggestions(query);
      open = true;
      activeIndex = suggestions.length > 0 ? 0 : -1;
    } catch {
      suggestions = [];
      open = true;
      activeIndex = -1;
    } finally {
      loading = false;
    }
  }

  function closeDropdown() {
    open = false;
    activeIndex = -1;
  }

  function choose(name: string) {
    value = name;
    onSelect(name);
    closeDropdown();
  }

  function handleInput(event: Event) {
    const target = event.target as HTMLInputElement;
    value = target.value;
    scheduleFetch(value);
  }

  function handleFocus() {
    if (value.trim().length >= 2) {
      scheduleFetch(value);
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (!open && (event.key === 'ArrowDown' || event.key === 'ArrowUp') && value.trim().length >= 2) {
      scheduleFetch(value);
      event.preventDefault();
      return;
    }
    if (!open) return;

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      if (flatSuggestions.length === 0) return;
      activeIndex = (activeIndex + 1) % flatSuggestions.length;
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      if (flatSuggestions.length === 0) return;
      activeIndex = (activeIndex - 1 + flatSuggestions.length) % flatSuggestions.length;
    } else if (event.key === 'Enter') {
      if (activeIndex >= 0 && flatSuggestions[activeIndex]) {
        event.preventDefault();
        choose(flatSuggestions[activeIndex].name);
      }
    } else if (event.key === 'Escape') {
      event.preventDefault();
      closeDropdown();
    }
  }

  function handleWindowClick(event: MouseEvent) {
    if (open && rootEl && !rootEl.contains(event.target as Node)) {
      closeDropdown();
    }
  }

  onDestroy(() => {
    if (debounceTimer) clearTimeout(debounceTimer);
  });
</script>

<svelte:window on:click={handleWindowClick} />

<div class="vendor-autocomplete" bind:this={rootEl}>
  <input
    type="text"
    class="vendor-input"
    {placeholder}
    {disabled}
    bind:value
    on:input={handleInput}
    on:focus={handleFocus}
    on:keydown={handleKeydown}
    role="combobox"
    aria-expanded={open}
    aria-controls={listId}
    aria-autocomplete="list"
    autocomplete="off"
  />

  {#if open}
    <div class="dropdown" id={listId} role="listbox">
      {#if loading}
        <p class="status">Searching…</p>
      {:else if suggestions.length === 0}
        <p class="status">No suggestions found</p>
      {:else}
        {#if counterpartySuggestions.length > 0}
          <p class="group-label">Registered counterparties</p>
          {#each counterpartySuggestions as row, index (row.name)}
            {@const flatIndex = index}
            <button
              type="button"
              class="option"
              class:active={activeIndex === flatIndex}
              role="option"
              aria-selected={activeIndex === flatIndex}
              on:mousedown|preventDefault={() => choose(row.name)}
            >
              <span class="name">{row.name}</span>
              <span class="badge">{counterpartyBadge(row.counterparty_type)}</span>
            </button>
          {/each}
        {/if}
        {#if historySuggestions.length > 0}
          <p class="group-label">From case history</p>
          {#each historySuggestions as row, index (row.name)}
            {@const flatIndex = counterpartySuggestions.length + index}
            <button
              type="button"
              class="option"
              class:active={activeIndex === flatIndex}
              role="option"
              aria-selected={activeIndex === flatIndex}
              on:mousedown|preventDefault={() => choose(row.name)}
            >
              <span class="name">{row.name}</span>
              <span class="badge history">Previously processed</span>
            </button>
          {/each}
        {/if}
      {/if}
    </div>
  {/if}
</div>

<style>
  .vendor-autocomplete {
    position: relative;
  }
  .vendor-input {
    width: 100%;
    box-sizing: border-box;
  }
  .dropdown {
    position: absolute;
    left: 0;
    right: 0;
    top: calc(100% + 0.25rem);
    z-index: 40;
    background: #fff;
    border: 1px solid #cbd5e1;
    border-radius: 0.375rem;
    box-shadow: 0 8px 20px rgba(15, 23, 42, 0.12);
    max-height: 16rem;
    overflow-y: auto;
    padding: 0.35rem 0;
  }
  .group-label {
    margin: 0;
    padding: 0.35rem 0.75rem 0.2rem;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    color: #64748b;
  }
  .status {
    margin: 0;
    padding: 0.5rem 0.75rem;
    font-size: 0.875rem;
    color: #64748b;
  }
  .option {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    width: 100%;
    padding: 0.45rem 0.75rem;
    border: none;
    background: none;
    font: inherit;
    font-size: 0.875rem;
    text-align: left;
    cursor: pointer;
    color: #0f172a;
  }
  .option:hover,
  .option.active {
    background: #f1f5f9;
  }
  .name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .badge {
    flex-shrink: 0;
    padding: 0.1rem 0.45rem;
    border-radius: 999px;
    background: #dbeafe;
    color: #1d4ed8;
    font-size: 0.72rem;
    font-weight: 600;
  }
  .badge.history {
    background: #f1f5f9;
    color: #475569;
  }
</style>
