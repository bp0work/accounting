import { writable } from 'svelte/store';
import { subscribeFinanceEvents } from '$lib/sse-client';

export type CaseStatusChangedEvent = {
  type?: string;
  case_id?: string;
  case_number?: string;
  status?: string;
};

type LiveUpdatesState = {
  connected: boolean;
  lastCaseStatusEvent: CaseStatusChangedEvent | null;
  sequence: number;
};

const initialState: LiveUpdatesState = {
  connected: false,
  lastCaseStatusEvent: null,
  sequence: 0,
};

export const liveUpdates = writable<LiveUpdatesState>(initialState);

let unsubscribeSse: (() => void) | null = null;

export function startLiveUpdates(): void {
  if (unsubscribeSse) return;
  unsubscribeSse = subscribeFinanceEvents((eventType, data) => {
    if (eventType === 'connected') {
      liveUpdates.update((s) => ({ ...s, connected: true }));
      return;
    }
    if (eventType === 'case.status_changed') {
      const payload = (data ?? {}) as CaseStatusChangedEvent;
      liveUpdates.update((s) => ({
        connected: true,
        lastCaseStatusEvent: payload,
        sequence: s.sequence + 1,
      }));
      return;
    }
    liveUpdates.update((s) => ({ ...s, connected: true, sequence: s.sequence + 1 }));
  });
}

export function stopLiveUpdates(): void {
  if (unsubscribeSse) {
    unsubscribeSse();
    unsubscribeSse = null;
  }
  liveUpdates.set(initialState);
}
