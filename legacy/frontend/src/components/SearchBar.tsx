import { useMutation } from "@tanstack/react-query";
import { Loader2, Search, X } from "lucide-react";
import { useState } from "react";
import { fetchNlSearch } from "../api/intelligence";
import type { NlSearchResult, VesselPosition } from "../types";
import { useVesselStore } from "../store/vessels";
import { RiskBadge } from "./RiskBadge";

interface SearchBarProps {
  onClose: () => void;
}

function SearchResultCard({
  vessel,
  onSelect,
}: {
  vessel: VesselPosition;
  onSelect: (imo: number) => void;
}) {
  const hasSanctions = vessel.current_sanctions_status !== "clean";
  return (
    <li
      className="flex cursor-pointer items-start justify-between gap-2 px-3 py-2.5 transition-colors hover:bg-white/60"
      onClick={() => onSelect(vessel.imo)}
    >
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-[var(--text-primary)]">{vessel.name}</p>
        <div className="mt-0.5 flex items-center gap-2 text-xs text-[var(--text-muted)]">
          <span className="mono">IMO {vessel.imo}</span>
          {(vessel.flag_name || vessel.flag) && (
            <span>
              · {vessel.flag_emoji ? `${vessel.flag_emoji} ` : ""}
              {vessel.flag_name ?? vessel.flag}
            </span>
          )}
          {(vessel.vessel_type_label || vessel.vessel_type) && (
            <span>· {vessel.vessel_type_label ?? vessel.vessel_type}</span>
          )}
        </div>
        <div className="flex items-center gap-1.5 mt-1">
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
      {vessel.latest_composite_risk != null && (
        <RiskBadge score={vessel.latest_composite_risk} size="sm" />
      )}
    </li>
  );
}

function SpecPill({ label }: { label: string }) {
  return (
    <span className="rounded border border-teal-200 bg-teal-50 px-1.5 py-0.5 text-xs text-teal-700">
      {label}
    </span>
  );
}

function SpecSummary({ result }: { result: NlSearchResult }) {
  const { spec } = result;
  const pills: string[] = [];
  if (spec.flag_codes?.length) pills.push(`Flag: ${spec.flag_codes.join(", ")}`);
  if (spec.vessel_types?.length) pills.push(spec.vessel_types.join(", "));
  if (spec.sanctioned_only) pills.push("Sanctioned");
  if (spec.shadow_fleet_only) pills.push("Shadow fleet");
  if (spec.min_risk_score != null) pills.push(`Risk ≥ ${spec.min_risk_score}`);
  if (spec.connected_to_sanctioned_org) pills.push("Org-linked");
  if (spec.new_arrivals_only) pills.push("New arrivals");
  if (!pills.length) pills.push("All vessels");
  return (
    <div className="flex flex-wrap gap-1 border-b border-[var(--border)] px-3 py-2">
      {pills.map((p) => (
        <SpecPill key={p} label={p} />
      ))}
      {result.cached && (
        <span className="ml-auto text-xs text-[var(--text-muted)]">cached</span>
      )}
    </div>
  );
}

export function SearchBar({ onClose }: SearchBarProps) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<NlSearchResult | null>(null);
  const { setSelectedImo } = useVesselStore();

  const { mutate, isPending, error } = useMutation({
    mutationFn: (q: string) => fetchNlSearch(q),
    onSuccess: (data) => setResult(data),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) mutate(query.trim());
  }

  function handleSelect(imo: number) {
    setSelectedImo(imo);
    onClose();
  }

  return (
    <div className="search-popover glass-panel-bright absolute left-1/2 top-14 z-[650] flex w-[28rem] max-w-[calc(100vw-1rem)] -translate-x-1/2 flex-col overflow-hidden rounded-xl">
      {/* Input row */}
      <form onSubmit={handleSubmit} className="flex items-center gap-2 px-3 py-2">
        {isPending ? (
          <Loader2 size={16} className="shrink-0 animate-spin text-[var(--text-muted)]" />
        ) : (
          <Search size={16} className="shrink-0 text-[var(--text-muted)]" />
        )}
        <input
          autoFocus
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder='e.g. "sanctioned tankers from Iran with high risk"'
          className="flex-1 bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] outline-none"
          aria-label="Natural language vessel search"
        />
        <button
          type="button"
          onClick={onClose}
          className="rounded border border-[var(--border)] p-0.5 text-[var(--text-secondary)] hover:border-[var(--border-accent)] hover:bg-white"
          aria-label="Close search"
        >
          <X size={14} />
        </button>
      </form>

      {/* Error */}
      {error && (
        <p className="px-3 pb-2 text-xs text-red-700">
          {(error as Error).message || "Search failed — try again"}
        </p>
      )}

      {/* Results */}
      {result && (
        <>
          <SpecSummary result={result} />
          {result.vessels.length === 0 ? (
            <p className="px-3 py-4 text-center text-sm text-[var(--text-muted)]">No vessels matched.</p>
          ) : (
            <ul className="thin-scroll max-h-72 overflow-y-auto divide-y divide-[var(--border)]">
              {result.vessels.map((v) => (
                <SearchResultCard key={v.imo} vessel={v} onSelect={handleSelect} />
              ))}
            </ul>
          )}
          <div className="border-t border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text-muted)]">
            {result.vessels.length} result{result.vessels.length !== 1 ? "s" : ""}
          </div>
        </>
      )}
    </div>
  );
}
