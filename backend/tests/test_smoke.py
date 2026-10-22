"""Testes unitários da detecção e poligonização de plumas de fumaça."""

import numpy as np
from shapely.geometry import box

from app.processing.geos import GeosProjection
from app.processing.smoke import (
    extract_plumes,
    geodesic_area_km2,
    smoke_mask,
    smoke_quality,
)


def test_smoke_quality_and_mask():
    # Bitmask 0b1100: 0 = alta (0), 4 = média (0b0100), 8 = baixa (0b1000), 12 = ruim (0b1100)
    dqf = np.array([[0, 4], [8, 12]], dtype=np.uint16)
    q = smoke_quality(dqf)
    assert q[0, 0] == 0
    assert q[0, 1] == 4
    assert q[1, 0] == 8
    assert q[1, 1] == 12

    smoke = np.ones((2, 2), dtype=np.int8)

    # Filtro com 'high' deve aceitar apenas o pixel 0
    m_high = smoke_mask(smoke, dqf, min_confidence="high")
    assert m_high[0, 0] and not m_high[0, 1] and not m_high[1, 0] and not m_high[1, 1]

    # Filtro com 'medium' aceita alta e média
    m_med = smoke_mask(smoke, dqf, min_confidence="medium")
    assert m_med[0, 0] and m_med[0, 1] and not m_med[1, 0]

    # Filtro com 'low' aceita alta, média e baixa
    m_low = smoke_mask(smoke, dqf, min_confidence="low")
    assert m_low[0, 0] and m_low[0, 1] and m_low[1, 0] and not m_low[1, 1]


def test_geodesic_area():
    # Quadrilátero de 1x1 grau no equador (~111x111 km ≈ 12321 km²)
    sq = box(-60.0, 0.0, -59.0, 1.0)
    area = geodesic_area_km2(sq)
    assert 12000 < area < 12500


def test_extract_plumes_synthetic():
    proj = GeosProjection()
    h = proj.h
    cx, cy = proj.to_geos.transform(-60.0, -5.0)

    # Cria grade sintética 50x50 com pixel de 2 km
    res = 2000.0
    x_m = cx + (np.arange(50) - 25) * res
    y_m = cy + (25 - np.arange(50)) * res

    smoke = np.zeros((50, 50), dtype=np.int8)
    dqf = np.zeros((50, 50), dtype=np.uint16)

    # Bloco 1: 5x5 pixels de fumaça alta confiança (25 pixels >= 10 mínimo)
    smoke[10:15, 10:15] = 1
    dqf[10:15, 10:15] = 0

    # Bloco 2: 2x2 pixels (4 pixels < 10 mínimo -> deve ser filtrado como ruído)
    smoke[35:37, 35:37] = 1
    dqf[35:37, 35:37] = 0

    plumes, total_px = extract_plumes(
        smoke=smoke,
        dqf=dqf,
        x_m=x_m,
        y_m=y_m,
        proj=proj,
        region=None,
        min_pixels=10,
        simplify_deg=0.001,
    )

    assert total_px == 29
    assert len(plumes) == 1
    p = plumes[0]
    assert p.pixel_count == 25
    assert p.confidence == 1.0
    # 25 pixels de 2x2 km = ~100 km²
    assert 80.0 <= p.area_km2 <= 120.0
