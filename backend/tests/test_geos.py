"""Testes unitários da projeção geoestacionária GOES."""

import numpy as np
from shapely.geometry import box

from app.processing.geos import GeosProjection


def test_geos_roundtrip():
    proj = GeosProjection()
    lons = [-60.0, -55.0, -50.0]
    lats = [-5.0, 0.0, 2.0]

    xs, ys = proj.to_geos.transform(lons, lats)
    assert len(xs) == 3
    assert not any(np.isnan(xs))

    # Converte de volta para lon/lat
    lons_back, lats_back = proj.to_lonlat.transform(xs, ys)
    np.testing.assert_allclose(lons_back, lons, atol=1e-5)
    np.testing.assert_allclose(lats_back, lats, atol=1e-5)


def test_region_bounds_m():
    proj = GeosProjection()
    geom = box(-70.0, -10.0, -50.0, 0.0)
    xmin, ymin, xmax, ymax = proj.region_bounds_m(geom, margin_deg=0.5)

    assert xmin < xmax
    assert ymin < ymax
    # Verifica que o ponto central está dentro dos limites
    cx, cy = proj.to_geos.transform(-60.0, -5.0)
    assert xmin <= cx <= xmax
    assert ymin <= cy <= ymax
