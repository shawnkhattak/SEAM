/**
 * LiveMap — full-screen Leaflet map with vessel markers and controls.
 *
 * Key differences from legacy:
 *  - VesselDetailSheet (bottom sheet) replaces VesselDetailPanel (right drawer)
 *  - Journal button removed from toolbar (moved to /admin)
 *  - SEAM branding throughout
 */
import { useEffect, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  Database,
  Layers,
  Newspaper,
  Search,
  Ship,
  ShieldAlert,
} from "lucide-react";
import { MapContainer, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { useLivePositions } from "../lib/useLivePositions";
import type { VesselPosition } from "../types";
import { useVesselStore } from "../store/vessels";
import { VesselDetailSheet } from "./VesselDetailSheet";
import { VesselMarker } from "./VesselMarker";
import { GeoLayersRenderer, GeoLayerPanel } from "./GeospatialOverlay";
import { VesselTrailPolyline, TimelineScrubber } from "./TimelineBar";

const SG_CENTER: [number, number] = [1.265, 103.82];
const DEFAULT_ZOOM = 11;

function visiblePositions(
  positions: VesselPosition[],
  shadowFleetOnly: boolean,
  riskThreshold: number,
): VesselPosition[] {
  let result = positions;
  if (shadowFleetOnly) result = result.filter((v) => v.is_shadow_fleet);
  if (riskThreshold > 0)
    result = result.filter(
      (v) => v.latest_composite_risk != null && v.latest_composite_risk >= riskThreshold,
    );
  return result;
}

function SeamMark({ size = 30 }: { size?: number }) {
  const id = `seam-mark-${size}`;
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" className="shrink-0" aria-hidden="true">
      <defs>
        <linearGradient id={`${id}-grad`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#3ecdb5" />
          <stop offset="100%" stopColor="#1f8a7a" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="38" height="38" rx="11" fill="rgba(47,184,163,0.12)" stroke="rgba(47,184,163,0.22)" />
      <path d="M5 26 Q 14 18, 20 22 T 35 22" fill="none" stroke="rgba(47,184,163,0.30)" strokeWidth="2" strokeLinecap="round" />
      <path d="M5 20 Q 14 12, 20 16 T 35 16" fill="none" stroke={`url(#${id}-grad)`} strokeWidth="2.2" strokeLinecap="round" strokeDasharray="2.2 2.2" />
      <circle cx="5" cy="20" r="2.6" fill="#fafbfc" stroke={`url(#${id}-grad)`} strokeWidth="1.8" />
      <circle cx="35" cy="16" r="2.6" fill={`url(#${id}-grad)`} />
    </svg>
  );
}

interface ToolbarButtonProps {
  active?: boolean;
  tone?: "ocean" | "amber" | "red";
  icon: ReactNode;
  label: string;
  title: string;
  onClick: () => void;
}

function ToolbarButton({ active, tone = "ocean", icon, label, title, onClick }: ToolbarButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`toolbar-btn ${active ? `active-${tone}` : ""}`}
      aria-label={title}
      title={title}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

export function LiveMap() {
  const { positions, isLoading, lastUpdated } = useLivePositions();
  const { selectedImo, setSelectedImo, riskThreshold, setRiskThreshold } = useVesselStore();

  const [showGeoLayers, setShowGeoLayers] = useState(false);
  const [enabledLayers, setEnabledLayers] = useState<Set<string>>(new Set());
  const [showNews, setShowNews] = useState(false);
  const [showArrivals, setShowArrivals] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [shadowFleetOnly, setShadowFleetOnly] = useState(false);
  const [showRiskSlider, setShowRiskSlider] = useState(false);
  const [scrubOffset, setScrubOffset] = useState(0);

  function toggleLayer(name: string) {
    setEnabledLayers((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  useEffect(() => {
    // Nothing to reset on vessel change — sheet stays open
  }, [selectedImo]);

  const visible = visiblePositions(positions, shadowFleetOnly, riskThreshold);
  const riskActive = riskThreshold > 0;
  const lastUpdateLabel = lastUpdated?.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }) ?? "waiting";

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-[var(--bg-canvas)]">
      {/* Map */}
      <MapContainer center={SG_CENTER} zoom={DEFAULT_ZOOM} className="h-full w-full" zoomControl={true}>
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          maxZoom={18}
        />
        {visible.map((vessel) => (
          <VesselMarker
            key={vessel.imo}
            vessel={vessel}
            selected={vessel.imo === selectedImo}
            onClick={setSelectedImo}
          />
        ))}
        <GeoLayersRenderer enabled={enabledLayers} />
        <VesselTrailPolyline imo={selectedImo} scrubOffset={scrubOffset} />
      </MapContainer>

      {/* Header bar */}
      <header className="glass-panel-bright absolute left-0 right-0 top-0 z-[700] flex h-11 items-center gap-3 rounded-none border-x-0 border-t-0 px-4">
        <div className="flex shrink-0 items-center gap-3">
          <SeamMark size={30} />
          <div>
            <div className="text-lg font-extrabold leading-none tracking-normal text-[var(--text-primary)]">
              SEAM
            </div>
            <div className="mono mt-0.5 text-[9px] tracking-[0.08em] text-[var(--text-secondary)]">
              Singapore Entity Analytics
            </div>
          </div>
        </div>
        <div className="h-6 w-px shrink-0 bg-[var(--border)]" />
        <div className="flex min-w-0 items-center gap-2">
          <span className="live-dot shrink-0" />
          <span className="mono text-[11px] text-[var(--text-secondary)]">
            <span className="font-semibold text-[var(--text-primary)]">{positions.length}</span>{" "}
            vessels
          </span>
          <span className="mono hidden text-[10px] text-[var(--text-muted)] sm:inline">
            · updated {lastUpdateLabel}
          </span>
        </div>
        <div className="flex-1" />
        <div className="hidden items-center gap-3 md:flex">
          {["OpenSanctions", "Open-Meteo", "MPA Singapore"].map((source) => (
            <span key={source} className="text-[10px] text-[var(--text-muted)]">
              {source}
            </span>
          ))}
          <div className="h-4 w-px bg-[var(--border)]" />
          <a
            href="/admin"
            className="flex items-center gap-1.5 rounded-md border border-[var(--border)] px-2 py-1 text-[11px] text-[var(--text-muted)] transition hover:border-[var(--border-accent)] hover:text-[var(--text-secondary)]"
          >
            <Database size={12} />
            Admin
          </a>
        </div>
      </header>

      {/* Status pill */}
      <div className="glass-panel absolute left-3 top-14 z-[500] flex items-center gap-2 rounded-full px-3 py-1.5">
        {isLoading ? (
          <span className="mono animate-pulse text-[11px] text-[var(--text-secondary)]">
            Loading vessels…
          </span>
        ) : (
          <>
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{
                backgroundColor: shadowFleetOnly
                  ? "var(--amber)"
                  : riskActive
                  ? "var(--red)"
                  : "var(--green)",
                boxShadow: "0 0 6px currentColor",
              }}
            />
            <span className="mono text-[11px] text-[var(--text-secondary)]">
              {shadowFleetOnly
                ? `${visible.length} shadow fleet`
                : riskActive
                ? `${visible.length} risk ≥ ${riskThreshold}`
                : `${positions.length} vessels`}
            </span>
            <span className="mono text-[10px] text-[var(--text-muted)]">· {lastUpdateLabel}</span>
          </>
        )}
      </div>

      {/* Right toolbar — no Journal button (moved to /admin) */}
      <div className="absolute right-3 top-14 z-[500] flex flex-col gap-1">
        <ToolbarButton
          active={showGeoLayers}
          icon={<Layers size={13} />}
          label="Layers"
          title="Toggle geospatial layers"
          onClick={() => setShowGeoLayers((v) => !v)}
        />
        <ToolbarButton
          active={showNews}
          icon={<Newspaper size={13} />}
          label="News"
          title="Toggle news drawer"
          onClick={() => {
            setShowNews((v) => !v);
            setShowArrivals(false);
            setShowSearch(false);
          }}
        />
        <ToolbarButton
          active={showArrivals}
          icon={<Ship size={13} />}
          label="Arrivals"
          title="Show vessels that arrived in the last 24 hours"
          onClick={() => {
            setShowArrivals((v) => !v);
            setShowNews(false);
            setShowSearch(false);
          }}
        />
        <ToolbarButton
          active={shadowFleetOnly}
          tone="amber"
          icon={<AlertTriangle size={13} />}
          label="Shadow"
          title="Show only shadow fleet vessels"
          onClick={() => setShadowFleetOnly((v) => !v)}
        />
        <ToolbarButton
          active={riskActive}
          tone="red"
          icon={<ShieldAlert size={13} />}
          label={riskActive ? `Risk ≥${riskThreshold}` : "Risk"}
          title="Filter by minimum risk score"
          onClick={() => setShowRiskSlider((v) => !v)}
        />
        <ToolbarButton
          active={showSearch}
          icon={<Search size={13} />}
          label="Search"
          title="Search vessels with natural language"
          onClick={() => {
            setShowSearch((v) => !v);
            setShowNews(false);
            setShowArrivals(false);
          }}
        />
      </div>

      {/* Risk slider popover */}
      {showRiskSlider && (
        <div className="menu-popover glass-panel absolute right-28 top-[10.5rem] z-[500] w-44 space-y-1 px-3 py-2">
          <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
            <span className="mono text-[10px] uppercase tracking-[0.06em] text-[var(--text-muted)]">
              Min risk score
            </span>
            <span className="mono font-semibold text-[var(--text-primary)]">{riskThreshold}</span>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={riskThreshold}
            onChange={(e) => setRiskThreshold(Number(e.target.value))}
            className="seam-range w-full"
            aria-label="Risk score threshold"
          />
          <div className="flex justify-between text-[10px] text-[var(--text-muted)]">
            <span>0 (all)</span>
            <span>100</span>
          </div>
          {riskActive && (
            <button
              onClick={() => setRiskThreshold(0)}
              className="w-full pt-0.5 text-center text-[11px] text-[var(--accent-deep)] hover:text-[var(--text-primary)]"
            >
              Clear filter
            </button>
          )}
        </div>
      )}

      {/* Geo layer toggle panel */}
      {showGeoLayers && (
        <GeoLayerPanel
          enabled={enabledLayers}
          onToggle={toggleLayer}
          onClose={() => setShowGeoLayers(false)}
        />
      )}

      {/* Timeline scrubber */}
      <TimelineScrubber
        imo={selectedImo}
        scrubOffset={scrubOffset}
        onScrub={setScrubOffset}
      />

      {/* Vessel detail — bottom sheet (doesn't cover right controls) */}
      {selectedImo !== null && (
        <VesselDetailSheet imo={selectedImo} onClose={() => setSelectedImo(null)} />
      )}
    </div>
  );
}
