"""Rotas de consulta a focos de incêndio (BDQueimadas)."""

import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import FireHotspot
from app.schemas import HotspotFeature, HotspotGeoJSON, HotspotProps

router = APIRouter(prefix="/hotspots", tags=["hotspots"])


@router.get("", response_model=HotspotGeoJSON)
def list_hotspots(
    start: Annotated[datetime | None, Query(description="Início do intervalo (ISO)")] = None,
    end: Annotated[datetime | None, Query(description="Fim do intervalo (ISO)")] = None,
    min_lat: Annotated[float | None, Query()] = None,
    max_lat: Annotated[float | None, Query()] = None,
    min_lon: Annotated[float | None, Query()] = None,
    max_lon: Annotated[float | None, Query()] = None,
    only_in_region: Annotated[bool, Query()] = True,
    limit: Annotated[int, Query(ge=1, le=10000)] = 5000,
    db: Session = Depends(get_db),
) -> HotspotGeoJSON:
    """Retorna os focos de incêndio no formato GeoJSON FeatureCollection."""
    stmt = select(
        FireHotspot.id,
        FireHotspot.detected_at,
        FireHotspot.satellite,
        FireHotspot.in_region,
        func.ST_AsGeoJSON(FireHotspot.geom).label("geojson"),
    )

    if start:
        stmt = stmt.where(FireHotspot.detected_at >= start)
    if end:
        stmt = stmt.where(FireHotspot.detected_at <= end)
    if only_in_region:
        stmt = stmt.where(FireHotspot.in_region.is_(True))

    if min_lon is not None and min_lat is not None and max_lon is not None and max_lat is not None:
        bbox_geom = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
        stmt = stmt.where(FireHotspot.geom.ST_Intersects(bbox_geom))

    stmt = stmt.order_by(FireHotspot.detected_at.desc()).limit(limit)
    rows = db.execute(stmt).all()

    features = [
        HotspotFeature(
            type="Feature",
            geometry=json.loads(r.geojson),
            properties=HotspotProps(
                id=r.id,
                detected_at=r.detected_at,
                satellite=r.satellite,
                in_region=r.in_region,
            ),
        )
        for r in rows
    ]

    return HotspotGeoJSON(type="FeatureCollection", features=features)
