import axios from "axios";
import type { GeoJsonFeatureCollection, TrailPoint, VesselDetail, VesselPosition } from "../types";

const api = axios.create({ baseURL: "/api" });

export async function fetchPositions(): Promise<VesselPosition[]> {
  const { data } = await api.get<VesselPosition[]>("/vessels/positions");
  return data;
}

export async function fetchVesselDetail(imo: number): Promise<VesselDetail> {
  const { data } = await api.get<VesselDetail>(`/vessels/${imo}`);
  return data;
}

export async function fetchVesselTrail(imo: number): Promise<TrailPoint[]> {
  const { data } = await api.get<TrailPoint[]>(`/history/trail/${imo}`);
  return data;
}

export async function fetchGeoLayer(layerName: string): Promise<GeoJsonFeatureCollection> {
  const { data } = await api.get<GeoJsonFeatureCollection>(`/geo/layer/${layerName}`);
  return data;
}

export async function fetchGeoLayerNames(): Promise<string[]> {
  const { data } = await api.get<string[]>("/geo/layers");
  return data;
}
