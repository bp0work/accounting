import { ensureValidAccessToken } from '$lib/api/client';

const STREAM_PATH = '/api/events/stream';
const RECONNECT_DELAY_MS = 5000;

export type SseHandler = (eventType: string, data: unknown) => void;

function parseEventData(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function connectSource(token: string): EventSource {
  const url = `${STREAM_PATH}?token=${encodeURIComponent(token)}`;
  return new EventSource(url);
}

/**
 * Subscribe to finance SSE with auto-reconnect.
 * Returns cleanup function.
 */
export function subscribeFinanceEvents(onEvent: SseHandler): () => void {
  let source: EventSource | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let closed = false;

  const scheduleReconnect = () => {
    if (closed || reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      void connect();
    }, RECONNECT_DELAY_MS);
  };

  const cleanupSource = () => {
    if (!source) return;
    source.close();
    source = null;
  };

  const connect = async () => {
    if (closed) return;
    cleanupSource();
    let token: string | null = null;
    try {
      token = await ensureValidAccessToken();
    } catch {
      scheduleReconnect();
      return;
    }
    if (!token) {
      scheduleReconnect();
      return;
    }

    source = connectSource(token);

    source.addEventListener('connected', (ev) => {
      onEvent('connected', parseEventData((ev as MessageEvent).data));
    });

    source.addEventListener('case.status_changed', (ev) => {
      onEvent('case.status_changed', parseEventData((ev as MessageEvent).data));
    });

    source.onmessage = (ev) => {
      onEvent('message', parseEventData(ev.data));
    };

    source.onerror = () => {
      cleanupSource();
      scheduleReconnect();
    };
  };

  void connect();

  return () => {
    closed = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    cleanupSource();
  };
}
