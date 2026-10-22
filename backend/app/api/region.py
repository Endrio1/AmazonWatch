"""Rota para disponibilização do limite territorial da Amazônia Legal."""

from typing import Any
from fastapi import APIRouter
from app.region import get_region

router = APIRouter(prefix="/region", tags=["region"])


@router.get("", response_model=dict[str, Any])
def get_amazonia_legal_boundary() -> dict[str, Any]:
    """Retorna a geometria GeoJSON oficial da Amazônia Legal (IBGE)."""
    return get_region().geojson
