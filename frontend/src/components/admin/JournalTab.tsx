import { useEffect, useState } from "react";
import { BookOpen, ChevronRight } from "lucide-react";

interface JournalEntry {
  id: number;
  slug: string;
  title: string;
  body: string;
  created_at: string;
  tags: string[];
}

export function JournalTab() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<JournalEntry | null>(null);
  const adminToken = import.meta.env.VITE_ADMIN_TOKEN ?? "";

  useEffect(() => {
    fetch("/api/journal", { headers: { "X-Admin-Token": adminToken } })
      .then((r) => r.json() as Promise<JournalEntry[]>)
      .then(setEntries)
      .catch(() => setEntries([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="animate-pulse text-xs text-[var(--text-muted)]">Loading...</p>;

  return (
    <div className="space-y-5">
      <div className="admin-tab-enter">
        <h1 className="text-2xl font-bold tracking-normal text-[var(--text-primary)]">Journal</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">ADRs, decision records, and project documentation.</p>
      </div>

      <div className="flex min-h-[60vh] flex-col gap-4 lg:flex-row">
        <aside className="admin-card-enter w-full shrink-0 self-start p-3 lg:w-72">
          <p className="mono mb-2 px-2 text-[10px] font-semibold uppercase tracking-[0.10em] text-[var(--text-muted)]">
            Entries
          </p>
          {entries.length === 0 ? (
            <div className="flex flex-col items-center gap-3 px-4 py-8 text-center">
              <BookOpen size={28} className="text-[var(--text-muted)]" />
              <p className="text-xs text-[var(--text-muted)]">No journal entries yet.</p>
            </div>
          ) : (
            <ul className="thin-scroll max-h-[70vh] space-y-0.5 overflow-auto">
              {entries.map((e) => (
                <li key={e.id}>
                  <button
                    onClick={() => setSelected(e)}
                    className={`group flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs transition ${
                      selected?.id === e.id
                        ? "bg-teal-50 text-[var(--accent-deep)]"
                        : "text-[var(--text-secondary)] hover:bg-white/70 hover:text-[var(--text-primary)]"
                    }`}
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{e.title}</span>
                      <span className="block text-[10px] text-[var(--text-muted)]">
                        {new Date(e.created_at).toLocaleDateString()}
                      </span>
                    </span>
                    <ChevronRight size={12} className="shrink-0 opacity-0 group-hover:opacity-100" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <section className="admin-card-enter min-w-0 flex-1 overflow-hidden" style={{ animationDelay: "80ms" }}>
          {!selected ? (
            <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 p-8 text-center">
              <BookOpen size={32} className="text-[var(--text-muted)]" />
              <p className="text-sm text-[var(--text-muted)]">Select an entry to read.</p>
            </div>
          ) : (
            <div className="thin-scroll h-full overflow-auto p-6">
              <div className="mb-1 flex flex-wrap gap-1.5">
                {selected.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-teal-200 bg-teal-50 px-2 py-0.5 text-[10px] font-semibold text-[var(--accent-deep)]"
                  >
                    {tag}
                  </span>
                ))}
              </div>
              <h2 className="mb-1 text-xl font-bold tracking-normal text-[var(--text-primary)]">
                {selected.title}
              </h2>
              <p className="mono mb-5 text-[11px] text-[var(--text-muted)]">
                {new Date(selected.created_at).toLocaleString()}
              </p>
              <div className="prose prose-sm max-w-none text-[var(--text-secondary)]">
                {selected.body.split("\n").map((line, i) =>
                  line.trim() === "" ? (
                    <br key={i} />
                  ) : (
                    <p key={i} className="mb-2 leading-relaxed">
                      {line}
                    </p>
                  ),
                )}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
