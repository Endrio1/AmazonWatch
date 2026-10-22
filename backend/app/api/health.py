"""Rota de verificação de integridade (health check)."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import FireHotspot, SatelliteFrame, SmokeScan
from app.schemas import HealthStatus

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthStatus)
def health_check(db: Session = Depends(get_db)) -> HealthStatus:
    db_ok = False
    last_adp = None
    last_hotspot = None
    last_frame = None

    try:
        db.execute(text("SELECT 1"))
        db_ok = True
        last_adp = db.scalar(select(func.max(SmokeScan.scan_time)))
        last_hotspot = db.scalar(select(func.max(FireHotspot.detected_at)))
        last_frame = db.scalar(select(func.max(SatelliteFrame.scan_time)))
    except Exception as e:
        return HealthStatus(
            status="unhealthy",
            database_connected=False,
            last_adp_scan=None,
            last_hotspot=None,
            last_satellite_frame=None,
            uptime_message=f"Falha de conexão ao banco de dados: {e}",
        )

    status_str = "healthy" if db_ok else "unhealthy"
    return HealthStatus(
        status=status_str,
        database_connected=db_ok,
        last_adp_scan=last_adp,
        last_hotspot=last_hotspot,
        last_satellite_frame=last_frame,
        uptime_message="AmazonWatch API operacional",
    )
