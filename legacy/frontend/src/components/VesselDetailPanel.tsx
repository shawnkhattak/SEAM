import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import React from "react";
import { fetchVesselRisk } from "../api/risk";
import { fetchVesselSanctions } from "../api/sanctions";
import { fetchVesselDetail } from "../api/vessels";
import { formatUtc, relativeTime } from "../lib/timezone";
import { useTimezoneStore } from "../store/timezone";
import type { RiskScoreResponse, SanctionsMatch } from "../types";
import { RiskBadge } from "./RiskBadge";

interface VesselDetailPanelProps {
  imo: number;
  onClose: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  arrived: "At berth",
  departing: "Departing",
  incoming: "Incoming",
  departed: "Departed",
};

const STATUS_COLORS: Record<string, string> = {
  arrived: "text-teal-700",
  departing: "text-amber-700",
  incoming: "text-blue-700",
  departed: "text-slate-500",
};

const SANCTIONS_STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  clean: { label: "Clean", cls: "text-teal-700" },
  sanctioned: { label: "Sanctioned", cls: "text-red-700" },
  pending: { label: "Under review", cls: "text-amber-700" },
  prev_sanctioned: { label: "Previously sanctioned", cls: "text-orange-700" },
};

const MATCH_METHOD_LABELS: Record<string, string> = {
  imo_exact: "IMO exact",
  name_flag_fuzzy: "Name + flag",
  name_fuzzy: "Name fuzzy",
  org_link: "Org link",
};

const MATCH_STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
  auto_confirmed: { label: "Confirmed (auto)", cls: "text-red-700" },
  confirmed: { label: "Confirmed", cls: "text-red-700" },
  pending: { label: "Pending review", cls: "text-amber-700" },
  rejected: { label: "Rejected", cls: "text-slate-500" },
};

