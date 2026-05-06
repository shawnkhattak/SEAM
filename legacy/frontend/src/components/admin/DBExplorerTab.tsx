import { useEffect, useState } from "react";
import { fetchTableList, fetchTablePage } from "../../api/admin";
import type { TablePage } from "../../api/admin";

export function DBExplorerTab() {
  const [tables, setTables] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<TablePage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTableList()
      .then(setTables)
      .catch((e: unknown) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    setError(null);
    fetchTablePage(selected, page)
      .then((d) => { setData(d); setLoading(false); })
      .catch((e: unknown) => { setError(String(e)); setLoading(false); });
  }, [selected, page]);

  function selectTable(t: string) {
    setSelected(t);
    setPage(1);
    setData(null);
  }

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1;

  return (
    <div className="space-y-5">
      <div className="admin-tab-enter">
        <h1 className="text-2xl font-bold tracking-normal text-[var(--text-primary)]">Data explorer</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">Browse raw tables in read-only mode.</p>
      </div>

      <div className="flex min-h-[65vh] flex-col gap-4 lg:flex-row">
        <aside className="admin-card-enter w-full shrink-0 self-start p-3 lg:w-64">
        <p className="mono mb-2 px-2 text-[10px] font-semibold uppercase tracking-[0.10em] text-[var(--text-muted)]">Tables</p>
        <ul className="thin-scroll max-h-[60vh] space-y-0.5 overflow-auto">
          {tables.map((t) => (
            <li key={t}>
              <button
                onClick={() => selectTable(t)}
                className={`w-full rounded-lg px-3 py-2 text-left text-xs transition ${
                  selected === t
                    ? "bg-teal-50 font-semibold text-[var(--accent-deep)]"
                    : "text-[var(--text-secondary)] hover:bg-white/70 hover:text-[var(--text-primary)]"
                }`}
              >
                {t}
              </button>
            </li>
          ))}
        </ul>
        </aside>

      <section className="admin-card-enter min-w-0 flex-1 overflow-hidden" style={{ animationDelay: "80ms" }}>
        {!selected && (
          <p className="p-8 text-sm text-[var(--text-muted)]">Select a table to browse rows.</p>
        )}
        {error && <p className="p-5 text-xs text-red-700">{error}</p>}
        {loading && <p className="animate-pulse p-5 text-xs text-[var(--text-muted)]">Loading...</p>}
        {data && !loading && (
          <div className="flex h-full flex-col">
            <div className="flex items-center gap-3 border-b border-[var(--border)] bg-white/45 px-5 py-4">
              <h2 className="mono text-xs font-semibold text-[var(--accent-deep)]">{data.table}</h2>
              <span className="text-[11px] text-[var(--text-muted)]">
                {data.total.toLocaleString()} rows · page {data.page} of {totalPages}
              </span>
              <div className="ml-auto flex gap-1">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded-md border border-[var(--border)] bg-white/60 px-2 py-0.5 text-xs text-[var(--text-secondary)] hover:bg-white disabled:opacity-30"
                >
                  Prev
                </button>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-md border border-[var(--border)] bg-white/60 px-2 py-0.5 text-xs text-[var(--text-secondary)] hover:bg-white disabled:opacity-30"
                >
                  Next
                </button>
              </div>
            </div>
            <div className="thin-scroll overflow-auto">
              <table className="admin-table min-w-[900px]">
                <thead>
                  <tr>
                    {data.columns.map((col) => (
                      <th key={col}>
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((row, i) => (
                    <tr key={i}>
                      {data.columns.map((col) => {
                        const val = row[col];
                        const display =
                          val === null ? (
                            <span className="text-slate-400">null</span>
                          ) : typeof val === "object" ? (
                            <span className="text-[var(--text-muted)]">{JSON.stringify(val).slice(0, 80)}</span>
                          ) : (
                            <span className="text-[var(--text-primary)]">{String(val).slice(0, 80)}</span>
                          );
                        return (
                          <td key={col} className="max-w-[220px] truncate">
                            {display}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
      </div>
    </div>
  );
}
