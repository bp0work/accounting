import { apiUrl, ensureValidAccessToken, getToken } from './client';

export type SseHandler = (eventType: string, data: unknown) => void;

/** Subscribe to finance SSE; returns cleanup function. */
export function subscribeFinanceEvents(onEvent: SseHandler): () => void {
  let source: EventSource | null = null;
  let closed = false;

  void (async () => {
    const token = getToken();
    if (!token) return;
    try {
      await ensureValidAccessToken();
    } catch {
      return;
    }
    if (closed) return;

    const url = `${apiUrl('/events/stream')}?access_token=${encodeURIComponent(getToken() ?? '')}`;
    source = new EventSource(url);

    source.addEventListener('case.status_changed', (ev) => {
      try {
        onEvent('case.status_changed', JSON.parse((ev as MessageEvent).data));
      } catch {
        onEvent('case.status_changed', null);
      }
    });
    source.addEventListener('message', (ev) => {
      try {
        onEvent('message', JSON.parse((ev as MessageEvent).data));
      } catch {
        onEvent('message', null);
      }
    });
    source.onmessage = (ev) => {
      try {
        onEvent('message', JSON.parse(ev.data));
      } catch {
        onEvent('message', null);
      }
    };
  })();

  return () => {
    closed = true;
    source?.close();
  };
}
