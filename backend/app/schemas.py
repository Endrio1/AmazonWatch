"""Modelos Pydantic para validação e serialização da API REST."""

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class HotspotProps(BaseModel):
    id: int
    detected_at: datetime
    satellite: str
    in_region: bool


class HotspotFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: dict[str, Any]
    properties: HotspotProps


class HotspotGeoJSON(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[HotspotFeature]


class PlumeHotspotLink(BaseModel):
    hotspot_id: int
    lat: float
    lon: float
    distance_km: float
    age_minutes: float
    cluster_id: int
    score: float
    is_origin: bool
    detected_at: datetime
    satellite: str


class PlumeProps(BaseModel):
    id: int
    scan_time: datetime
    area_km2: float
    pixel_count: int
    confidence: float
    hotspots_count: int = 0
    origins_count: int = 0


class PlumeFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: dict[str, Any]
    properties: PlumeProps


class PlumeGeoJSON(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[PlumeFeature]


class PlumeDetail(BaseModel):
    id: int
    scan_time: datetime
    area_km2: float
    pixel_count: int
    confidence: float
    geometry: dict[str, Any]
    centroid: dict[str, Any]
    links: list[PlumeHotspotLink]


class SatelliteFrameOut(BaseModel):
    id: int
    scan_time: datetime
    product: str
    image_url: str
    west: float
    south: float
    east: float
    north: float


class StatsSummary(BaseModel):
    total_hotspots: int
    total_plumes: int
    total_smoke_area_km2: float
    active_origins: int
    latest_scan_time: datetime | None


class HealthStatus(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    database_connected: bool
    last_adp_scan: datetime | None
    last_hotspot: datetime | None
    last_satellite_frame: datetime | None
    uptime_message: str | None = None
