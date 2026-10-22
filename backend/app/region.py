"""Limite da Amazônia Legal (IBGE 2022, simplificado a ~1 km)."""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from shapely import prepared
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from app.config import get_settings

GEOJSON_PATH = Path(__file__).parent / "data" / "amazonia_legal.geojson"


@dataclass(frozen=True)
class Region:
    geojson: dict
    geometry: BaseGeometry
    prepared: prepared.PreparedGeometry
    bounds: tuple[float, float, float, float]  # west, south, east, north
    margin_bounds: tuple[float, float, float, float]

    def contains(self, lon: float, lat: float) -> bool:
        from shapely.geometry import Point

        return self.prepared.contains(Point(lon, lat))

    def in_margin_bbox(self, lon: float, lat: float) -> bool:
        w, s, e, n = self.margin_bounds
        return w <= lon <= e and s <= lat <= n


@lru_cache
def get_region() -> Region:
    data = json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))
    geom = shape(data["features"][0]["geometry"])
    m = get_settings().region_margin_deg
    w, s, e, n = geom.bounds
    return Region(
        geojson=data,
        geometry=geom,
        prepared=prepared.prep(geom),
        bounds=(w, s, e, n),
        margin_bounds=(w - m, s - m, e + m, n + m),
    )
