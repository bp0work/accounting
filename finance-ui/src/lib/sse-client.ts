const ACCESS_TOKEN_KEY = 'finance_access_token';
const STREAM_PATH = '/api/events/stream';

export type SseHandler = (eventType: string, data: unknown) => void;

function getAccessToken(): string | null {
  if (typeof localStorage === 'undefined') return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

function parseEventData(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/** Subscribe to finance SSE; returns cleanup function. */
export function subscribeFinanceEvents(onEvent: SseHandler): () => void {
  const token = getAccessToken();
  if (!token) return () => {};

  const url = `${STREAM_PATH}?token=${encodeURIComponent(token)}`;
  const source = new EventSource(url);

  source.addEventListener('case.status_changed', (ev) => {
    onEvent('case.status_changed', parseEventData((ev as MessageEvent).data));
  });

  source.onmessage = (ev) => {
    onEvent('message', parseEventData(ev.data));
  };

  return () => {
    source.close();
  };
}
