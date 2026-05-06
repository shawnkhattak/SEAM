import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { SupportedTimezone } from "../types";

interface TimezoneState {
  timezone: SupportedTimezone;
  setTimezone: (tz: SupportedTimezone) => void;
}

export const useTimezoneStore = create<TimezoneState>()(
  persist(
    (set) => ({
      timezone: "America/Chicago",
      setTimezone: (tz) => set({ timezone: tz }),
    }),
    { name: "oceansx-timezone" },
  ),
);
