import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  fetchNewsEntities,
  fetchRiskHistogram,
  fetchSanctionsOverview,
  fetchTopRisk,
  fetchVesselTypes,
} from "../../api/admin";

const OCEAN_BLUE = "#2fb8a3";
const RED = "#d94f4f";
const AMBER = "#d68b3a";
const BLUE = "#5b8def";
const GRID = "rgba(38,52,68,0.12)";
const TICK = "#8a93a3";
const TOOLTIP = {
  background: "rgba(255,255,255,0.96)",
  border: "1px solid rgba(38,52,68,0.14)",
  borderRadius: 8,
  boxShadow: "0 8px 24px rgba(38,52,68,0.12)",
  fontSize: 11,
  color: "#1f2937",
};

interface VesselType { vessel_type: string; vessel_type_label?: string; count: number }
interface RiskBucket { bucket: number; count: number }
interface TopRiskRow { imo: number; name: string; score: number }
interface EntityMention { entity_text: string; entity_type: string; mentions: number }

export function StatsTab() {
  const [vesselTypes, setVesselTypes] = useState<VesselType[]>([]);
  const [riskHist, setRiskHist] = useState<RiskBucket[]>([]);
  const [topRisk, setTopRisk] = useState<TopRiskRow[]>([]);
  const [sanctions, setSanctions] = useState<Record<string, number>>({});
  const [entities, setEntities] = useState<EntityMention[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.allSettled([
      fetchVesselTypes() as Promise<VesselType[]>,
      fetchRiskHistogram() as Promise<RiskBucket[]>,
      fetchTopRisk() as Promise<TopRiskRow[]>,
      fetchSanctionsOverview(),
      fetchNewsEntities() as Promise<EntityMention[]>,
    ]).then(([vt, rh, tr, so, ne]) => {
      if (vt.status === "fulfilled") setVesselTypes(vt.value);
      if (rh.status === "fulfilled") setRiskHist(rh.value);
      if (tr.status === "fulfilled") setTopRisk(tr.value);
      if (so.status === "fulfilled") setSanctions(so.value);
      if (ne.status === "fulfilled") setEntities(ne.value);
      const rejected = [vt, rh, tr, so, ne].filter((r) => r.status === "rejected");
      if (rejected.length === 5) {
        const reason = rejected[0].reason;
        setError(reason instanceof Error ? reason.message : String(reason));
      }
      setLoading(false);
    });
  }, []);

  if (loading) return <p className="animate-pulse text-xs text-[var(--text-muted)]">Loading charts...</p>;
  if (error) return <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>;

  return (
    <div className="space-y-6">
      <div className="admin-tab-enter">
        <h1 className="text-2xl font-bold tracking-normal text-[var(--text-primary)]">Statistics</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">Fleet composition and risk distribution.</p>
      </div>

      <section className="grid gap-4 md:grid-cols-3">
          {[
            { label: "Sanctioned vessels", value: sanctions.sanctioned ?? "-", color: "text-red-700", bg: "bg-red-50 border-red-100" },
            { label: "Shadow fleet", value: sanctions.shadow_fleet ?? "-", color: "text-amber-700", bg: "bg-amber-50 border-amber-100" },
            { label: "Pending reviews", value: sanctions.pending_reviews ?? "-", color: "text-[var(--accent-deep)]", bg: "bg-teal-50 border-teal-100" },
          ].map((s, index) => (
            <div key={s.label} className="admin-card-enter p-5" style={{ animationDelay: `${index * 50}ms` }}>
              <div className={`mb-3 flex h-10 w-10 items-center justify-center rounded-xl border ${s.bg}`} />
              <div className={`text-4xl font-bold leading-none tracking-normal ${s.color}`}>{s.value}</div>
              <div className="mt-2 text-xs font-medium text-[var(--text-secondary)]">{s.label}</div>
            </div>
          ))}
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
      <section className="admin-card-enter p-5">
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Vessel type distribution</h2>
        <p className="mb-4 mt-1 text-xs text-[var(--text-secondary)]">Top vessel categories.</p>
        {vesselTypes.length === 0 ? (
          <p className="text-xs text-[var(--text-muted)]">No data</p>
        ) : (
          <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
            <ResponsiveContainer width={220} height={220}>
              <PieChart>
                <Pie
                  data={vesselTypes.slice(0, 8)}
                  dataKey="count"
                  nameKey="vessel_type_label"
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  stroke="none"
                  isAnimationActive
                >
                  {vesselTypes.slice(0, 8).map((_, i) => (
                    <Cell
                      key={i}
                      fill={[OCEAN_BLUE, BLUE, AMBER, RED, "#8a93a3", "#7cc8ba", "#6e9df2", "#e0aa70"][i % 8]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={TOOLTIP}
                  formatter={(v) => [v, "vessels"]}
                />
              </PieChart>
            </ResponsiveContainer>
            <ul className="text-xs space-y-1">
              {vesselTypes.slice(0, 8).map((vt, i) => (
                <li key={vt.vessel_type} className="flex items-center gap-2">
                  <span
                    className="inline-block w-2.5 h-2.5 rounded-sm"
                    style={{ background: [OCEAN_BLUE, BLUE, AMBER, RED, "#8a93a3", "#7cc8ba", "#6e9df2", "#e0aa70"][i % 8] }}
                  />
                  <span className="text-[var(--text-primary)]">{vt.vessel_type_label ?? vt.vessel_type}</span>
                  <span className="ml-auto pl-4 text-[var(--text-muted)]">{vt.count.toLocaleString()}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section className="admin-card-enter p-5" style={{ animationDelay: "60ms" }}>
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Risk score distribution</h2>
        <p className="mb-4 mt-1 text-xs text-[var(--text-secondary)]">Last 24 hours.</p>
        {riskHist.length === 0 ? (
          <p className="text-xs text-[var(--text-muted)]">No risk scores in last 24 hours</p>
        ) : (
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={riskHist} barSize={14}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="bucket" tick={{ fontSize: 10, fill: TICK }} />
              <YAxis tick={{ fontSize: 10, fill: TICK }} />
              <Tooltip contentStyle={TOOLTIP} />
              <Bar dataKey="count" fill={OCEAN_BLUE} radius={[6, 6, 0, 0]} isAnimationActive />
            </BarChart>
          </ResponsiveContainer>
        )}
      </section>
      </div>

      <section className="admin-card-enter p-5" style={{ animationDelay: "100ms" }}>
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Top risk vessels</h2>
        <p className="mb-4 mt-1 text-xs text-[var(--text-secondary)]">Highest scoring entities right now.</p>
        {topRisk.length === 0 ? (
          <p className="text-xs text-[var(--text-muted)]">No data</p>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={topRisk} layout="vertical" barSize={12}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10, fill: TICK }} />
              <YAxis
                type="category"
                dataKey="name"
                width={130}
                tick={{ fontSize: 10, fill: TICK }}
              />
              <Tooltip
                contentStyle={TOOLTIP}
                formatter={(v) => [Number(v).toFixed(1), "risk"]}
              />
              <Bar dataKey="score" radius={[0, 6, 6, 0]} isAnimationActive>
                {topRisk.map((row, i) => (
                  <Cell
                    key={i}
                    fill={row.score >= 75 ? RED : row.score >= 40 ? AMBER : OCEAN_BLUE}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </section>

      <section className="admin-card-enter p-5" style={{ animationDelay: "140ms" }}>
        <h2 className="text-base font-semibold text-[var(--text-primary)]">Top entity mentions</h2>
        <p className="mb-4 mt-1 text-xs text-[var(--text-secondary)]">Last 7 days.</p>
        {entities.length === 0 ? (
          <p className="text-xs text-[var(--text-muted)]">No entity mentions</p>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={entities.slice(0, 15)} barSize={16}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis
                dataKey="entity_text"
                tick={{ fontSize: 9, fill: TICK }}
                angle={-30}
                textAnchor="end"
                height={50}
              />
              <YAxis tick={{ fontSize: 10, fill: TICK }} />
              <Tooltip contentStyle={TOOLTIP} />
              <Bar dataKey="mentions" fill={OCEAN_BLUE} radius={[6, 6, 0, 0]} isAnimationActive />
            </BarChart>
          </ResponsiveContainer>
        )}
      </section>
    </div>
  );
}
