export interface HotspotProps {
  id: number;
  detected_at: string;
  satellite: string;
  in_region: boolean;
}

export interface PlumeProps {
  id: number;
  scan_time: string;
  area_km2: number;
  pixel_count: number;
  confidence: number;
  hotspots_count: number;
  origins_count: number;
}

export interface PlumeHotspotLink {
  hotspot_id: number;
  lat: number;
  lon: number;
  distance_km: number;
  age_minutes: number;
  cluster_id: number;
  score: number;
  is_origin: boolean;
  detected_at: string;
  satellite: string;
}

export interface PlumeDetail {
  id: number;
  scan_time: string;
  area_km2: number;
  pixel_count: number;
  confidence: number;
  geometry: any;
  centroid: any;
  links: PlumeHotspotLink[];
}

/** Pedido de enquadramento do mapa numa pluma (botão "Aproximar no mapa"). */
export interface FocusRequest {
  plume: PlumeDetail;
  nonce: number; // muda a cada clique para refocar mesmo na mesma pluma
}

export interface SatelliteFrame {
  id: number;
  scan_time: string;
  product: string;
  image_url: string;
  west: number;
  south: number;
  east: number;
  north: number;
}

export interface StatsSummary {
  total_hotspots: number;
  total_plumes: number;
  total_smoke_area_km2: number;
  active_origins: number;
  latest_scan_time: string | null;
}
