import { useState, useEffect, useCallback } from "react";

interface UseApiDataOptions {
  pollInterval?: number; // ms, 0 = no polling
}

export function useApiData<T>(
  url: string,
  opts: UseApiDataOptions = {}
): { data: T | null; loading: boolean; error: string | null; refetch: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const json = await res.json();
      setData(json);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [url]);

  useEffect(() => {
    fetchData();
    if (opts.pollInterval && opts.pollInterval > 0) {
      const id = setInterval(fetchData, opts.pollInterval);
      return () => clearInterval(id);
    }
  }, [fetchData, opts.pollInterval]);

  return { data, loading, error, refetch: fetchData };
}
