import { Polyline, Tooltip } from "react-leaflet";
import { useQuery } from "@tanstack/react-query";
import { DateTime } from "luxon";
import { fetchVesselTrail } from "../api/vessels";
import type { TrailPoint } from "../types";

function useScrubTrail(imo: number | null, scrubOffset: number) {
  const { data: trail = [] } = useQuery<TrailPoint[]>({
    queryKey: ["trail", imo],
    queryFn: () => fetchVesselTrail(imo!),
    enabled: imo !== null,
    staleTime: 5 * 60 * 1000,
  });

  const cutoffMs = Date.now() + scrubOffset * 60 * 1000;
  const visible = trail.filter((p) => new Date(p.recorded_at).getTime() <= cutoffMs);
  return { visible, trail };
}

interface PolylineProps {
  imo: number | null;
  scrubOffset: number;
}

/** Renders the vessel trail polyline — mount INSIDE MapContainer. */
export function VesselTrailPolyline({ imo, scrubOffset }: PolylineProps) {
  const { visible } = useScrubTrail(imo, scrubOffset);

  if (imo === null || visible.length < 2) return null;

  const positions = visible.map((p) => [p.lat, p.lon] as [number, number]);
  const label =
    scrubOffset === 0
      ? "Now"
      : DateTime.now().plus({ minutes: scrubOffset }).toRelative() ?? "";

  return (
    <Polyline
      positions={positions}
      pathOptions={{ color: "#2fb8a3", weight: 2, opacity: 0.75, dashArray: "4 4" }}
    >
      <Tooltip sticky>
        {visible.length} points · {label}
      </Tooltip>
    </Polyline>
  );
}

interface ScrubberProps {
  imo: number | null;
  scrubOffset: number;
  onScrub: (offset: number) => void;
}

/** Timeline scrubber bar — mount OUTSIDE MapContainer to avoid Leaflet event capture. */
export function TimelineScrubber({ imo, scrubOffset, onScrub }: ScrubberProps) {
  const { trail } = useScrubTrail(imo, scrubOffset);

  if (imo === null || trail.length === 0) return null;

  const label =
    scrubOffset === 0
      ? "Now"
      : DateTime.now().plus({ minutes: scrubOffset }).toRelative() ?? "";

  return (
    <div className="glass-panel-bright absolute bottom-6 left-1/2 z-[1000] flex w-80 max-w-[90vw] -translate-x-1/2 items-center gap-3 rounded-full px-4 py-2">
      <span className="mono shrink-0 text-[11px] text-[var(--text-muted)]">24h</span>
      <input
        type="range"
        min={-1440}
        max={0}
        step={15}
        value={scrubOffset}
        onChange={(e) => onScrub(Number(e.target.value))}
        className="seam-range h-1 flex-1"
      />
      <span className="mono w-14 shrink-0 text-right text-[11px] text-[var(--accent-deep)]">
        {label}
      </span>
    </div>
  );
}
