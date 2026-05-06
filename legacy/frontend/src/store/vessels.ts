import { create } from "zustand";

interface VesselUIState {
  selectedImo: number | null;
  setSelectedImo: (imo: number | null) => void;
  highlightedImo: number | null;
  setHighlightedImo: (imo: number | null) => void;
  /** Map filter: show only shadow fleet */
  filterShadowFleet: boolean;
  toggleShadowFleetFilter: () => void;
  /** Map filter: show only sanctioned */
  filterSanctioned: boolean;
  toggleSanctionedFilter: () => void;
  /** Risk threshold slider (0–100, default 0 = show all) */
  riskThreshold: number;
  setRiskThreshold: (v: number) => void;
}

export const useVesselStore = create<VesselUIState>()((set) => ({
  selectedImo: null,
  setSelectedImo: (imo) => set({ selectedImo: imo }),
  highlightedImo: null,
  setHighlightedImo: (imo) => set({ highlightedImo: imo }),
  filterShadowFleet: false,
  toggleShadowFleetFilter: () => set((s) => ({ filterShadowFleet: !s.filterShadowFleet })),
  filterSanctioned: false,
  toggleSanctionedFilter: () => set((s) => ({ filterSanctioned: !s.filterSanctioned })),
  riskThreshold: 0,
  setRiskThreshold: (v) => set({ riskThreshold: v }),
}));
