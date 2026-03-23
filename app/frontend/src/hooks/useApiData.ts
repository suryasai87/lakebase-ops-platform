import { useState, useEffect, useCallback, useRef } from "react";

interface UseApiDataOptions {
  pollInterval?: number; // ms, 0 = no polling
  retries?: number;      // retry count on failure (default 2)
}

const RETRY_DELAY_MS = 2000;

export function useApiData<T>(
  url: string,
  opts: UseApiDataOptions = {}
): { data: T | null; loading: boolean; error: string | null; refetch: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const maxRetries = opts.retries ?? 2;

  const fetchData = useCallback(async () => {
    if (!url) {
      setLoading(false);
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    let lastError: string | null = null;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      if (controller.signal.aborted) return;
      try {
        const res = await fetch(url, { signal: controller.signal });
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        const json = await res.json();
        if (!controller.signal.aborted) {
          setData(json);
          setError(null);
          setLoading(false);
        }
        return;
      } catch (e: any) {
        if (e.name === "AbortError") return;
        lastError = e.message;
        if (attempt < maxRetries) {
          await new Promise((r) => setTimeout(r, RETRY_DELAY_MS));
        }
      }
    }

    if (!controller.signal.aborted) {
      setError(lastError);
      setLoading(false);
    }
  }, [url, maxRetries]);

  useEffect(() => {
    fetchData();
    let intervalId: ReturnType<typeof setInterval> | undefined;
    if (opts.pollInterval && opts.pollInterval > 0) {
      intervalId = setInterval(fetchData, opts.pollInterval);
    }
    return () => {
      abortRef.current?.abort();
      if (intervalId) clearInterval(intervalId);
    };
  }, [fetchData, opts.pollInterval]);

  return { data, loading, error, refetch: fetchData };
}
