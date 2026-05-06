import L from "leaflet";
import { useMemo } from "react";
import { Marker, Tooltip } from "react-leaflet";
import type { VesselPosition } from "../types";

const STATUS_COLORS: Record<string, string> = {
  arrived: "#22c55e",   // green
  departing: "#f59e0b", // amber
  incoming: "#3b82f6",  // blue
  departed: "#6b7280",  // grey
};

function makeIcon(
  heading: number,
  color: string,
  selected: boolean,
  isShadowFleet: boolean,
  isSanctioned: boolean,
): L.DivIcon {
  const size = selected ? 18 : 14;
  const arrowSvg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24"
         style="transform:rotate(${heading}deg);display:block;">
      <polygon points="12,2 20,22 12,17 4,22" fill="${color}" stroke="white" stroke-width="1.5"/>
    </svg>`;

  // Sanctioned: red ring container
  // Shadow fleet: amber dot in top-right corner
  const ringStyle = isSanctioned
    ? `border:2px solid #ef4444;border-radius:50%;box-sizing:border-box;`
    : "";

  const shadowDot = isShadowFleet
    ? `<div style="position:absolute;top:-3px;right:-3px;width:7px;height:7px;background:#f59e0b;border-radius:50%;border:1px solid #1e293b;"></div>`
    : "";

  const containerSize = size + (isSanctioned ? 8 : 0);
  const padding = isSanctioned ? 3 : 0;

  return L.divIcon({
    html: `<div style="position:relative;width:${containerSize}px;height:${containerSize}px;${ringStyle}padding:${padding}px;display:flex;align-items:center;justify-content:center;">${arrowSvg}${shadowDot}</div>`,
    className: "",
    iconSize: [containerSize, containerSize],
    iconAnchor: [containerSize / 2, containerSize / 2],
  });
}

interface VesselMarkerProps {
  vessel: VesselPosition;
  selected: boolean;
  onClick: (imo: number) => void;
}

export function VesselMarker({ vessel, selected, onClick }: VesselMarkerProps) {
  const color = STATUS_COLORS[vessel.inferred_status] ?? STATUS_COLORS.departed;
  const heading = vessel.heading_degrees ?? vessel.course_degrees ?? 0;
  const isSanctioned = vessel.current_sanctions_status === "sanctioned";
  const isShadowFleet = vessel.is_shadow_fleet;

  const icon = useMemo(
    () => makeIcon(heading, color, selected, isShadowFleet, isSanctioned),
    [heading, color, selected, isShadowFleet, isSanctioned],
  );

  return (
    <Marker
      position={[vessel.lat, vessel.lon]}
      icon={icon}
      zIndexOffset={selected ? 1000 : isSanctioned ? 500 : 0}
      eventHandlers={{ click: () => onClick(vessel.imo) }}
    >
      <Tooltip direction="top" offset={[0, -8]} opacity={0.9}>
        <span className="text-xs font-medium">{vessel.name}</span>
        {(isSanctioned || isShadowFleet) && (
          <>
            <br />
            <span className="text-xs" style={{ color: isSanctioned ? "#ef4444" : "#f59e0b" }}>
              {isSanctioned ? "⚠ Sanctioned" : ""}
              {isSanctioned && isShadowFleet ? " · " : ""}
              {isShadowFleet ? "Shadow fleet" : ""}
            </span>
          </>
        )}
        <br />
        <span className="text-xs text-slate-400">
          {vessel.speed_knots?.toFixed(1) ?? "—"} kn ·{" "}
          {vessel.flag_name
            ? `${vessel.flag_emoji ? `${vessel.flag_emoji} ` : ""}${vessel.flag_name}`
            : vessel.flag ?? "—"}
          {vessel.vessel_type_label ? ` · ${vessel.vessel_type_label}` : ""}
        </span>
      </Tooltip>
    </Marker>
  );
}
