import { useQueryClient, useQuery } from "@tanstack/react-query";
import { useCallback } from "react";
import { fetchPositions } from "../api/vessels";
import { useSSE } from "./useSSE";
import type { VesselPosition } from "../types";

export const POSITIONS_KEY = ["positions"] as const;

/**
 * Fetches vessel positions once on mount, then subscribes to SSE.
 * SSE `positions_updated` event invalidates the cache → re-fetch.
 * staleTime: Infinity means React Query never auto-refetches on its own.
 */
export function useLivePositions(): {
  positions: VesselPosition[];
  isLoading: boolean;
  lastUpdated: Date | null;
} {
  const queryClient = useQueryClient();

  const { data: positions = [], isLoading } = useQuery({
    queryKey: POSITIONS_KEY,
    queryFn: fetchPositions,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  const handleSSEEvent = useCallback(
    (_eventName: string, _data: unknown) => {
      queryClient.invalidateQueries({ queryKey: POSITIONS_KEY });
    },
    [queryClient],
  );

  useSSE({ url: "/api/sse/positions", onEvent: handleSSEEvent });

  const state = queryClient.getQueryState(POSITIONS_KEY);
  const lastUpdated = state?.dataUpdatedAt ? new Date(state.dataUpdatedAt) : null;

  return { positions, isLoading, lastUpdated };
}
