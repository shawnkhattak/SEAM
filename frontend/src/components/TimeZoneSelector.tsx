import { TIMEZONE_OPTIONS, tzAbbreviation } from "../lib/timezone";
import { useTimezoneStore } from "../store/timezone";
import type { SupportedTimezone } from "../types";

export function TimeZoneSelector() {
  const { timezone, setTimezone } = useTimezoneStore();

  return (
    <div className="flex items-center gap-2 text-xs text-slate-400">
      <span>All times:</span>
      <select
        value={timezone}
        onChange={(e) => setTimezone(e.target.value as SupportedTimezone)}
        className="bg-transparent border border-slate-600 rounded px-1 py-0.5 text-slate-300 focus:outline-none focus:border-ocean-500"
        aria-label="Display timezone"
      >
        {TIMEZONE_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value} className="bg-slate-800">
            {opt.label}
          </option>
        ))}
      </select>
      <span className="text-slate-500">({tzAbbreviation(timezone)})</span>
    </div>
  );
}
