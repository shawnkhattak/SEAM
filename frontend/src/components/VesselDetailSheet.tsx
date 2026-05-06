/**
 * VesselDetailSheet — bottom sheet for vessel details.
 * Positioned absolute bottom-0, doesn't cover right-side map controls.
 * Three tabs: Summary | Provenance | Relationships
 */
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useState } from "react";
import { fetchVesselDetail, fetchVesselProvenance, fetchVesselRelationships } from "../api/vessels";
import { relativeTime, formatUtc } from "../lib/timezone";
import { useTimezoneStore } from "../store/timezone";
import type { CompanyRelationship, ParticularFact } from "../types";

interface Props {
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

const ROLE_LABELS: Record<string, string> = {
  registered_owner: "Owner",
  operator: "Operator",
  ism_manager: "ISM Manager",
  classification_society: "Class Society",
  bareboat_charterer: "Bareboat Charterer",
};

const FIELD_LABELS: Record<string, string> = {
  mmsi: "MMSI",
  call_sign: "Call Sign",
  flag: "Flag",
  vessel_type: "Type",
  year_built: "Year Built",
  gross_tonnage: "Gross Tonnage",
  deadweight: "Deadweight",
  length_overall: "LOA (m)",
  beam: "Beam (m)",
  draft_max: "Draft Max (m)",
  net_tonnage: "Net Tonnage",
};

type Tab = "summary" | "provenance" | "relationships";

export function VesselDetailSheet({ imo, onClose }: Props) {
  const [tab, setTab] = useState<Tab>("summary");
  const { timezone } = useTimezoneStore();

  const { data: vessel, isLoading } = useQuery({
    queryKey: ["vessel", imo],
    queryFn: () => fetchVesselDetail(imo),
    staleTime: 60_000,
  });

  const { data: provenance = [] } = useQuery({
    queryKey: ["vessel-provenance", imo],
    queryFn: () => fetchVesselProvenance(imo),
    staleTime: 120_000,
    enabled: tab === "provenance",
  });

  const { data: relationships = [] } = useQuery({
    queryKey: ["vessel-relationships", imo],
    queryFn: () => fetchVesselRelationships(imo),
    staleTime: 120_000,
    enabled: tab === "relationships",
  });

  // Also use inline relationships from vessel detail (available immediately)
  const inlineRels = vessel?.relationships ?? [];
  const inlineProv = vessel?.particulars ?? [];

  return (
    <div
      className="vessel-detail-sheet glass-panel-bright absolute bottom-0 left-0 right-0 z-[620] flex max-h-[50vh] flex-col overflow-hidden rounded-t-2xl shadow-2xl"
      style={{ borderBottom: "none" }}
    >
      {/* Drag handle */}
      <div className="flex justify-center pb-1 pt-2">
        <div className="h-1 w-10 rounded-full bg-[var(--border-accent)]" />
      </div>

      {/* Header */}
      <div className="flex items-center justify-between gap-3 px-4 pb-2 pt-1">
        <div className="min-w-0">
          {isLoading ? (
            <div className="h-5 w-36 animate-pulse rounded bg-slate-200" />
          ) : (
            <h2 className="truncate text-sm font-semibold text-[var(--text-primary)]">
              {vessel?.name}
              {vessel?.flag_emoji && (
                <span className="ml-1.5">{vessel.flag_emoji}</span>
              )}
            </h2>
          )}
          <p className="mono text-[11px] text-[var(--text-muted)]">IMO {imo}</p>
        </div>
        <button
          onClick={onClose}
          className="rounded border border-[var(--border)] p-1 text-[var(--text-secondary)] hover:border-[var(--border-accent)] hover:bg-white"
          aria-label="Close"
        >
          <X size={15} />
        </button>
      </div>

      {/* Alert banners */}
      {vessel && (vessel.current_sanctions_status !== "clean" || vessel.is_shadow_fleet) && (
        <div className="flex gap-2 px-4 pb-2">
          {vessel.current_sanctions_status !== "clean" && (
            <span className="rounded border border-red-200 bg-red-50 px-2 py-0.5 text-[11px] text-red-700">
              ⚠ Sanctioned
            </span>
          )}
          {vessel.is_shadow_fleet && (
            <span className="rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] text-amber-700">
              ⚑ Shadow Fleet
            </span>
          )}
        </div>
      )}

      {/* Tab bar */}
      <div className="tab-bar mx-4 mb-2">
        <button className={`tab-btn ${tab === "summary" ? "active" : ""}`} onClick={() => setTab("summary")}>
          Summary
        </button>
        <button className={`tab-btn ${tab === "provenance" ? "active" : ""}`} onClick={() => setTab("provenance")}>
          Provenance
        </button>
        <button className={`tab-btn ${tab === "relationships" ? "active" : ""}`} onClick={() => setTab("relationships")}>
          Relationships
        </button>
      </div>

      {/* Content */}
      <div className="thin-scroll flex-1 overflow-y-auto px-4 pb-4 text-sm">
        {tab === "summary" && (
          <SummaryTab vessel={vessel} isLoading={isLoading} timezone={timezone} />
        )}
        {tab === "provenance" && (
          <ProvenanceTab facts={provenance.length > 0 ? provenance : inlineProv} timezone={timezone} />
        )}
        {tab === "relationships" && (
          <RelationshipsTab rels={relationships.length > 0 ? relationships : inlineRels} />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Summary tab
// ---------------------------------------------------------------------------

function SummaryTab({
  vessel,
  isLoading,
  timezone,
}: {
  vessel: ReturnType<typeof useQuery<Awaited<ReturnType<typeof fetchVesselDetail>>>>["data"];
  isLoading: boolean;
  timezone: string;
}) {
  if (isLoading) {
    return (
      <div className="space-y-2 pt-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-4 animate-pulse rounded bg-slate-200" />
        ))}
      </div>
    );
  }
  if (!vessel) return null;

  const pos = vessel.position;

  // Get latest company names from inline relationships
  const ownerRel = vessel.relationships.find((r) => r.role === "registered_owner");
  const opRel = vessel.relationships.find((r) => r.role === "operator");
  const ismRel = vessel.relationships.find((r) => r.role === "ism_manager");
  const classRel = vessel.relationships.find((r) => r.role === "classification_society");

  // Get scalar particulars from inline provenance
  const prov = Object.fromEntries(vessel.particulars.map((f) => [f.field_name, f.field_value]));

  return (
    <div className="space-y-3 pt-1">
      {/* Current position */}
      {pos && (
        <section>
          <SectionHeader>Current Position</SectionHeader>
          <div className="space-y-0.5">
            <Row label="Status">
              <span className={STATUS_COLORS[pos.inferred_status]}>
                {STATUS_LABELS[pos.inferred_status] ?? pos.inferred_status}
              </span>
            </Row>
            <Row label="Coordinates">{pos.lat.toFixed(4)}°N, {pos.lon.toFixed(4)}°E</Row>
            <Row label="Speed">{pos.speed_knots != null ? `${pos.speed_knots.toFixed(1)} kn` : "—"}</Row>
            <Row label="Heading">{pos.heading_degrees != null ? `${pos.heading_degrees.toFixed(0)}°` : "—"}</Row>
            <Row label="As of">{relativeTime(pos.recorded_at)}</Row>
          </div>
        </section>
      )}

      {/* Particulars */}
      <section>
        <SectionHeader>Particulars</SectionHeader>
        <div className="space-y-0.5">
          <Row label="Flag">
            {vessel.flag_name
              ? `${vessel.flag_emoji ? `${vessel.flag_emoji} ` : ""}${vessel.flag_name}`
              : vessel.flag ?? "—"}
          </Row>
          <Row label="Type">{vessel.vessel_type_label ?? vessel.vessel_type ?? "—"}</Row>
          <Row label="Year built">{prov.year_built ?? vessel.year_built ?? "—"}</Row>
          <Row label="GT">{vessel.gross_tonnage?.toLocaleString() ?? "—"}</Row>
          <Row label="DWT">{vessel.deadweight?.toLocaleString() ?? "—"}</Row>
          <Row label="LOA">{vessel.length_overall ? `${vessel.length_overall} m` : "—"}</Row>
          <Row label="Beam">{vessel.beam ? `${vessel.beam} m` : "—"}</Row>
        </div>
      </section>

      {/* Ownership */}
      {(ownerRel ?? opRel ?? ismRel ?? classRel) && (
        <section>
          <SectionHeader>Ownership</SectionHeader>
          <div className="space-y-0.5">
            {ownerRel && <Row label="Owner">{ownerRel.company_name}</Row>}
            {opRel && <Row label="Operator">{opRel.company_name}</Row>}
            {ismRel && <Row label="ISM Manager">{ismRel.company_name}</Row>}
            {classRel && <Row label="Class">{classRel.company_name}</Row>}
          </div>
        </section>
      )}

      {/* Timestamps */}
      {vessel.last_observed_at && (
        <p className="text-[11px] text-[var(--text-muted)]">
          Last observed:{" "}
          {formatUtc(vessel.last_observed_at, timezone as any, "yyyy-MM-dd HH:mm")}
          {vessel.last_enriched_at && (
            <> · Enriched {relativeTime(vessel.last_enriched_at)}</>
          )}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Provenance tab
// ---------------------------------------------------------------------------

function ProvenanceTab({ facts, timezone }: { facts: ParticularFact[]; timezone: string }) {
  if (facts.length === 0) {
    return (
      <p className="pt-4 text-center text-xs text-[var(--text-muted)]">
        No provenance data yet — vessel is queued for enrichment.
      </p>
    );
  }

  return (
    <div className="space-y-2 pt-1">
      {facts.map((f, i) => (
        <div
          key={`${f.field_name}-${i}`}
          className="rounded border border-[var(--border)] bg-white/55 px-3 py-2 text-xs"
        >
          <div className="flex items-start justify-between gap-2">
            <span className="font-medium text-[var(--text-primary)]">
              {FIELD_LABELS[f.field_name] ?? f.field_name}
            </span>
            <span className="text-right text-[var(--text-primary)]">
              {f.field_value ?? <em className="text-[var(--text-muted)]">null</em>}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[var(--text-muted)]">
            {f.source && <span>Source: {f.source}</span>}
            {f.fetch_time && (
              <span>Fetched: {formatUtc(f.fetch_time, timezone as any, "yyyy-MM-dd HH:mm")}</span>
            )}
            {f.confidence != null && <span>Confidence: {(f.confidence * 100).toFixed(0)}%</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Relationships tab
// ---------------------------------------------------------------------------

function RelationshipsTab({ rels }: { rels: CompanyRelationship[] }) {
  if (rels.length === 0) {
    return (
      <p className="pt-4 text-center text-xs text-[var(--text-muted)]">
        No company relationships on record.
      </p>
    );
  }

  const byRole = rels.reduce<Record<string, CompanyRelationship[]>>((acc, r) => {
    (acc[r.role] ??= []).push(r);
    return acc;
  }, {});

  return (
    <div className="space-y-3 pt-1">
      {Object.entries(byRole).map(([role, items]) => (
        <section key={role}>
          <SectionHeader>{ROLE_LABELS[role] ?? role}</SectionHeader>
          <div className="space-y-1.5">
            {items.map((rel, i) => (
              <div
                key={i}
                className="rounded border border-[var(--border)] bg-white/55 px-3 py-2 text-xs"
              >
                <p className="font-medium text-[var(--text-primary)]">{rel.company_name}</p>
                <div className="mt-0.5 flex flex-wrap gap-x-3 text-[var(--text-muted)]">
                  {rel.source && <span>{rel.source}</span>}
                  {rel.confidence != null && (
                    <span>{(rel.confidence * 100).toFixed(0)}% confidence</span>
                  )}
                  {rel.valid_to && <span className="text-amber-600">Closed</span>}
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared sub-components
// ---------------------------------------------------------------------------

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mono mb-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
      {children}
    </h3>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[6rem_minmax(0,1fr)] gap-2 py-0.5 text-xs">
      <span className="shrink-0 text-[var(--text-secondary)]">{label}</span>
      <span className="break-words text-right text-[var(--text-primary)]">{children}</span>
    </div>
  );
}
