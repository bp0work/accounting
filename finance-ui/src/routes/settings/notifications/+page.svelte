<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '$lib/api/client';

  let templates: { event_key: string; display_name: string; user_overridable?: boolean }[] = [];
  let saved = false;
  let error = '';

  onMount(async () => {
    try {
      templates = await apiFetch('/notification-templates');
    } catch (e) {
      error = e instanceof Error ? e.message : 'Load failed';
    }
  });

  async function saveDefaults() {
    try {
      await apiFetch('/users/me/notification-preferences', {
        method: 'PUT',
        body: JSON.stringify({
          quiet_hours: {},
          channels: { email: true, in_app: true },
          subscriptions: templates
            .filter((t) => t.user_overridable !== false)
            .map((t) => ({
              event_key: t.event_key,
              email: true,
              in_app: true,
              digest: 'off',
            })),
        }),
      });
      saved = true;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Save failed';
    }
  }
</script>

<h1>Notification preferences</h1>
{#if error}<p style="color: #b91c1c;">{error}</p>{/if}
{#if saved}<p style="color: #15803d;">Preferences saved.</p>{/if}

<p>Catalog ({templates.length} events):</p>
<ul>
  {#each templates as t}
    <li>{t.display_name} <code>{t.event_key}</code></li>
  {/each}
</ul>

<button on:click={saveDefaults}>Enable all in-app notifications</button>
