import { useEffect, useState } from "react";
import { CloudSun, FileSearch, Newspaper, RefreshCw, ShieldAlert } from "lucide-react";
import {
  fetchAuditLog,
  fetchDependencyAudit,
  fetchSourcesHealth,
  forceAction,
} from "../../api/admin";

interface SourceHealth {
  source_name: string;
  last_success_at: string | null;
  last_attempt_at: string | null;
  last_error: string | null;
  consecutive_failures: number;
}

interface AuditEntry {
  id: number;
  occurred_at: string;
  actor: string;
  action: string;
  target_type: string | null;
  severity: string;
  detail: Record<string, unknown> | null;
}

interface DepAudit {
  id: number;
  audited_at: string;
  ecosystem: string;
  high_critical_count: number;
  total_count: number;
}

const FORCE_ACTIONS = [
  { key: "force-poll", label: "Force Poll", desc: "Re-fetch AIS positions", icon: <RefreshCw size={18} /> },
  { key: "force-risk-score", label: "Force Risk Score", desc: "Recompute vessel risk", icon: <ShieldAlert size={18} /> },
  { key: "force-weather", label: "Force Weather", desc: "Refresh metocean overlays", icon: <CloudSun size={18} /> },
  { key: "force-news", label: "Force News", desc: "Pull latest maritime news", icon: <Newspaper size={18} /> },
  { key: "force-journal-index", label: "Force Journal Index", desc: "Rebuild docs search index", icon: <FileSearch size={18} /> },
];

function HealthRow({ s }: { s: SourceHealth }) {
  const ok = s.consecutive_failures === 0;
  return (
    <tr>
      <td className="font-medium text-[var(--text-primary)]">{s.source_name}</td>
      <td>
        <span className={`admin-status-pill ${ok ? "border-teal-200 bg-teal-50 text-teal-700" : "border-red-200 bg-red-50 text-red-700"}`}>
          {ok ? "OK" : `${s.consecutive_failures} failures`}
        </span>
      </td>
      <td className="mono text-[11px] text-[var(--text-muted)]">
        {s.last_success_at ? new Date(s.last_success_at).toLocaleString() : "never"}
      </td>
    </tr>
  );
}

export function OverviewTab() {
  const [sources, setSources] = useState<SourceHealth[]>([]);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [depAudit, setDepAudit] = useState<DepAudit[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetchSourcesHealth() as Promise<SourceHealth[]>,
      fetchAuditLog() as Promise<AuditEntry[]>,
      fetchDependencyAudit() as Promise<DepAudit[]>,
    ])
      .then(([s, a, d]) => {
        setSources(s);
        setAuditLog(a);
        setDepAudit(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  async function handleForce(action: string) {
    try {
      setActionMsg(`Running ${action}…`);
      const result = await forceAction(action);
      setActionMsg(`Done: ${JSON.stringify(result)}`);
    } catch (e: unknown) {
      setActionMsg(`Error: ${String(e)}`);
    }
    setTimeout(() => setActionMsg(null), 6000);
  }

  if (loading) return <p className="animate-pulse text-xs text-[var(--text-muted)]">Loading...</p>;

  return (
    <div className="space-y-6">
      <div className="admin-tab-enter">
        <h1 className="text-2xl font-bold tracking-normal text-[var(--text-primary)]">Welcome back</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">Pipelines and data sources at a glance.</p>
      </div>

      <section className="admin-card-enter p-5">
        <div className="mb-4">
          <h2 className="text-base font-semibold text-[var(--text-primary)]">Force actions</h2>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">Manually trigger ingestion or scoring pipelines.</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {FORCE_ACTIONS.map((a) => (
            <button key={a.key} onClick={() => handleForce(a.key)} className="admin-action-btn">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-teal-200 bg-teal-50 text-[var(--accent-deep)]">
                {a.icon}
              </span>
              <span className="min-w-0">
                <span className="block font-semibold">{a.label}</span>
                <span className="block truncate text-[10px] text-[var(--text-muted)]">{a.desc}</span>
              </span>
            </button>
          ))}
        </div>
        {actionMsg && (
          <p className="mono mt-4 rounded-lg border border-teal-200 bg-teal-50 px-3 py-2 text-xs text-[var(--accent-deep)]">
            {actionMsg}
          </p>
        )}
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <section className="admin-card-enter overflow-hidden" style={{ animationDelay: "60ms" }}>
          <div className="border-b border-[var(--border)] px-5 py-4">
            <h2 className="text-base font-semibold text-[var(--text-primary)]">Source health</h2>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">Upstream data feeds.</p>
          </div>
          {sources.length === 0 ? (
            <p className="p-5 text-xs text-[var(--text-muted)]">No status rows yet. Sources report after first run.</p>
          ) : (
            <div className="thin-scroll max-h-[360px] overflow-auto">
              <table className="admin-table">
                <thead><tr><th>Source</th><th>Status</th><th>Last Success</th></tr></thead>
                <tbody>{sources.map((s) => <HealthRow key={s.source_name} s={s} />)}</tbody>
              </table>
            </div>
          )}
        </section>

        <section className="admin-card-enter overflow-hidden" style={{ animationDelay: "100ms" }}>
          <div className="border-b border-[var(--border)] px-5 py-4">
            <h2 className="text-base font-semibold text-[var(--text-primary)]">Dependency audit</h2>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">Last 10 audit runs.</p>
          </div>
          {depAudit.length === 0 ? (
            <p className="p-5 text-xs text-[var(--text-muted)]">No audit runs yet.</p>
          ) : (
            <div className="thin-scroll max-h-[360px] overflow-auto">
              <table className="admin-table">
                <thead><tr><th>Ecosystem</th><th>High/Critical</th><th>Total</th><th>Run at</th></tr></thead>
                <tbody>
                  {depAudit.map((d) => (
                    <tr key={d.id}>
                      <td className="font-medium text-[var(--text-primary)]">{d.ecosystem}</td>
                      <td className={d.high_critical_count > 0 ? "font-semibold text-red-700" : "font-semibold text-teal-700"}>
                        {d.high_critical_count}
                      </td>
                      <td>{d.total_count}</td>
                      <td className="mono text-[11px] text-[var(--text-muted)]">
                        {new Date(d.audited_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      <section className="admin-card-enter overflow-hidden" style={{ animationDelay: "140ms" }}>
        <div className="border-b border-[var(--border)] px-5 py-4">
          <h2 className="text-base font-semibold text-[var(--text-primary)]">Recent activity</h2>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">Audit log, last 50 events.</p>
        </div>
        {auditLog.length === 0 ? (
          <p className="p-5 text-xs text-[var(--text-muted)]">No audit entries yet.</p>
        ) : (
          <div className="thin-scroll max-h-[440px] overflow-auto">
            <table className="admin-table">
              <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Severity</th></tr></thead>
              <tbody>
                {auditLog.map((e) => (
                  <tr key={e.id}>
                    <td className="mono whitespace-nowrap text-[11px] text-[var(--text-muted)]">
                      {new Date(e.occurred_at).toLocaleString()}
                    </td>
                    <td>{e.actor}</td>
                    <td className="font-medium text-[var(--text-primary)]">{e.action}</td>
                    <td className={
                      e.severity === "warning" ? "font-semibold text-amber-700" :
                      e.severity === "error" ? "font-semibold text-red-700" :
                      "text-[var(--text-muted)]"
                    }>{e.severity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
