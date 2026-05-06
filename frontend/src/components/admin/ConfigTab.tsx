import { useEffect, useState } from "react";
import { Eye, EyeOff, KeyRound, Trash2 } from "lucide-react";
import {
  deleteConfigKey,
  fetchConfigKeys,
  setConfigKey,
  type ConfigKey,
} from "../../api/admin";

export function ConfigTab() {
  const [keys, setKeys] = useState<ConfigKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<{ text: string; error?: boolean } | null>(null);
  const [editKey, setEditKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [showValue, setShowValue] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newSecret, setNewSecret] = useState(true);

  async function load() {
    setLoading(true);
    try {
      setKeys(await fetchConfigKeys());
    } catch (e: unknown) {
      setMsg({ text: String(e), error: true });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  function flash(text: string, error = false) {
    setMsg({ text, error });
    setTimeout(() => setMsg(null), 5000);
  }

  async function handleSaveEdit(key: string) {
    try {
      await setConfigKey(key, editValue, {});
      flash(`Saved "${key}"`);
      setEditKey(null);
      setEditValue("");
      void load();
    } catch (e: unknown) {
      flash(String(e), true);
    }
  }

  async function handleDelete(key: string) {
    if (!confirm(`Delete config key "${key}"?`)) return;
    try {
      await deleteConfigKey(key);
      flash(`Deleted "${key}"`);
      void load();
    } catch (e: unknown) {
      flash(String(e), true);
    }
  }

  async function handleCreate() {
    if (!newKey.trim() || !newValue.trim()) return;
    try {
      await setConfigKey(newKey.trim(), newValue, {
        is_secret: newSecret,
        description: newDesc.trim() || undefined,
      });
      flash(`Created "${newKey.trim()}"`);
      setNewKey("");
      setNewValue("");
      setNewDesc("");
      setNewSecret(true);
      void load();
    } catch (e: unknown) {
      flash(String(e), true);
    }
  }

  return (
    <div className="space-y-6">
      <div className="admin-tab-enter">
        <h1 className="text-2xl font-bold tracking-normal text-[var(--text-primary)]">Configuration</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Manage API keys and runtime configuration. Secret values are Fernet-encrypted at rest.
        </p>
      </div>

      {msg && (
        <p className={`mono rounded-lg border px-3 py-2 text-xs ${
          msg.error
            ? "border-red-200 bg-red-50 text-red-700"
            : "border-teal-200 bg-teal-50 text-[var(--accent-deep)]"
        }`}>
          {msg.text}
        </p>
      )}

      {/* Existing keys */}
      <section className="admin-card-enter overflow-hidden">
        <div className="border-b border-[var(--border)] px-5 py-4">
          <h2 className="text-base font-semibold text-[var(--text-primary)]">Current keys</h2>
        </div>
        {loading && <p className="animate-pulse p-5 text-xs text-[var(--text-muted)]">Loading...</p>}
        {!loading && keys.length === 0 && (
          <p className="p-8 text-center text-sm text-[var(--text-muted)]">No config keys yet.</p>
        )}
        {!loading && keys.length > 0 && (
          <div className="thin-scroll overflow-auto">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Key</th><th>Description</th><th>Secret</th><th>Has value</th>
                  <th>Updated</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {keys.map((k) => (
                  <tr key={k.key}>
                    <td className="mono font-semibold text-[var(--accent-deep)]">{k.key}</td>
                    <td className="text-[var(--text-secondary)]">{k.description ?? "—"}</td>
                    <td>
                      {k.is_secret ? (
                        <span className="admin-status-pill border-amber-200 bg-amber-50 text-amber-700">
                          <KeyRound size={10} className="mr-1 inline" />secret
                        </span>
                      ) : (
                        <span className="admin-status-pill border-slate-200 bg-slate-50 text-slate-500">plain</span>
                      )}
                    </td>
                    <td>
                      <span className={`admin-status-pill ${k.has_value ? "border-teal-200 bg-teal-50 text-teal-700" : "border-slate-200 bg-slate-50 text-slate-400"}`}>
                        {k.has_value ? "set" : "empty"}
                      </span>
                    </td>
                    <td className="mono text-[11px] text-[var(--text-muted)]">
                      {k.updated_at ? new Date(k.updated_at).toLocaleString() : "—"}
                      {k.updated_by && <span className="ml-1">by {k.updated_by}</span>}
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        {editKey === k.key ? (
                          <div className="flex items-center gap-1.5">
                            <div className="relative">
                              <input
                                type={showValue ? "text" : "password"}
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                placeholder="New value"
                                className="mono w-40 rounded border border-[var(--border)] bg-white px-2 py-1 text-xs text-[var(--text-primary)] focus:border-[var(--border-accent)] focus:outline-none"
                                autoFocus
                              />
                              <button
                                type="button"
                                onClick={() => setShowValue((v) => !v)}
                                className="absolute right-1.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
                              >
                                {showValue ? <EyeOff size={11} /> : <Eye size={11} />}
                              </button>
                            </div>
                            <button
                              onClick={() => handleSaveEdit(k.key)}
                              className="rounded-md border border-teal-200 bg-teal-50 px-2 py-1 text-[11px] font-semibold text-teal-700 hover:bg-teal-100"
                            >
                              Save
                            </button>
                            <button
                              onClick={() => { setEditKey(null); setEditValue(""); }}
                              className="rounded-md border border-[var(--border)] bg-white px-2 py-1 text-[11px] text-[var(--text-secondary)] hover:bg-slate-50"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => { setEditKey(k.key); setEditValue(""); setShowValue(false); }}
                            className="rounded-md border border-[var(--border)] bg-white px-2.5 py-1 text-[11px] text-[var(--text-secondary)] transition hover:border-[var(--border-accent)] hover:bg-white"
                          >
                            Update
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete(k.key)}
                          className="rounded-md border border-red-200 bg-red-50 p-1 text-red-600 transition hover:bg-red-100"
                          aria-label="Delete"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Add new key */}
      <section className="admin-card-enter p-5" style={{ animationDelay: "60ms" }}>
        <h2 className="mb-4 text-base font-semibold text-[var(--text-primary)]">Add / update key</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="mono mb-1 block text-[10px] font-semibold uppercase tracking-[0.06em] text-[var(--text-muted)]">
              Key name
            </label>
            <input
              type="text"
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              placeholder="e.g. oceansx_api_key"
              className="mono w-full rounded border border-[var(--border)] bg-white px-2.5 py-1.5 text-xs text-[var(--text-primary)] focus:border-[var(--border-accent)] focus:outline-none"
            />
          </div>
          <div>
            <label className="mono mb-1 block text-[10px] font-semibold uppercase tracking-[0.06em] text-[var(--text-muted)]">
              Value
            </label>
            <input
              type="password"
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              placeholder="Value"
              className="mono w-full rounded border border-[var(--border)] bg-white px-2.5 py-1.5 text-xs text-[var(--text-primary)] focus:border-[var(--border-accent)] focus:outline-none"
            />
          </div>
          <div>
            <label className="mono mb-1 block text-[10px] font-semibold uppercase tracking-[0.06em] text-[var(--text-muted)]">
              Description
            </label>
            <input
              type="text"
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              placeholder="Optional description"
              className="w-full rounded border border-[var(--border)] bg-white px-2.5 py-1.5 text-xs text-[var(--text-primary)] focus:border-[var(--border-accent)] focus:outline-none"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="mono mb-1 block text-[10px] font-semibold uppercase tracking-[0.06em] text-[var(--text-muted)]">
              Type
            </label>
            <label className="flex cursor-pointer items-center gap-2 text-xs text-[var(--text-secondary)]">
              <input
                type="checkbox"
                checked={newSecret}
                onChange={(e) => setNewSecret(e.target.checked)}
                className="rounded"
              />
              Store as secret (encrypted)
            </label>
          </div>
        </div>
        <div className="mt-4">
          <button
            onClick={handleCreate}
            disabled={!newKey.trim() || !newValue.trim()}
            className="rounded-lg border border-[var(--border-accent)] bg-white px-4 py-2 text-sm font-semibold text-[var(--accent-deep)] transition hover:bg-teal-50 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Save key
          </button>
        </div>
      </section>
    </div>
  );
}
