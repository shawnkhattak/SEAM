import { useMemo, useState, type CSSProperties } from "react";
import { useVesselStore } from "../store/vessels";
import type { VesselPosition } from "../types";

interface TopBarProps {
  positions: VesselPosition[];
  lastUpdated: Date | null;
  isLoading: boolean;
  onShowNews: () => void;
  onShowJournal: () => void;
  onShowArrivals: () => void;
  onShowSearch: () => void;
  vesselTypeFilter: string | null;
  onVesselTypeFilterChange: (filter: string | null) => void;
  searchQuery: string;
  onSearchQueryChange: (q: string) => void;
}

interface FilterPill {
  key: string;
  label: string;
  /** True if a special filter (shadow / sanctioned) */
  special?: "shadow" | "sanctioned";
}

const TYPE_PILLS: FilterPill[] = [
  { key: "ALL", label: "All" },
  { key: "CS", label: "CS" },
  { key: "BC", label: "BC" },
  { key: "TA", label: "TA" },
  { key: "GT", label: "GT" },
  { key: "TC", label: "TC" },
  { key: "GC", label: "GC" },
  { key: "shadow", label: "Shadow", special: "shadow" },
  { key: "sanctioned", label: "Sanctioned", special: "sanctioned" },
];

const BAR_STYLE: CSSProperties = {
  position: "fixed",
  top: 0,
  left: 0,
  right: 0,
  height: 56,
  zIndex: 30,
  background: "rgba(255, 255, 255, 0.92)",
  backdropFilter: "blur(20px)",
  WebkitBackdropFilter: "blur(20px)",
  boxShadow: "0 1px 12px rgba(13, 31, 53, 0.08)",
  borderBottom: "1px solid rgba(13, 31, 53, 0.06)",
  display: "flex",
  alignItems: "center",
  padding: "0 16px",
  gap: 16,
  fontFamily: "'DM Sans', sans-serif",
};

const LOGO_WRAP: CSSProperties = {
  display: "flex",
  alignItems: "baseline",
  gap: 8,
  paddingRight: 12,
  borderRight: "1px solid rgba(13, 31, 53, 0.08)",
  marginRight: 4,
};

const LOGO_TEXT: CSSProperties = {
  fontSize: 18,
  fontWeight: 700,
  letterSpacing: "-0.01em",
  color: "#0d1f35",
};

const LOGO_CAPTION: CSSProperties = {
  fontSize: 9,
  fontWeight: 600,
  letterSpacing: "0.18em",
  color: "#94a3b8",
  textTransform: "uppercase",
};

const PILLS_WRAP: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 4,
  flexShrink: 0,
};

function pillStyle(active: boolean, special?: "shadow" | "sanctioned"): CSSProperties {
  if (active) {
    if (special === "shadow") {
      return {
        background: "#f59e0b",
        color: "#fff",
        border: "1px solid #f59e0b",
      } as CSSProperties;
    }
    if (special === "sanctioned") {
      return {
        background: "#ef4444",
        color: "#fff",
        border: "1px solid #ef4444",
      } as CSSProperties;
    }
    return {
      background: "#0d1f35",
      color: "#fff",
      border: "1px solid #0d1f35",
    } as CSSProperties;
  }
  return {
    background: "rgba(0, 0, 0, 0.05)",
    color: "#0d1f35",
    border: "1px solid rgba(0, 0, 0, 0.08)",
  } as CSSProperties;
}

const PILL_BASE: CSSProperties = {
  fontSize: 12,
  fontWeight: 500,
  padding: "5px 10px",
  borderRadius: 8,
  cursor: "pointer",
  transition: "all 120ms ease",
  whiteSpace: "nowrap",
  fontFamily: "inherit",
};

const SEARCH_INPUT: CSSProperties = {
  flex: "0 1 220px",
  height: 32,
  padding: "0 10px",
  borderRadius: 8,
  border: "1px solid rgba(0, 0, 0, 0.08)",
  background: "rgba(0, 0, 0, 0.04)",
  fontSize: 12,
  color: "#0d1f35",
  outline: "none",
  fontFamily: "inherit",
};

const ACTION_BTN: CSSProperties = {
  ...PILL_BASE,
  background: "rgba(0, 0, 0, 0.05)",
  color: "#0d1f35",
  border: "1px solid rgba(0, 0, 0, 0.08)",
};

const LIVE_WRAP: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 6,
  fontSize: 11,
  color: "#475569",
  marginLeft: 4,
  whiteSpace: "nowrap",
};

