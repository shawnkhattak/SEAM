import { useEffect, useRef } from "react";

interface UseSSEOptions {
  url: string;
  onEvent: (eventName: string, data: unknown) => void;
  /** Fallback polling interval in ms if SSE stays disconnected >30s. Default: 60_000 */
  fallbackIntervalMs?: number;
}

/**
 * Subscribes to a Server-Sent Events stream.
 * - Reconnects automatically with 5s back-off on disconnect.
 * - Falls back to a polling callback if SSE remains down.
 */
export function useSSE({ url, onEvent, fallbackIntervalMs = 60_000 }: UseSSEOptions): void {
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fallbackTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const connectedRef = useRef(false);

  useEffect(() => {
    let destroyed = false;

    function clearFallback() {
      if (fallbackTimer.current) {
        clearInterval(fallbackTimer.current);
        fallbackTimer.current = null;
      }
    }

    function startFallback() {
      if (fallbackTimer.current) return;
      fallbackTimer.current = setInterval(() => {
        if (!connectedRef.current) {
          onEvent("positions_updated", {});
        }
      }, fallbackIntervalMs);
    }

    function connect() {
      if (destroyed) return;
      esRef.current?.close();

      const es = new EventSource(url);
      esRef.current = es;

      es.addEventListener("connected", () => {
        connectedRef.current = true;
        clearFallback();
      });

      es.addEventListener("positions_updated", (e: MessageEvent) => {
        try {
          const parsed = JSON.parse(e.data);
          onEvent("positions_updated", parsed);
        } catch {
          onEvent("positions_updated", {});
        }
      });

      es.onerror = () => {
        connectedRef.current = false;
        es.close();
        startFallback();
        reconnectTimer.current = setTimeout(connect, 5_000);
      };
    }

    connect();

    return () => {
      destroyed = true;
      clearFallback();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      esRef.current?.close();
    };
  }, [url, onEvent, fallbackIntervalMs]);
}
