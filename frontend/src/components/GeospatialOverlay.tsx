import { GeoJSON } from "react-leaflet";
import { useQuery } from "@tanstack/react-query";
import { fetchGeoLayer, fetchGeoLayerNames } from "../api/vessels";
import type { GeoJsonFeatureCollection } from "../types";

const LAYER_COLORS: Record<string, string> = {
  coastline_a: "#334155",
  coastline_l: "#475569",
  dangers_a: "#ef4444",
  dangers_l: "#f97316",
  dangers_p: "#dc2626",
  aids_to_navigation_p: "#facc15",
  ports_and_services_a: "#22c55e",
  ports_and_services_l: "#4ade80",
  ports_and_services_p: "#86efac",
  offshore_installations_a: "#f97316",
  offshore_installations_l: "#fb923c",
};

const LAYER_LABELS: Record<string, string> = {
  coastline_a: "Coastline (area)",
  coastline_l: "Coastline (line)",
  dangers_a: "Dangers (area)",
  dangers_l: "Dangers (line)",
  dangers_p: "Dangers (point)",
  aids_to_navigation_p: "Aids to Navigation",
  ports_and_services_a: "Ports & Services (area)",
  ports_and_services_l: "Ports & Services (line)",
  ports_and_services_p: "Ports & Services (point)",
  offshore_installations_a: "Offshore (area)",
  offshore_installations_l: "Offshore (line)",
};

function GeoLayer({ name, color }: { name: string; color: string }) {
  const { data } = useQuery<GeoJsonFeatureCollection>({
    queryKey: ["geo", name],
    queryFn: () => fetchGeoLayer(name),
    staleTime: 24 * 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
  });

  if (!data) return null;

  return (
    <GeoJSON
      key={name}
      data={data as never}
      style={() => ({
        color,
        weight: 1.5,
        opacity: 0.8,
        fillOpacity: 0.15,
        fillColor: color,
      })}
      pointToLayer={(_feature, latlng) => {
        const L = (window as never as { L: typeof import("leaflet") }).L;
        return L.circleMarker(latlng, {
          radius: 4,
          color,
          fillColor: color,
          fillOpacity: 0.8,
          weight: 1,
        });
      }}
    />
  );
}

/** Renders active GeoJSON layers — mount INSIDE MapContainer. */
export function GeoLayersRenderer({ enabled }: { enabled: Set<string> }) {
  return (
    <>
      {[...enabled].map((name) => (
        <GeoLayer key={name} name={name} color={LAYER_COLORS[name] ?? "#94a3b8"} />
      ))}
    </>
  );
}

interface PanelProps {
  enabled: Set<string>;
  onToggle: (name: string) => void;
  onClose: () => void;
}

/** Toggle checkbox panel — mount OUTSIDE MapContainer to avoid Leaflet event capture. */
export function GeoLayerPanel({ enabled, onToggle, onClose }: PanelProps) {
  const { data: layerNames = [] } = useQuery<string[]>({
    queryKey: ["geo", "layers"],
    queryFn: fetchGeoLayerNames,
    staleTime: Infinity,
  });

  return (
    <div className="menu-popover glass-panel absolute right-28 top-14 z-[1000] w-56 text-xs text-[var(--text-secondary)]">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-3 py-2">
        <span className="mono text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
          Geo Layers
        </span>
        <button
          onClick={onClose}
          className="leading-none text-[var(--text-muted)] hover:text-[var(--text-primary)]"
        >
          ✕
        </button>
      </div>
      <div className="thin-scroll max-h-64 overflow-y-auto p-1">
        {layerNames.map((name) => (
          <label
            key={name}
            className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 hover:bg-white/60"
          >
            <input
              type="checkbox"
              checked={enabled.has(name)}
              onChange={() => onToggle(name)}
              className="accent-[var(--accent)]"
            />
            <span
              className="h-2 w-2 shrink-0 rounded-full"
              style={{ backgroundColor: LAYER_COLORS[name] ?? "#94a3b8" }}
            />
            <span className="truncate">{LAYER_LABELS[name] ?? name}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
