import axios from "axios";
import type { ReviewQueueItem, SanctionsMatch } from "../types";

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

export async function fetchVesselSanctions(imo: number): Promise<SanctionsMatch[]> {
  const { data } = await api.get<SanctionsMatch[]>(`/sanctions/vessel/${imo}`);
  return data;
}

export async function fetchReviewQueue(
  status: "open" | "confirmed" | "rejected" | "all" = "open"
): Promise<ReviewQueueItem[]> {
  const adminToken = import.meta.env.VITE_ADMIN_TOKEN ?? "";
  const { data } = await api.get<ReviewQueueItem[]>("/sanctions/review-queue", {
    params: { status },
    headers: { "X-Admin-Token": adminToken },
  });
  return data;
}

export async function confirmReviewItem(id: number): Promise<void> {
  const adminToken = import.meta.env.VITE_ADMIN_TOKEN ?? "";
  await api.post(`/sanctions/review-queue/${id}/confirm`, null, {
    headers: { "X-Admin-Token": adminToken },
  });
}

export async function rejectReviewItem(id: number): Promise<void> {
  const adminToken = import.meta.env.VITE_ADMIN_TOKEN ?? "";
  await api.post(`/sanctions/review-queue/${id}/reject`, null, {
    headers: { "X-Admin-Token": adminToken },
  });
}
