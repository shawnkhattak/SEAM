import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { fetchVesselDetail, fetchVesselProvenance, fetchVesselRelationships } from "../api/vessels";
import { relativeTime, formatUtc } from "../lib/timezone";
import { useTimezoneStore } from "../store/timezone";
import type { ParticularFact, CompanyRelationship } from "../types";

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

export function VesselInspector() {
  const { imo: imoParam } = useParams<{ imo: string }>();
  const imo = Number(imoParam);
  const navigate = useNavigate();
  const { timezone } = useTimezoneStore();

  const { data: vessel, isLoading } = useQuery({
    queryKey: ["vessel", imo],
    queryFn: () => fetchVesselDetail(imo),
    staleTime: 60_000,
    enabled: !isNaN(imo),
  });

  const { data: provenance = [] } = useQuery({
    queryKey: ["vessel-provenance", imo],
    queryFn: () => fetchVesselProvenance(imo),
    staleTime: 120_000,
    enabled: !isNaN(imo),
  });

  const { data: relationships = [] } = useQuery({
    queryKey: ["vessel-relationships", imo],
    queryFn: () => fetchVesselRelationships(imo),
    staleTime: 120_000,
    enabled: !isNaN(imo),
  });

  const inlineRels = vessel?.relationships ?? [];
  const inlineProv = vessel?.particulars ?? [];
  const allRels = relationships.length > 0 ? relationships : inlineRels;
  const allProv = provenance.length > 0 ? provenance : inlineProv;

  const byRole = allRels.reduce<Record<string, CompanyRelationship[]>>((acc, r) => {
    (acc[r.role] ??= []).push(r);
    return acc;
  }, {});

  return (
    <div className="min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)]">
      {/* Header */}
      <header className="glass-panel-bright sticky top-0 z-10 flex h-12 items-center gap-3 border-x-0 border-t-0 px-4">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 rounded-md border border-[var(--border)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] transition hover:border-[var(--border-accent)] hover:text-[var(--text-primary)]"
        >
          <ArrowLeft size={13} />
          Back
        </button>
        <div className="h-5 w-px bg-[var(--border)]" />
        {isLoading ? (
          <div className="h-4 w-48 animate-pulse rounded bg-slate-200" />
        ) : (
          <h1 className="text-sm font-semibold text-[var(--text-primary)]">
            {vessel?.name ?? `IMO ${imo}`}
            {vessel?.flag_emoji && <span className="ml-1.5">{vessel.flag_emoji}</span>}
          </h1>
        )}
        <span className="mono text-[11px] text-[var(--text-muted)]">IMO {imo}</span>
        <div className="flex-1" />
        <a
          href="/"
          className="flex items-center gap-1.5 text-[11px] text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
        >
          <ExternalLink size={11} />
          Map
        </a>
      </header>

      <div className="mx-auto max-w-5xl px-4 py-6">
        {/* Alert banners */}
        {vessel && (vessel.current_sanctions_status !== "clean" || vessel.is_shadow_fleet) && (
          <div className="mb-5 flex flex-wrap gap-2">
            {vessel.current_sanctions_status !== "clean" && (
              <span className="rounded border border-red-200 bg-red-50 px-3 py-1.5 text-sm text-red-700">
                ⚠ Sanctioned
              </span>
            )}
            {vessel.is_shadow_fleet && (
              <span className="rounded border border-amber-200 bg-amber-50 px-3 py-1.5 text-sm text-amber-700">
                ⚑ Shadow Fleet vessel
              </span>
            )}
          </div>
        )}

        <div className="grid gap-5 lg:grid-cols-[1fr_1.4fr]">
          {/* Left column */}
          <div className="space-y-4">
            {/* Current position */}
            {vessel?.position && (
              <Card title="Current Position">
                <Row label="Status">
                  <span className={STATUS_COLORS[vessel.position.inferred_status]}>
                    {STATUS_LABELS[vessel.position.inferred_status] ?? vessel.position.inferred_status}
                  </span>
                </Row>
                <Row label="Coordinates">
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
                <Row label="As of">{relativeTime(vessel.position.recorded_at)}</Row>
              </Card>
            )}

            {/* Particulars */}
            <Card title="Particulars">
              {isLoading ? (
                <div className="space-y-1.5">
                  {Array.from({ length: 7 }).map((_, i) => (
                    <div key={i} className="h-4 animate-pulse rounded bg-slate-200" />
                  ))}
                </div>
              ) : vessel ? (
                <>
                  <Row label="Flag">
                    {vessel.flag_name
                      ? `${vessel.flag_emoji ? `${vessel.flag_emoji} ` : ""}${vessel.flag_name}`
                      : vessel.flag ?? "—"}
                  </Row>
                  <Row label="Type">{vessel.vessel_type_label ?? vessel.vessel_type ?? "—"}</Row>
                  <Row label="Year built">{vessel.year_built ?? "—"}</Row>
                  <Row label="GT">{vessel.gross_tonnage?.toLocaleString() ?? "—"}</Row>
                  <Row label="DWT">{vessel.deadweight?.toLocaleString() ?? "—"}</Row>
                  <Row label="LOA">{vessel.length_overall ? `${vessel.length_overall} m` : "—"}</Row>
                  <Row label="Beam">{vessel.beam ? `${vessel.beam} m` : "—"}</Row>
                </>
              ) : null}
            </Card>

            {/* Timestamps */}
            {vessel?.last_observed_at && (
              <p className="text-xs text-[var(--text-muted)]">
                Last observed:{" "}
                {formatUtc(vessel.last_observed_at, timezone as any, "yyyy-MM-dd HH:mm")}
                {vessel.last_enriched_at && (
                  <> · Enriched {relativeTime(vessel.last_enriched_at)}</>
                )}
              </p>
            )}
          </div>

          {/* Right column */}
          <div className="space-y-4">
            {/* Relationships */}
            {(allRels.length > 0 || isLoading) && (
              <Card title="Company Relationships">
                {isLoading ? (
                  <div className="space-y-1.5">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <div key={i} className="h-4 animate-pulse rounded bg-slate-200" />
                    ))}
                  </div>
                ) : (
                  <div className="space-y-3">
                    {Object.entries(byRole).map(([role, items]) => (
                      <div key={role}>
                        <SectionHeader>{ROLE_LABELS[role] ?? role}</SectionHeader>
                        <div className="space-y-1.5">
                          {items.map((rel, i) => (
                            <div
                              key={i}
                              className="rounded border border-[var(--border)] bg-white/55 px-3 py-2 text-xs"
                            >
                              <p className="font-medium text-[var(--text-primary)]">
                                {rel.company_name}
                              </p>
                              <div className="mt-0.5 flex flex-wrap gap-x-3 text-[var(--text-muted)]">
                                {rel.source && <span>{rel.source}</span>}
                                {rel.confidence != null && (
                                  <span>{(rel.confidence * 100).toFixed(0)}% confidence</span>
                                )}
                                {rel.valid_to && (
                                  <span className="text-amber-600">Closed</span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            )}

            {/* Provenance */}
            <Card title="Field Provenance">
              {allProv.length === 0 ? (
                <p className="py-2 text-xs text-[var(--text-muted)]">
                  No provenance data yet — vessel is queued for enrichment.
                </p>
              ) : (
                <div className="space-y-2">
                  {allProv.map((f, i) => (
                    <ProvenanceRow key={`${f.field_name}-${i}`} fact={f} timezone={timezone} />
                  ))}
                </div>
              )}
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}

function ProvenanceRow({ fact: f, timezone }: { fact: ParticularFact; timezone: string }) {
  return (
    <div className="rounded border border-[var(--border)] bg-white/55 px-3 py-2 text-xs">
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
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="glass-panel rounded-xl border border-[var(--border)] bg-white/60 px-4 py-4 shadow-sm">
      <SectionHeader>{title}</SectionHeader>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mono text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
      {children}
    </h3>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[7rem_minmax(0,1fr)] gap-2 py-0.5 text-xs">
      <span className="text-[var(--text-secondary)]">{label}</span>
      <span className="break-words text-right text-[var(--text-primary)]">{children}</span>
    </div>
  );
}
