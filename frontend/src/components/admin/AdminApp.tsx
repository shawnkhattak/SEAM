import { lazy, Suspense, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  BarChart3,
  BookOpen,
  CheckCircle2,
  Database,
  Home,
  KeyRound,
  Menu,
  RadioTower,
  Zap,
} from "lucide-react";

const OverviewTab = lazy(() =>
  import("./OverviewTab").then((m) => ({ default: m.OverviewTab }))
);
const ApprovalsTab = lazy(() =>
  import("./ApprovalsTab").then((m) => ({ default: m.ApprovalsTab }))
);
const DBExplorerTab = lazy(() =>
  import("./DBExplorerTab").then((m) => ({ default: m.DBExplorerTab }))
);
const StatsTab = lazy(() =>
  import("./StatsTab").then((m) => ({ default: m.StatsTab }))
);
const ConfigTab = lazy(() =>
  import("./ConfigTab").then((m) => ({ default: m.ConfigTab }))
);
const JournalTab = lazy(() =>
  import("./JournalTab").then((m) => ({ default: m.JournalTab }))
);

type Tab = "overview" | "approvals" | "db" | "stats" | "config" | "journal" | "ops";

const TABS: { key: Tab; label: string; icon: ReactNode }[] = [
  { key: "overview", label: "Overview", icon: <Home size={16} /> },
  { key: "approvals", label: "Approvals", icon: <CheckCircle2 size={16} /> },
  { key: "db", label: "Data", icon: <Database size={16} /> },
  { key: "stats", label: "Stats", icon: <BarChart3 size={16} /> },
  { key: "config", label: "Config", icon: <KeyRound size={16} /> },
  { key: "journal", label: "Journal", icon: <BookOpen size={16} /> },
  { key: "ops", label: "Ops Swarm", icon: <Zap size={16} /> },
];

function SeamMark({ size = 28 }: { size?: number }) {
  const id = `admin-seam-${size}`;
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

const TabLoading = () => (
  <div className="flex min-h-[40vh] items-center justify-center">
    <p className="animate-pulse text-xs text-[var(--text-muted)]">Loading…</p>
  </div>
);

export function AdminApp() {
  const [tab, setTab] = useState<Tab>("overview");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  function selectTab(next: Tab) {
    setTab(next);
    setSidebarOpen(false);
  }

  return (
    <div className="admin-shell fixed inset-0 flex flex-col overflow-hidden bg-[var(--bg-base)] text-[var(--text-primary)]">
      <header className="admin-header glass-panel-bright z-20 flex h-14 shrink-0 items-center gap-3 rounded-none border-x-0 border-t-0 px-4 md:px-5">
        <button
          onClick={() => setSidebarOpen((v) => !v)}
          className="admin-mobile-menu hidden h-8 w-8 items-center justify-center rounded-lg border border-[var(--border)] text-[var(--text-secondary)] hover:bg-white"
          aria-label="Toggle admin navigation"
        >
          <Menu size={16} />
        </button>
        <SeamMark />
        <div>
          <div className="text-base font-extrabold leading-none tracking-normal">
            SEAM <span className="font-semibold text-[var(--accent-deep)]">Admin</span>
          </div>
          <div className="mono mt-1 text-[10px] tracking-[0.06em] text-[var(--text-muted)]">
            Internal · Build 2026.05
          </div>
        </div>
        <div className="ml-auto hidden items-center gap-2 rounded-full border border-teal-200 bg-teal-50 px-3 py-1.5 md:flex">
          <span className="live-dot" />
          <span className="mono text-[11px] font-semibold text-[var(--accent-deep)]">All systems healthy</span>
        </div>
        <a
          href="/"
          className="rounded-lg border border-[var(--border-accent)] bg-white/60 px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] transition hover:-translate-y-0.5 hover:bg-white hover:shadow-sm"
        >
          Back to map
        </a>
      </header>

      <div className="relative z-10 flex min-h-0 flex-1 overflow-hidden">
        <aside className={`admin-sidebar ${sidebarOpen ? "open" : ""}`}>
          <div className="mono px-3 pb-2 pt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
            Navigation
          </div>
          <nav className="space-y-1">
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => selectTab(t.key)}
                className={`admin-nav-item ${tab === t.key ? "active" : ""}`}
              >
                {t.icon}
                <span>{t.label}</span>
                {tab === t.key && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[var(--accent)]" />}
              </button>
            ))}
          </nav>
          <div className="mt-auto rounded-xl border border-[var(--border)] bg-white/50 p-3 text-xs leading-relaxed text-[var(--text-secondary)]">
            <div className="mb-1 flex items-center gap-2 font-semibold text-[var(--text-primary)]">
              <RadioTower size={14} className="text-[var(--accent-deep)]" />
              Live Control
            </div>
            Force actions trigger real ingestion and scoring endpoints when an admin token is configured.
          </div>
        </aside>

        {sidebarOpen && (
          <button
            className="absolute inset-0 z-20 bg-slate-900/20 md:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close navigation overlay"
          />
        )}

        <main className="thin-scroll min-w-0 flex-1 overflow-y-auto p-5 md:p-7">
          <div key={tab} className="admin-tab-enter mx-auto max-w-7xl">
            <Suspense fallback={<TabLoading />}>
              {tab === "overview" && <OverviewTab />}
              {tab === "approvals" && <ApprovalsTab />}
              {tab === "db" && <DBExplorerTab />}
              {tab === "stats" && <StatsTab />}
              {tab === "config" && <ConfigTab />}
              {tab === "journal" && <JournalTab />}
              {tab === "ops" && <OpsSwarmTab />}
            </Suspense>
          </div>
        </main>
      </div>
    </div>
  );
}

function OpsSwarmTab() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <section className="glass-panel admin-card-enter max-w-md px-10 py-9 text-center">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-blue-200 bg-blue-50 text-blue-700">
          <Zap size={28} className="admin-pulse-icon" />
        </div>
        <h1 className="text-xl font-semibold tracking-normal text-[var(--text-primary)]">Ops Swarm</h1>
        <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">
          Multi-agent coordination view is reserved for the post-launch operations console.
        </p>
        <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700">
          <Activity size={13} />
          Coming soon
        </div>
      </section>
    </div>
  );
}