const LIVE_DOT: CSSProperties = {
  width: 7,
  height: 7,
  borderRadius: "50%",
  background: "#22c55e",
  display: "inline-block",
};

export function TopBar({
  positions,
  lastUpdated,
  isLoading,
  onShowNews,
  onShowJournal,
  onShowArrivals,
  onShowSearch,
  vesselTypeFilter,
  onVesselTypeFilterChange,
  searchQuery,
  onSearchQueryChange,
}: TopBarProps) {
  const { filterShadowFleet, toggleShadowFleetFilter, filterSanctioned, toggleSanctionedFilter } =
    useVesselStore();

  const counts = useMemo(() => {
    const c: Record<string, number> = { ALL: positions.length, shadow: 0, sanctioned: 0 };
    for (const v of positions) {
      const t = (v.vessel_type ?? "").toUpperCase();
      if (t) c[t] = (c[t] ?? 0) + 1;
      if (v.is_shadow_fleet) c.shadow += 1;
      if (v.current_sanctions_status && v.current_sanctions_status !== "none") {
        c.sanctioned += 1;
      }
    }
    return c;
  }, [positions]);

  const [hovered, setHovered] = useState<string | null>(null);

  function isActive(p: FilterPill): boolean {
    if (p.special === "shadow") return filterShadowFleet;
    if (p.special === "sanctioned") return filterSanctioned;
    if (p.key === "ALL") return vesselTypeFilter === null;
    return vesselTypeFilter === p.key;
  }

  function handlePillClick(p: FilterPill) {
    if (p.special === "shadow") {
      toggleShadowFleetFilter();
      return;
    }
    if (p.special === "sanctioned") {
      toggleSanctionedFilter();
      return;
    }
    if (p.key === "ALL") {
      onVesselTypeFilterChange(null);
      return;
    }
    onVesselTypeFilterChange(p.key);
  }

  return (
    <div style={BAR_STYLE} className="anim-fade-in">
      {/* Logo */}
      <div style={LOGO_WRAP}>
        <span style={LOGO_TEXT}>OceansX</span>
        <span style={LOGO_CAPTION}>Singapore</span>
      </div>

      {/* Vessel type filter pills */}
      <div style={PILLS_WRAP}>
        {TYPE_PILLS.map((p) => {
          const active = isActive(p);
          const count = counts[p.key];
          return (
            <button
              key={p.key}
              type="button"
              onClick={() => handlePillClick(p)}
              onMouseEnter={() => setHovered(p.key)}
              onMouseLeave={() => setHovered(null)}
              style={{
                ...PILL_BASE,
                ...pillStyle(active, p.special),
                ...(hovered === p.key && !active
                  ? { background: "rgba(0, 0, 0, 0.08)" }
                  : {}),
              }}
              title={
                p.special === "shadow"
                  ? "Filter shadow fleet vessels"
                  : p.special === "sanctioned"
                  ? "Filter sanctioned vessels"
                  : `Filter by type ${p.label}`
              }
            >
              {p.label}
              {count != null && count > 0 && p.key !== "ALL" && (
                <span style={{ marginLeft: 5, opacity: 0.7, fontSize: 11 }}>{count}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Search input */}
      <input
        type="text"
        placeholder="Search vessel, IMO, flag…"
        value={searchQuery}
        onChange={(e) => onSearchQueryChange(e.target.value)}
        style={SEARCH_INPUT}
        aria-label="Search vessels"
      />

      <div style={{ flex: 1 }} />

      {/* Right side actions */}
      <button type="button" style={ACTION_BTN} onClick={onShowNews}>
        News
      </button>
      <button type="button" style={ACTION_BTN} onClick={onShowJournal}>
        Journal
      </button>
      <button type="button" style={ACTION_BTN} onClick={onShowArrivals}>
        Arrivals
      </button>
      <button type="button" style={ACTION_BTN} onClick={onShowSearch} title="Natural-language search">
        NL Search
      </button>

      {/* LIVE indicator */}
      <div style={LIVE_WRAP}>
        <span style={LIVE_DOT} className="live-pulse" />
        <span style={{ fontWeight: 600, color: "#0d1f35", letterSpacing: "0.05em" }}>LIVE</span>
        {isLoading ? (
          <span style={{ color: "#94a3b8" }}>loading…</span>
        ) : lastUpdated ? (
          <span style={{ color: "#94a3b8" }}>· {lastUpdated.toLocaleTimeString()}</span>
        ) : null}
      </div>
    </div>
  );
}
