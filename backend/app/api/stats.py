"""Rotas de estatísticas agregadas e métricas da Amazônia Legal."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import FireHotspot, PlumeFireLink, SmokePlume, SmokeScan
from app.schemas import StatsSummary

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=StatsSummary)
def get_stats(
    hours: Annotated[int, Query(description="Janela de tempo em horas", ge=1, le=168)] = 6,
    db: Session = Depends(get_db),
) -> StatsSummary:
    """Calcula estatísticas agregadas de focos, plumas e origens na janela solicitada."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    total_hotspots = (
        db.scalar(
            select(func.count(FireHotspot.id)).where(
                FireHotspot.detected_at >= since,
                FireHotspot.in_region.is_(True),
            )
        )
        or 0
    )

    plumes_agg = db.execute(
        select(
            func.count(SmokePlume.id).label("count"),
            func.coalesce(func.sum(SmokePlume.area_km2), 0.0).label("total_area"),
        ).where(SmokePlume.scan_time >= since)
    ).first()

    total_plumes = plumes_agg.count if plumes_agg else 0
    total_area = float(plumes_agg.total_area if plumes_agg else 0.0)

    # Contagem de focos distintos identificados como origem de alguma pluma
    active_origins = (
        db.scalar(
            select(func.count(func.distinct(PlumeFireLink.hotspot_id)))
            .join(SmokePlume, PlumeFireLink.plume_id == SmokePlume.id)
            .where(
                SmokePlume.scan_time >= since,
                PlumeFireLink.is_origin.is_(True),
            )
        )
        or 0
    )

    latest_scan = db.scalar(select(func.max(SmokeScan.scan_time)))

    return StatsSummary(
        total_hotspots=total_hotspots,
        total_plumes=total_plumes,
        total_smoke_area_km2=round(total_area, 1),
        active_origins=active_origins,
        latest_scan_time=latest_scan,
    )
