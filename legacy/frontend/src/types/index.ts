// Minimal GeoJSON types (avoids @types/geojson dependency)
export interface GeoJsonFeatureCollection {
  type: "FeatureCollection";
  features: GeoJsonFeature[];
}

export interface GeoJsonFeature {
  type: "Feature";
  properties: Record<string, unknown> | null;
  geometry: {
    type: string;
    coordinates: unknown;
  } | null;
}

export type SupportedTimezone =
  | "America/Chicago"
  | "UTC"
  | "Asia/Singapore"
  | "__browser__";

export interface HealthResponse {
  status: string;
  db: string;
  version: string;
}

export interface VesselPosition {
  imo: number;
  mmsi?: string;
  name: string;
  flag?: string;
  flag_name?: string;
  flag_emoji?: string;
  vessel_type?: string;
  vessel_type_label?: string;
  year_built?: string;
  gross_tonnage?: number;
  lat: number;
  lon: number;
  speed_knots?: number;
  course_degrees?: number;
  heading_degrees?: number;
  nav_status?: string;
  inferred_status: "arrived" | "departing" | "incoming" | "departed" | "unknown";
  recorded_at: string; // ISO 8601 UTC
  is_shadow_fleet: boolean;
  current_sanctions_status: string;
  latest_composite_risk?: number | null;
}

export interface RiskScoreResponse {
  vessel_imo: number;
  scored_at: string;
  composite: number;
  sanctions_score: number;
  shadow_fleet_score: number;
  age_score: number;
  flag_mou_score: number;
  congestion_score: number;
  weather_score: number;
  components?: Record<string, unknown> | null;
}

export interface RiskLeaderboardItem {
  imo: number;
  name: string;
  flag?: string;
  flag_name?: string;
  flag_emoji?: string;
  vessel_type?: string;
  vessel_type_label?: string;
  composite: number;
  is_shadow_fleet: boolean;
  current_sanctions_status: string;
  scored_at: string;
}

export interface SanctionsMatch {
  id: number;
  imo: number;
  os_entity_id: string;
  match_method: string;
  status: "auto_confirmed" | "pending" | "confirmed" | "rejected";
  confidence?: number;
  created_at: string;
  reviewed_at?: string;
  entity_name?: string;
  entity_datasets: string[];
}

export interface ReviewQueueItem {
  id: number;
  imo: number;
  os_entity_id: string;
  match_method: string;
  confidence?: number;
  match_evidence?: Record<string, unknown>;
  status: "open" | "confirmed" | "rejected";
  reviewer_note?: string;
  created_at: string;
  resolved_at?: string;
}

export interface VesselDetail {
  imo: number;
  name: string;
  mmsi?: string;
  call_sign?: string;
  flag?: string;
  flag_name?: string;
  flag_emoji?: string;
  vessel_type?: string;
  vessel_type_label?: string;
  year_built?: string;
  gross_tonnage?: number;
  deadweight?: number;
  length_overall?: number;
  beam?: number;
  ism_manager?: string;
  registered_owner?: string;
  operator?: string;
  classification_society?: string;
  is_shadow_fleet: boolean;
  current_sanctions_status: string;
  first_observed_at?: string;
  last_observed_at?: string;
  last_enriched_at?: string;
  position?: VesselPosition;
  movements: Record<string, unknown>[];
}

export interface TrailPoint {
  imo: number;
  recorded_at: string;
  lat: number;
  lon: number;
  speed_knots?: number;
  heading_degrees?: number;
  inferred_status: string;
}

export type SSEEvent = "positions_updated" | "connected" | "queue_updated";

export interface NewsSummaryResponse {
  id: number;
  news_id: number;
  summary_text: string;
  model_used: string;
  generated_at_utc: string;
  tokens_in?: number | null;
  tokens_out?: number | null;
}

export interface SearchFilterSpec {
  flag_codes?: string[] | null;
  vessel_types?: string[] | null;
  sanctioned_only: boolean;
  shadow_fleet_only: boolean;
  min_risk_score?: number | null;
  max_risk_score?: number | null;
  connected_to_sanctioned_org: boolean;
  new_arrivals_only: boolean;
  min_age_years?: number | null;
  max_age_years?: number | null;
  min_gross_tonnage?: number | null;
  max_gross_tonnage?: number | null;
}

export interface NlSearchResult {
  spec: SearchFilterSpec;
  vessels: VesselPosition[];
  cached: boolean;
}
