import { useEffect, useState } from "react";
import {
  confirmReviewItem,
  fetchReviewQueue,
  rejectReviewItem,
} from "../../api/sanctions";
import type { ReviewQueueItem } from "../../types";

export function ApprovalsTab() {
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"open" | "confirmed" | "rejected" | "all">("open");
  const [msg, setMsg] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const data = await fetchReviewQueue(filter);
      setItems(data);
    } catch (e: unknown) {
      setMsg(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [filter]);

  async function handleAction(id: number, action: "confirm" | "reject") {
    try {
      if (action === "confirm") await confirmReviewItem(id);
      else await rejectReviewItem(id);
      setMsg(`Item ${id} ${action}ed`);
      void load();
    } catch (e: unknown) {
      setMsg(String(e));
    }
    setTimeout(() => setMsg(null), 4000);
  }

  return (
    <div className="space-y-5">
      <div className="admin-tab-enter flex flex-wrap items-end gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-normal text-[var(--text-primary)]">Review queue</h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">Confirm or reject auto-detected entity matches.</p>
        </div>
        <div className="ml-auto flex flex-wrap gap-1">
          {(["open", "confirmed", "rejected", "all"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium capitalize transition ${
                filter === f
                  ? "border-[var(--border-accent)] bg-white text-[var(--text-primary)] shadow-sm"
                  : "border-[var(--border)] bg-white/40 text-[var(--text-secondary)] hover:bg-white"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>
      {msg && <p className="mono rounded-lg border border-teal-200 bg-teal-50 px-3 py-2 text-xs text-[var(--accent-deep)]">{msg}</p>}
      <section className="admin-card-enter overflow-hidden">
        {loading && <p className="animate-pulse p-5 text-xs text-[var(--text-muted)]">Loading...</p>}
        {!loading && items.length === 0 && (
          <p className="p-8 text-center text-sm text-[var(--text-muted)]">No items for status: {filter}</p>
        )}
        {!loading && items.length > 0 && (
          <div className="thin-scroll overflow-auto">
            <table className="admin-table min-w-[760px]">
              <thead>
                <tr><th>ID</th><th>IMO</th><th>OS Entity</th><th>Status</th><th>Confidence</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td className="mono text-[var(--accent-deep)]">{item.id}</td>
                    <td className="mono font-semibold text-[var(--text-primary)]">{item.imo}</td>
                    <td className="max-w-[220px] truncate font-medium text-[var(--text-primary)]">{item.os_entity_id}</td>
                    <td>
                      <span className={`admin-status-pill ${
                        item.status === "confirmed"
                          ? "border-teal-200 bg-teal-50 text-teal-700"
                          : item.status === "rejected"
                            ? "border-red-200 bg-red-50 text-red-700"
                            : "border-amber-200 bg-amber-50 text-amber-700"
                      }`}>
                        {item.status}
                      </span>
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-200">
                          <div
                            className="h-full rounded-full bg-[var(--accent)] transition-all duration-500"
                            style={{ width: `${Math.min(100, Math.max(0, (item.confidence ?? 0) * 100))}%` }}
                          />
                        </div>
                        <span className="mono text-[11px] text-[var(--text-primary)]">
                          {item.confidence != null ? `${(item.confidence * 100).toFixed(0)}%` : "-"}
                        </span>
                      </div>
                    </td>
                    <td>
                      {item.status === "open" && (
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleAction(item.id, "confirm")}
                            className="rounded-md border border-teal-200 bg-teal-50 px-2.5 py-1 text-[11px] font-semibold text-teal-700 transition hover:bg-teal-100"
                          >
                            Confirm
                          </button>
                          <button
                            onClick={() => handleAction(item.id, "reject")}
                            className="rounded-md border border-red-200 bg-red-50 px-2.5 py-1 text-[11px] font-semibold text-red-700 transition hover:bg-red-100"
                          >
                            Reject
                          </button>
                        </div>
                      )}
                    </td>
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
