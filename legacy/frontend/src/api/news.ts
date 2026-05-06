import axios from "axios";

const api = axios.create({ baseURL: "/api" });

export interface NewsEntity {
  entity_type: "vessel" | "port";
  entity_ref_id: number;
  matched_text: string;
}

export interface NewsItem {
  id: number;
  title: string;
  url: string;
  published_at_utc: string;
  ingested_at_utc: string;
  extraction_status: string;
  body_text: string | null;
  entities: NewsEntity[];
}

export async function fetchNews(params?: {
  limit?: number;
  entity_type?: string;
  entity_ref_id?: number;
}): Promise<NewsItem[]> {
  const { data } = await api.get<NewsItem[]>("/news/items", { params });
  return data;
}
