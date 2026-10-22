"""Extração de plumas de fumaça a partir da máscara ADP (ABI-L2-ADP) da NOAA.

Pipeline:
1. Seleciona pixels ``Smoke == 1`` cuja confiança (bits 2–3 do ``DQF``) atinge o mínimo.
2. Fechamento morfológico para unir fragmentos vizinhos da mesma pluma.
3. Rotulagem de componentes conectados (vizinhança-8) e descarte dos pequenos (ruído).
4. Poligonização na grade geoestacionária e reprojeção para lon/lat (EPSG:4326).
5. Mantém apenas plumas que tocam a Amazônia Legal.
"""

from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import shapely
from pyproj import Geod
from rasterio.features import shapes
from rasterio.transform import Affine
from scipy import ndimage
from shapely.geometry import MultiPolygon, Point, Polygon, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.prepared import PreparedGeometry

from app.processing.geos import GeosProjection

# Bits 2–3 do DQF do ADP: 0 = alta, 4 = média, 8 = baixa, 12 = ruim/ausente.
SMOKE_DQF_MASK = 0b1100
_ALLOWED_DQF = {
    "high": (0,),
    "medium": (0, 4),
    "low": (0, 4, 8),
}
_GEOD = Geod(ellps="WGS84")
_STRUCT8 = np.ones((3, 3), dtype=bool)


@dataclass
class PlumeGeometry:
    geometry: MultiPolygon
    centroid: Point
    area_km2: float
    pixel_count: int
    confidence: float  # fração de pixels com confiança alta ou média


def smoke_quality(dqf: np.ndarray) -> np.ndarray:
    """Retorna o código de confiança da fumaça (0, 4, 8 ou 12) por pixel."""
    return np.bitwise_and(dqf.astype(np.uint16), SMOKE_DQF_MASK)


def smoke_mask(smoke: np.ndarray, dqf: np.ndarray, min_confidence: str = "low") -> np.ndarray:
    if min_confidence not in _ALLOWED_DQF:
        raise ValueError(f"min_confidence inválido: {min_confidence!r}")
    q = smoke_quality(dqf)
    return (smoke == 1) & np.isin(q, _ALLOWED_DQF[min_confidence])


def grid_transform(x_m: np.ndarray, y_m: np.ndarray) -> Affine:
    """Affine dos centros de pixel (x crescente, y decrescente) para bordas de pixel."""
    rx = float(x_m[1] - x_m[0])
    ry = float(y_m[1] - y_m[0])
    return Affine(rx, 0.0, float(x_m[0]) - rx / 2, 0.0, ry, float(y_m[0]) - ry / 2)


def _to_multipolygon(geom: BaseGeometry) -> MultiPolygon | None:
    if geom.is_empty:
        return None
    if isinstance(geom, Polygon):
        return MultiPolygon([geom])
    if isinstance(geom, MultiPolygon):
        return geom
    polys = [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon) and not g.is_empty]
    return MultiPolygon(polys) if polys else None


def geodesic_area_km2(geom: BaseGeometry) -> float:
    area, _ = _GEOD.geometry_area_perimeter(geom)
    return abs(area) / 1e6


def extract_plumes(
    smoke: np.ndarray,
    dqf: np.ndarray,
    x_m: np.ndarray,
    y_m: np.ndarray,
    proj: GeosProjection,
    region: PreparedGeometry | None = None,
    *,
    min_confidence: str = "low",
    closing_iterations: int = 1,
    min_pixels: int = 10,
    simplify_deg: float = 0.01,
) -> tuple[list[PlumeGeometry], int]:
    """Converte a máscara de fumaça em polígonos.

    Args:
        smoke, dqf: recortes 2D (linhas = y, colunas = x) das variáveis ADP.
        x_m, y_m: coordenadas dos centros de pixel em metros geoestacionários.
        proj: projeção do arquivo.
        region: geometria preparada (lon/lat) para filtrar plumas; ``None`` mantém todas.

    Returns:
        (plumas, total de pixels de fumaça válidos no recorte)
    """
    mask = smoke_mask(smoke, dqf, min_confidence)
    total = int(mask.sum())
    if total == 0:
        return [], 0

    work = mask
    if closing_iterations > 0:
        work = ndimage.binary_closing(mask, structure=_STRUCT8, iterations=closing_iterations) | mask

    labels, n = ndimage.label(work, structure=_STRUCT8)
    if n == 0:
        return [], total
    idx = np.arange(1, n + 1)
    sizes = np.asarray(ndimage.sum(mask, labels, idx))
    good_q = mask & (smoke_quality(dqf) <= 4)
    good = np.asarray(ndimage.sum(good_q, labels, idx))

    keep = idx[sizes >= min_pixels]
    if keep.size == 0:
        return [], total
    kept = np.where(np.isin(labels, keep), labels, 0).astype(np.int32)

    transform = grid_transform(x_m, y_m)
    parts: dict[int, list[Polygon]] = defaultdict(list)
    for geojson, value in shapes(kept, mask=kept > 0, transform=transform, connectivity=8):
        parts[int(value)].append(shape(geojson))

    to_ll = proj.to_lonlat

    def _reproject(coords: np.ndarray) -> np.ndarray:
        lon, lat = to_ll.transform(coords[:, 0], coords[:, 1])
        return np.column_stack([lon, lat])

    plumes: list[PlumeGeometry] = []
    for label, polys in parts.items():
        geom_m = unary_union(polys)
        geom_ll = shapely.transform(geom_m, _reproject)
        if not geom_ll.is_valid:
            geom_ll = shapely.make_valid(geom_ll)
        if simplify_deg > 0:
            geom_ll = geom_ll.simplify(simplify_deg, preserve_topology=True)
        mp = _to_multipolygon(geom_ll)
        if mp is None:
            continue
        if region is not None and not region.intersects(mp):
            continue
        i = label - 1
        plumes.append(
            PlumeGeometry(
                geometry=mp,
                centroid=mp.centroid,
                area_km2=geodesic_area_km2(mp),
                pixel_count=int(sizes[i]),
                confidence=float(good[i] / sizes[i]) if sizes[i] else 0.0,
            )
        )

    plumes.sort(key=lambda p: p.area_km2, reverse=True)
    return plumes, total
