import axios from "axios";
import type { NewsSummaryResponse, NlSearchResult, VesselDetail } from "../types";

const api = axios.create({ baseURL: "/api" });

export async function fetchNewsSummary(newsId: number): Promise<NewsSummaryResponse> {
  const { data } = await api.post<NewsSummaryResponse>(`/news/${newsId}/summarize`);
  return data;
}

export async function fetchNewArrivals(hours = 24): Promise<VesselDetail[]> {
  const { data } = await api.get<VesselDetail[]>("/vessels/new-arrivals", { params: { hours } });
  return data;
}

export async function fetchNlSearch(query: string): Promise<NlSearchResult> {
  const { data } = await api.post<NlSearchResult>("/search/nl", { query });
  return data;
}
