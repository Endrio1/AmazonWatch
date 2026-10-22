"""Rotas para acesso aos quadros de imagens de satélite True Color."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import SatelliteFrame
from app.schemas import SatelliteFrameOut

router = APIRouter(prefix="/frames", tags=["frames"])


@router.get("", response_model=list[SatelliteFrameOut])
def list_frames(
    start: Annotated[datetime | None, Query(description="Início do intervalo")] = None,
    end: Annotated[datetime | None, Query(description="Fim do intervalo")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 36,
    db: Session = Depends(get_db),
) -> list[SatelliteFrameOut]:
    """Retorna os quadros de satélite disponíveis com URLs de imagem e limites geográficos."""
    stmt = select(SatelliteFrame)

    if start:
        stmt = stmt.where(SatelliteFrame.scan_time >= start)
    if end:
        stmt = stmt.where(SatelliteFrame.scan_time <= end)

    stmt = stmt.order_by(SatelliteFrame.scan_time.desc()).limit(limit)
    frames = db.scalars(stmt).all()

    return [
        SatelliteFrameOut(
            id=f.id,
            scan_time=f.scan_time,
            product=f.product,
            image_url=f"/media/{f.file_path.lstrip('/')}",
            west=f.west,
            south=f.south,
            east=f.east,
            north=f.north,
        )
        for f in frames
    ]
