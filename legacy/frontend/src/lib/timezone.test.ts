import { describe, expect, it } from "vitest";
import { formatUtc, relativeTime, resolveTimezone } from "./timezone";

describe("resolveTimezone", () => {
  it("passes through named zones", () => {
    expect(resolveTimezone("UTC")).toBe("UTC");
    expect(resolveTimezone("Asia/Singapore")).toBe("Asia/Singapore");
    expect(resolveTimezone("America/Chicago")).toBe("America/Chicago");
  });

  it("resolves __browser__ to a valid IANA zone", () => {
    const zone = resolveTimezone("__browser__");
    expect(typeof zone).toBe("string");
    expect(zone.length).toBeGreaterThan(0);
  });
});

describe("formatUtc", () => {
  it("formats an ISO 8601 UTC string in Chicago time", () => {
    const formatted = formatUtc("2026-04-30T12:00:00+00:00", "America/Chicago");
    expect(formatted).toContain("2026-04-30");
    expect(formatted).toMatch(/07:00:00/); // CDT = UTC-5
  });

  it("returns em-dash for null", () => {
    expect(formatUtc(null, "UTC")).toBe("—");
    expect(formatUtc(undefined, "UTC")).toBe("—");
  });
});

describe("relativeTime", () => {
  it("returns a non-empty string for a past timestamp", () => {
    const past = new Date(Date.now() - 3600_000).toISOString();
    const rel = relativeTime(past);
    expect(rel).not.toBe("—");
    expect(rel).toContain("ago");
  });

  it("returns em-dash for null", () => {
    expect(relativeTime(null)).toBe("—");
  });
});
