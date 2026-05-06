import type { RiskLeaderboardItem, RiskScoreResponse } from "../types";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export async function fetchVesselRisk(
  imo: number,
  days = 30,
): Promise<RiskScoreResponse[]> {
  const res = await fetch(`${BASE}/api/risk/vessel/${imo}?days=${days}`);
  if (res.status === 404) return [];
  if (!res.ok) throw new Error(`risk fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchRiskLeaderboard(
  limit = 20,
  minScore = 0,
): Promise<RiskLeaderboardItem[]> {
  const res = await fetch(
    `${BASE}/api/risk/leaderboard?limit=${limit}&min_score=${minScore}`,
  );
  if (!res.ok) throw new Error(`leaderboard fetch failed: ${res.status}`);
  return res.json();
}
