import axios from "axios";

const api = axios.create({ baseURL: "/api" });

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      return Promise.reject(
        new Error(
          "Admin token rejected. Set VITE_ADMIN_TOKEN to match backend ADMIN_TOKEN, then restart the frontend.",
        ),
      );
    }
    return Promise.reject(error);
  },
);

function adminHeaders() {
  return { "X-Admin-Token": import.meta.env.VITE_ADMIN_TOKEN ?? "" };
}

export async function forceAction(action: string): Promise<Record<string, string>> {
  const { data } = await api.post<Record<string, string>>(
    `/admin/${action}`,
    null,
    { headers: adminHeaders() },
  );
  return data;
}

export interface TablePage {
  table: string;
  page: number;
  page_size: number;
  total: number;
  columns: string[];
  rows: Record<string, unknown>[];
}

export async function fetchTableList(): Promise<string[]> {
  const { data } = await api.get<string[]>("/admin/db", { headers: adminHeaders() });
  return data;
}

export async function fetchTablePage(table: string, page: number): Promise<TablePage> {
  const { data } = await api.get<TablePage>(`/admin/db/${table}`, {
    params: { page },
    headers: adminHeaders(),
  });
  return data;
}

export async function fetchSourcesHealth(): Promise<unknown[]> {
  const { data } = await api.get<unknown[]>("/admin/stats/sources", { headers: adminHeaders() });
  return data;
}

export async function fetchVesselTypes(): Promise<unknown[]> {
  const { data } = await api.get<unknown[]>("/admin/stats/vessel-types", { headers: adminHeaders() });
  return data;
}

export async function fetchRiskHistogram(): Promise<unknown[]> {
  const { data } = await api.get<unknown[]>("/admin/stats/risk-histogram", { headers: adminHeaders() });
  return data;
}

export async function fetchTopRisk(): Promise<unknown[]> {
  const { data } = await api.get<unknown[]>("/admin/stats/top-risk", { headers: adminHeaders() });
  return data;
}

export async function fetchSanctionsOverview(): Promise<Record<string, number>> {
  const { data } = await api.get<Record<string, number>>("/admin/stats/sanctions-overview", {
    headers: adminHeaders(),
  });
  return data;
}

export async function fetchNewsEntities(): Promise<unknown[]> {
  const { data } = await api.get<unknown[]>("/admin/stats/news-entities", { headers: adminHeaders() });
  return data;
}

export async function fetchAuditLog(): Promise<unknown[]> {
  const { data } = await api.get<unknown[]>("/admin/stats/audit-log", { headers: adminHeaders() });
  return data;
}

export async function fetchDependencyAudit(): Promise<unknown[]> {
  const { data } = await api.get<unknown[]>("/admin/stats/dependency-audit", {
    headers: adminHeaders(),
  });
  return data;
}

export interface ConfigKey {
  key: string;
  is_secret: boolean;
  description: string | null;
  has_value: boolean;
  updated_at: string | null;
  updated_by: string | null;
}

export async function fetchConfigKeys(): Promise<ConfigKey[]> {
  const { data } = await api.get<ConfigKey[]>("/admin/config", { headers: adminHeaders() });
  return data;
}

export async function setConfigKey(
  key: string,
  value: string,
  opts: { is_secret?: boolean; description?: string },
): Promise<void> {
  await api.put(`/admin/config/${key}`, { value, ...opts }, { headers: adminHeaders() });
}

export async function deleteConfigKey(key: string): Promise<void> {
  await api.delete(`/admin/config/${key}`, { headers: adminHeaders() });
}
