"""Rotas de consulta a plumas de fumaça e suas relações de origem."""

import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import FireHotspot, PlumeFireLink, SmokePlume, SmokeScan
from app.schemas import (
    PlumeDetail,
    PlumeFeature,
    PlumeGeoJSON,
    PlumeHotspotLink,
    PlumeProps,
)

router = APIRouter(prefix="/plumes", tags=["plumes"])


@router.get("", response_model=PlumeGeoJSON)
def list_plumes(
    scan_time: Annotated[datetime | None, Query(description="Horário exato do scan")] = None,
    start: Annotated[datetime | None, Query(description="Início do intervalo (ISO)")] = None,
    end: Annotated[datetime | None, Query(description="Fim do intervalo (ISO)")] = None,
    min_area_km2: Annotated[float, Query(description="Área mínima em km²", ge=0.0)] = 5.0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 300,
    db: Session = Depends(get_db),
) -> PlumeGeoJSON:
    """Retorna plumas de fumaça poligonizadas com contagem de focos e origens."""
    stmt = (
        select(
            SmokePlume.id,
            SmokePlume.scan_time,
            SmokePlume.area_km2,
            SmokePlume.pixel_count,
            SmokePlume.confidence,
            func.ST_AsGeoJSON(SmokePlume.geom).label("geojson"),
            func.count(PlumeFireLink.hotspot_id).label("hotspots_count"),
            func.count(PlumeFireLink.hotspot_id)
            .filter(PlumeFireLink.is_origin.is_(True))
            .label("origins_count"),
        )
        .outerjoin(PlumeFireLink, SmokePlume.id == PlumeFireLink.plume_id)
        .group_by(SmokePlume.id)
    )

    if scan_time:
        stmt = stmt.where(SmokePlume.scan_time == scan_time)
    else:
        if start:
            stmt = stmt.where(SmokePlume.scan_time >= start)
        if end:
            stmt = stmt.where(SmokePlume.scan_time <= end)

    if min_area_km2 > 0:
        stmt = stmt.where(SmokePlume.area_km2 >= min_area_km2)

    stmt = stmt.order_by(SmokePlume.scan_time.desc(), SmokePlume.area_km2.desc()).limit(limit)
    rows = db.execute(stmt).all()

    features = [
        PlumeFeature(
            type="Feature",
            geometry=json.loads(r.geojson),
            properties=PlumeProps(
                id=r.id,
                scan_time=r.scan_time,
                area_km2=round(r.area_km2, 2),
                pixel_count=r.pixel_count,
                confidence=round(r.confidence, 3),
                hotspots_count=int(r.hotspots_count or 0),
                origins_count=int(r.origins_count or 0),
            ),
        )
        for r in rows
    ]

    return PlumeGeoJSON(type="FeatureCollection", features=features)


@router.get("/timeline", response_model=list[datetime])
def list_timeline_timestamps(
    hours: Annotated[int, Query(ge=1, le=168)] = 6,
    db: Session = Depends(get_db),
) -> list[datetime]:
    """Retorna os horários disponíveis com scans de fumaça para a linha do tempo."""
    stmt = (
        select(SmokeScan.scan_time)
        .order_by(SmokeScan.scan_time.desc())
        .limit(hours * 6)  # 6 scans por hora
    )
    times = db.scalars(stmt).all()
    return list(reversed(times))


@router.get("/{plume_id}", response_model=PlumeDetail)
def get_plume_detail(
    plume_id: int,
    db: Session = Depends(get_db),
) -> PlumeDetail:
    """Retorna os detalhes da pluma com a lista de focos de incêndio associados e prováveis origens."""
    stmt = select(
        SmokePlume.id,
        SmokePlume.scan_time,
        SmokePlume.area_km2,
        SmokePlume.pixel_count,
        SmokePlume.confidence,
        func.ST_AsGeoJSON(SmokePlume.geom).label("geojson"),
        func.ST_AsGeoJSON(SmokePlume.centroid).label("centroid_geojson"),
    ).where(SmokePlume.id == plume_id)

    row = db.execute(stmt).first()
    if not row:
        raise HTTPException(status_code=404, detail="Pluma de fumaça não encontrada")

    # Busca os focos associados
    links_stmt = (
        select(
            PlumeFireLink.hotspot_id,
            PlumeFireLink.distance_km,
            PlumeFireLink.age_minutes,
            PlumeFireLink.cluster_id,
            PlumeFireLink.score,
            PlumeFireLink.is_origin,
            FireHotspot.lat,
            FireHotspot.lon,
            FireHotspot.detected_at,
            FireHotspot.satellite,
        )
        .join(FireHotspot, PlumeFireLink.hotspot_id == FireHotspot.id)
        .where(PlumeFireLink.plume_id == plume_id)
        .order_by(PlumeFireLink.is_origin.desc(), PlumeFireLink.score.desc())
    )

    link_rows = db.execute(links_stmt).all()

    links = [
        PlumeHotspotLink(
            hotspot_id=lr.hotspot_id,
            lat=lr.lat,
            lon=lr.lon,
            distance_km=round(lr.distance_km, 2),
            age_minutes=round(lr.age_minutes, 1),
            cluster_id=lr.cluster_id,
            score=round(lr.score, 3),
            is_origin=lr.is_origin,
            detected_at=lr.detected_at,
            satellite=lr.satellite,
        )
        for lr in link_rows
    ]

    return PlumeDetail(
        id=row.id,
        scan_time=row.scan_time,
        area_km2=round(row.area_km2, 2),
        pixel_count=row.pixel_count,
        confidence=round(row.confidence, 3),
        geometry=json.loads(row.geojson),
        centroid=json.loads(row.centroid_geojson),
        links=links,
    )
