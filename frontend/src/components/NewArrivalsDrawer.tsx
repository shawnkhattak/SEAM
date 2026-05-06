import { useQuery } from "@tanstack/react-query";
import { Ship, X } from "lucide-react";
import { fetchNewArrivals } from "../api/intelligence";
import type { VesselDetail } from "../types";
import { useVesselStore } from "../store/vessels";

interface NewArrivalsDrawerProps {
  onClose: () => void;
}

function relativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function ArrivalCard({
  vessel,
  onSelect,
}: {
  vessel: VesselDetail;
  onSelect: (imo: number) => void;
}) {
  const hasSanctions = vessel.current_sanctions_status !== "clean";
  return (
    <li
      className="cursor-pointer px-4 py-3 transition-colors hover:bg-white/60"
      onClick={() => onSelect(vessel.imo)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-[var(--text-primary)]">{vessel.name}</p>
          <p className="mono mt-0.5 text-xs text-[var(--text-muted)]">IMO {vessel.imo}</p>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          {vessel.is_shadow_fleet && (
            <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-xs text-amber-700">
              Shadow
            </span>
          )}
          {hasSanctions && (
            <span className="rounded border border-red-200 bg-red-50 px-1.5 py-0.5 text-xs text-red-700">
              Sanctioned
            </span>
          )}
        </div>
      </div>
      <div className="mt-1 flex items-center gap-2 text-xs text-[var(--text-muted)]">
        {(vessel.flag_name || vessel.flag) && (
          <span>
            {vessel.flag_emoji ? `${vessel.flag_emoji} ` : ""}
            {vessel.flag_name ?? vessel.flag}
          </span>
        )}
        {(vessel.vessel_type_label || vessel.vessel_type) && (
          <span>· {vessel.vessel_type_label ?? vessel.vessel_type}</span>
        )}
        {vessel.first_observed_at && (
          <span className="ml-auto">{relativeTime(vessel.first_observed_at)}</span>
        )}
      </div>
    </li>
  );
}

export function NewArrivalsDrawer({ onClose }: NewArrivalsDrawerProps) {
  const { setSelectedImo } = useVesselStore();

  const { data: vessels = [], isLoading } = useQuery({
    queryKey: ["new-arrivals"],
    queryFn: () => fetchNewArrivals(24),
    staleTime: 120_000,
    refetchInterval: 300_000,
  });

  return (
    <div className="left-drawer-panel glass-panel-bright absolute bottom-0 left-0 top-11 z-[600] flex w-80 max-w-[calc(100vw-1rem)] flex-col overflow-hidden rounded-none border-y-0 border-l-0 shadow-2xl">
      <div className="flex shrink-0 items-center justify-between border-b border-[var(--border)] px-4 py-3">
        <div className="flex items-center gap-2">
          <Ship size={14} className="text-[var(--accent-deep)]" />
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">New Arrivals</h2>
        </div>
        <button
          onClick={onClose}
          className="rounded border border-[var(--border)] p-1 text-[var(--text-secondary)] transition-colors hover:border-[var(--border-accent)] hover:bg-white"
          aria-label="Close new arrivals drawer"
        >
          <X size={16} />
        </button>
      </div>
      <p className="shrink-0 border-b border-[var(--border)] px-4 py-1.5 text-xs text-[var(--text-muted)]">
        Vessels first observed in the last 24 hours
      </p>

      <div className="thin-scroll flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-4 space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="space-y-2 animate-pulse">
                <div className="h-4 w-2/3 rounded bg-slate-200" />
                <div className="h-3 w-1/3 rounded bg-slate-100" />
              </div>
            ))}
          </div>
        ) : vessels.length === 0 ? (
          <div className="p-6 text-center text-sm text-[var(--text-muted)]">
            No new arrivals in the last 24 hours.
          </div>
        ) : (
          <ul className="divide-y divide-[var(--border)]">
            {vessels.map((v) => (
              <ArrivalCard key={v.imo} vessel={v} onSelect={setSelectedImo} />
            ))}
          </ul>
        )}
      </div>

      <div className="shrink-0 border-t border-[var(--border)] px-4 py-2 text-xs text-[var(--text-muted)]">
        {vessels.length} vessel{vessels.length !== 1 ? "s" : ""} · refreshes every 5 min
      </div>
    </div>
  );
}