export function VesselDetailPanel({ imo, onClose }: VesselDetailPanelProps) {
  const { timezone } = useTimezoneStore();

  const { data: vessel, isLoading } = useQuery({
    queryKey: ["vessel", imo],
    queryFn: () => fetchVesselDetail(imo),
    staleTime: 60_000,
  });

  const { data: sanctions = [] } = useQuery({
    queryKey: ["vessel-sanctions", imo],
    queryFn: () => fetchVesselSanctions(imo),
    staleTime: 120_000,
    enabled: vessel !== undefined,
  });

  const { data: riskHistory = [] } = useQuery({
    queryKey: ["vessel-risk", imo],
    queryFn: () => fetchVesselRisk(imo, 1),
    staleTime: 300_000,
    enabled: vessel !== undefined,
  });
  const latestRisk: RiskScoreResponse | undefined = riskHistory[0];

  const activeSanctions = sanctions.filter(
    (m) => m.status === "auto_confirmed" || m.status === "confirmed"
  );
  const hasSanctionsAlert =
    vessel?.current_sanctions_status !== "clean" || activeSanctions.length > 0;

  return (
    <div className="vessel-detail-panel glass-panel-bright absolute bottom-0 right-0 top-11 z-[620] flex w-[22rem] max-w-[calc(100vw-1rem)] flex-col overflow-hidden rounded-none border-y-0 border-r-0 shadow-2xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
        <div className="min-w-0">
          {isLoading ? (
            <div className="h-5 w-40 animate-pulse rounded bg-slate-200" />
          ) : (
            <h2 className="truncate font-semibold text-[var(--text-primary)]">{vessel?.name}</h2>
          )}
          <p className="mono text-xs text-[var(--text-muted)]">IMO {imo}</p>
        </div>
        <button
          onClick={onClose}
          className="rounded border border-[var(--border)] p-1 text-[var(--text-secondary)] hover:border-[var(--border-accent)] hover:bg-white"
          aria-label="Close"
        >
          <X size={16} />
        </button>
      </div>

      {/* Content */}
      <div className="thin-scroll flex-1 space-y-4 overflow-y-auto p-4 text-sm">
        {isLoading && (
          <div className="space-y-2">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-4 animate-pulse rounded bg-slate-200" />
            ))}
          </div>
        )}

        {vessel && (
          <>
            {/* Compliance badges */}
            {(hasSanctionsAlert || vessel.is_shadow_fleet) && (
              <div className="detail-section-enter space-y-1">
                {vessel.current_sanctions_status !== "clean" && (
                  <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                    ⚠ Sanctions: {SANCTIONS_STATUS_CONFIG[vessel.current_sanctions_status]?.label ?? vessel.current_sanctions_status}
                  </div>
                )}
                {vessel.is_shadow_fleet && (
                  <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                    ⚑ Shadow fleet vessel
                  </div>
                )}
              </div>
            )}

            {/* Risk score */}
            {latestRisk && (
              <section className="detail-section-enter">
                <h3 className="mono mb-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
                  Risk Score
                </h3>
                <div className="space-y-2 rounded border border-[var(--border)] bg-white/55 px-3 py-2">
                  <div className="flex items-center justify-between">
                    <RiskBadge score={latestRisk.composite} size="lg" />
                    <span className="text-xs text-[var(--text-muted)]">
                      {relativeTime(latestRisk.scored_at)}
                    </span>
                  </div>
                  <div className="space-y-1 text-xs">
                    {latestRisk.sanctions_score > 0 && (
                      <RiskRow label="Sanctions" value={latestRisk.sanctions_score} />
                    )}
                    {latestRisk.shadow_fleet_score > 0 && (
                      <RiskRow label="Shadow fleet" value={latestRisk.shadow_fleet_score} />
                    )}
                    <RiskRow label="Flag MoU" value={latestRisk.flag_mou_score} />
                    <RiskRow label="Age" value={latestRisk.age_score} />
                  </div>
                </div>
              </section>
            )}

            {/* Current position */}
            {vessel.position && (
              <section className="detail-section-enter">
                <h3 className="mono mb-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
                  Current Position
                </h3>
                <div className="space-y-1">
                  <Row label="Status">
                    <span className={STATUS_COLORS[vessel.position.inferred_status]}>
                      {STATUS_LABELS[vessel.position.inferred_status] ?? vessel.position.inferred_status}
                    </span>
                  </Row>
                  <Row label="Position">
                    {vessel.position.lat.toFixed(4)}°N, {vessel.position.lon.toFixed(4)}°E
                  </Row>
                  <Row label="Speed">
                    {vessel.position.speed_knots != null
                      ? `${vessel.position.speed_knots.toFixed(1)} kn`
                      : "—"}
                  </Row>
                  <Row label="Heading">
                    {vessel.position.heading_degrees != null
                      ? `${vessel.position.heading_degrees.toFixed(0)}°`
                      : "—"}
                  </Row>
                  <Row label="As of">
                    {relativeTime(vessel.position.recorded_at)}
                  </Row>
                </div>
              </section>
            )}

            {/* Particulars */}
            <section className="detail-section-enter">
              <h3 className="mono mb-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
                Particulars
              </h3>
              <div className="space-y-1">
                <Row label="Flag">
                  {vessel.flag_name
                    ? `${vessel.flag_emoji ? `${vessel.flag_emoji} ` : ""}${vessel.flag_name}${vessel.flag ? ` (${vessel.flag})` : ""}`
                    : vessel.flag ?? "—"}
                </Row>
                <Row label="Type">{vessel.vessel_type_label ?? vessel.vessel_type ?? "—"}</Row>
                <Row label="Year built">{vessel.year_built ?? "—"}</Row>
                <Row label="GT">{vessel.gross_tonnage?.toLocaleString() ?? "—"}</Row>
                <Row label="DWT">{vessel.deadweight?.toLocaleString() ?? "—"}</Row>
                <Row label="LOA">{vessel.length_overall ? `${vessel.length_overall} m` : "—"}</Row>
                <Row label="Beam">{vessel.beam ? `${vessel.beam} m` : "—"}</Row>
                <Row label="Owner">{vessel.registered_owner ?? "Not returned by source"}</Row>
                <Row label="Operator">{vessel.operator ?? "Not returned by source"}</Row>
                <Row label="ISM Manager">{vessel.ism_manager ?? "Not returned by source"}</Row>
                <Row label="Class">{vessel.classification_society ?? "Not returned by source"}</Row>
              </div>
            </section>

            {/* Sanctions matches */}
            {sanctions.length > 0 && (
              <section className="detail-section-enter">
                <h3 className="mono mb-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
                  Sanctions Matches
                </h3>
                <div className="space-y-2">
                  {sanctions.map((match) => (
                    <SanctionsMatchCard key={match.id} match={match} />
                  ))}
                </div>
              </section>
            )}

            {/* Last seen */}
            {vessel.last_observed_at && (
              <p className="text-xs text-[var(--text-muted)]">
                Last observed: {formatUtc(vessel.last_observed_at, timezone, "yyyy-MM-dd HH:mm")}
              </p>
            )}
          </>
        )}
      </div>

      {/* Risk disclaimer */}
      <div className="border-t border-[var(--border)] px-4 py-2">
        <p className="text-xs leading-relaxed text-[var(--text-muted)]">
          Risk indicators are derived from public data sources and should not be
          relied upon for operational or commercial decisions.
        </p>
      </div>
    </div>
  );
}

function SanctionsMatchCard({ match }: { match: SanctionsMatch }) {
  const statusCfg = MATCH_STATUS_CONFIG[match.status] ?? { label: match.status, cls: "text-slate-400" };
  return (
    <div className="space-y-1 rounded border border-[var(--border)] bg-white/55 px-3 py-2 text-xs">
      {match.entity_name && (
        <p className="font-medium text-[var(--text-primary)]">{match.entity_name}</p>
      )}
      <div className="flex items-center justify-between gap-2">
        <span className="text-[var(--text-secondary)]">{MATCH_METHOD_LABELS[match.match_method] ?? match.match_method}</span>
        <span className={statusCfg.cls}>{statusCfg.label}</span>
      </div>
      {match.entity_datasets.length > 0 && (
        <p className="truncate text-[var(--text-muted)]">{match.entity_datasets.join(", ")}</p>
      )}
      {match.confidence != null && (
        <p className="text-[var(--text-muted)]">Confidence: {(match.confidence * 100).toFixed(0)}%</p>
      )}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-3 py-0.5">
      <span className="shrink-0 text-[var(--text-secondary)]">{label}</span>
      <span className="break-words text-right text-[var(--text-primary)]">{children}</span>
    </div>
  );
}

function RiskRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[var(--text-secondary)]">{label}</span>
      <div className="flex items-center gap-1.5">
        <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-[var(--accent)]"
            style={{ width: `${Math.min(100, value)}%` }}
          />
        </div>
        <span className="mono w-6 text-right text-[var(--text-primary)]">{Math.round(value)}</span>
      </div>
    </div>
  );
}
