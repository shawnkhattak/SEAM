import { DateTime } from "luxon";
import type { SupportedTimezone } from "../types";

export const TIMEZONE_OPTIONS: { label: string; value: SupportedTimezone }[] = [
  { label: "Chicago (CT)", value: "America/Chicago" },
  { label: "UTC", value: "UTC" },
  { label: "Singapore (SGT)", value: "Asia/Singapore" },
  { label: "Browser", value: "__browser__" },
];

export function resolveTimezone(tz: SupportedTimezone): string {
  return tz === "__browser__" ? Intl.DateTimeFormat().resolvedOptions().timeZone : tz;
}

export function formatUtc(
  isoString: string | null | undefined,
  tz: SupportedTimezone,
  fmt = "yyyy-MM-dd HH:mm:ss ZZZZ",
): string {
  if (!isoString) return "—";
  const dt = DateTime.fromISO(isoString, { zone: "utc" }).setZone(resolveTimezone(tz));
  return dt.isValid ? dt.toFormat(fmt) : isoString;
}

export function relativeTime(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  const dt = DateTime.fromISO(isoString, { zone: "utc" });
  if (!dt.isValid) return "—";
  // Never show "in X minutes" — clamp prevents future timestamps at source.
  const rel = dt.toRelative();
  return rel ?? "—";
}

export function tzAbbreviation(tz: SupportedTimezone): string {
  const zone = resolveTimezone(tz);
  return DateTime.now().setZone(zone).toFormat("ZZZZ");
}
