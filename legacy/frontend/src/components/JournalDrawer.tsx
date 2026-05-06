import { useEffect, useState } from "react";
import { fetchAdrs, fetchGlossary, fetchPhases } from "../api/journal";
import type { GlossaryTerm, JournalAdr, JournalPhase } from "../api/journal";

type Tab = "phases" | "adrs" | "glossary";

interface Props {
  onClose: () => void;
}

function StatusBadge({ status }: { status: string }) {
  const colours: Record<string, string> = {
    complete: "bg-teal-50 text-teal-700 border-teal-200",
    "in progress": "bg-blue-50 text-blue-700 border-blue-200",
    upcoming: "bg-slate-50 text-slate-600 border-slate-200",
    accepted: "bg-teal-50 text-teal-700 border-teal-200",
    superseded: "bg-amber-50 text-amber-700 border-amber-200",
    rejected: "bg-red-50 text-red-700 border-red-200",
    deprecated: "bg-slate-50 text-slate-600 border-slate-200",
  };
  const cls = colours[status.toLowerCase()] ?? "bg-slate-50 text-slate-600 border-slate-200";
  return (
    <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${cls}`}>
      {status}
    </span>
  );
}

function PhaseCard({ phase }: { phase: JournalPhase }) {
  return (
    <div className="space-y-1 rounded border border-[var(--border)] bg-white/45 p-3">
      <div className="flex items-center gap-2">
        <span className="mono text-xs text-[var(--text-muted)]">Phase {phase.phase_number}</span>
        <StatusBadge status={phase.completed_at ? "Complete" : "Upcoming"} />
      </div>
      <div className="text-sm font-semibold text-[var(--text-primary)]">{phase.title}</div>
      {phase.summary_md && (
        <p className="line-clamp-3 text-xs leading-relaxed text-[var(--text-secondary)]">{phase.summary_md}</p>
      )}
    </div>
  );
}

function AdrCard({ adr }: { adr: JournalAdr }) {
  return (
    <div className="space-y-1 rounded border border-[var(--border)] bg-white/45 p-3">
      <div className="flex items-center gap-2">
        <span className="mono text-xs text-[var(--text-muted)]">ADR {String(adr.adr_number).padStart(4, "0")}</span>
        <StatusBadge status={adr.status} />
        {adr.decided_at && (
          <span className="ml-auto text-[10px] text-[var(--text-muted)]">
            {new Date(adr.decided_at).toLocaleDateString()}
          </span>
        )}
      </div>
      <div className="text-sm font-semibold text-[var(--text-primary)]">{adr.title}</div>
      {adr.summary_md && (
        <p className="line-clamp-3 text-xs leading-relaxed text-[var(--text-secondary)]">{adr.summary_md}</p>
      )}
      {adr.superseded_by_adr_number && (
        <p className="text-[10px] text-amber-700">
          Superseded by ADR {String(adr.superseded_by_adr_number).padStart(4, "0")}
        </p>
      )}
    </div>
  );
}

function GlossaryCard({ term }: { term: GlossaryTerm }) {
  return (
    <div className="space-y-1 rounded border border-[var(--border)] bg-white/45 p-3">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-[var(--text-primary)]">{term.term}</span>
        {term.category && (
          <span className="rounded border border-teal-200 bg-teal-50 px-1.5 py-0.5 text-[10px] text-teal-700">{term.category}</span>
        )}
      </div>
      {term.plain_definition && (
        <p className="text-xs leading-relaxed text-[var(--text-secondary)]">{term.plain_definition}</p>
      )}
      {term.why_it_matters_in_project && (
        <p className="text-[11px] italic leading-relaxed text-[var(--accent-deep)]">
          {term.why_it_matters_in_project}
        </p>
      )}
    </div>
  );
}

export function JournalDrawer({ onClose }: Props) {
  const [tab, setTab] = useState<Tab>("phases");
  const [phases, setPhases] = useState<JournalPhase[]>([]);
  const [adrs, setAdrs] = useState<JournalAdr[]>([]);
  const [glossary, setGlossary] = useState<GlossaryTerm[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchPhases(), fetchAdrs(), fetchGlossary()])
      .then(([p, a, g]) => {
        setPhases(p);
        setAdrs(a);
        setGlossary(g);
        setLoading(false);
      })
      .catch((e: unknown) => {
        setError(String(e));
        setLoading(false);
      });
  }, []);

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: "phases", label: "Phases", count: phases.length },
    { key: "adrs", label: "ADRs", count: adrs.length },
    { key: "glossary", label: "Glossary", count: glossary.length },
  ];

  return (
    <div className="left-drawer-panel glass-panel-bright absolute bottom-0 left-0 top-11 z-[600] flex w-80 max-w-[calc(100vw-1rem)] flex-col overflow-hidden rounded-none border-y-0 border-l-0 shadow-2xl">
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between border-b border-[var(--border)] px-4 py-3">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">Project Journal</h2>
        <button
          onClick={onClose}
          className="rounded border border-[var(--border)] px-1.5 text-[var(--text-secondary)] hover:border-[var(--border-accent)] hover:bg-white"
          aria-label="Close journal"
        >
          ✕
        </button>
      </div>

      {/* Tabs */}
      <div className="shrink-0 border-b border-[var(--border)] p-2">
        <div className="tab-bar">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`tab-btn ${
              tab === t.key
                ? "active"
                : ""
            }`}
          >
            {t.label}
            {t.count > 0 && (
              <span className="ml-1 text-[10px] text-[var(--text-muted)]">({t.count})</span>
            )}
          </button>
        ))}
        </div>
      </div>

      {/* Content */}
      <div className="thin-scroll flex-1 space-y-2 overflow-y-auto p-3">
        {loading && (
          <p className="animate-pulse text-xs text-[var(--text-muted)]">Loading journal...</p>
        )}
        {error && (
          <p className="text-xs text-red-700">Error: {error}</p>
        )}
        {!loading && !error && tab === "phases" && phases.map((p) => (
          <PhaseCard key={p.phase_number} phase={p} />
        ))}
        {!loading && !error && tab === "adrs" && adrs.map((a) => (
          <AdrCard key={a.adr_number} adr={a} />
        ))}
        {!loading && !error && tab === "glossary" && glossary.map((g) => (
          <GlossaryCard key={g.term} term={g} />
        ))}
        {!loading && !error && tab === "phases" && phases.length === 0 && (
          <p className="text-xs text-[var(--text-muted)]">No phases indexed yet. Run the journal indexer.</p>
        )}
        {!loading && !error && tab === "adrs" && adrs.length === 0 && (
          <p className="text-xs text-[var(--text-muted)]">No ADRs indexed yet.</p>
        )}
        {!loading && !error && tab === "glossary" && glossary.length === 0 && (
          <p className="text-xs text-[var(--text-muted)]">No glossary terms indexed yet.</p>
        )}
      </div>
    </div>
  );
}
