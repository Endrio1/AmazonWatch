"""Projeção fixa do GOES-R ABI (geoestacionária) e utilitários de grade."""

from dataclasses import dataclass
from functools import cached_property

import numpy as np
from pyproj import CRS, Transformer
from shapely.geometry.base import BaseGeometry

# Grade Full Disk de 2 km do ABI: 5424 x 5424 pixels de 56 µrad.
FD_SIZE = 5424
FD_PIXEL_RAD = 5.6e-5
FD_HALF_EXTENT_RAD = FD_SIZE * FD_PIXEL_RAD / 2  # 0.151872 rad


@dataclass(frozen=True)
class GeosProjection:
    """Parâmetros da projeção `goes_imager_projection`."""

    lon_0: float = -75.0
    h: float = 35786023.0
    a: float = 6378137.0
    b: float = 6356752.31414
    sweep: str = "x"

    @classmethod
    def from_attrs(cls, attrs: dict) -> "GeosProjection":
        return cls(
            lon_0=float(attrs["longitude_of_projection_origin"]),
            h=float(attrs["perspective_point_height"]),
            a=float(attrs["semi_major_axis"]),
            b=float(attrs["semi_minor_axis"]),
            sweep=str(attrs.get("sweep_angle_axis", "x")),
        )

    @cached_property
    def crs(self) -> CRS:
        return CRS.from_proj4(
            f"+proj=geos +h={self.h} +lon_0={self.lon_0} +sweep={self.sweep} "
            f"+a={self.a} +b={self.b} +units=m +no_defs"
        )

    @cached_property
    def to_geos(self) -> Transformer:
        return Transformer.from_crs("EPSG:4326", self.crs, always_xy=True)

    @cached_property
    def to_lonlat(self) -> Transformer:
        return Transformer.from_crs(self.crs, "EPSG:4326", always_xy=True)

    def region_bounds_m(self, geom: BaseGeometry, margin_deg: float = 0.0) -> tuple[float, float, float, float]:
        """Envelope (xmin, ymin, xmax, ymax) em metros geoestacionários de uma geometria lon/lat.

        Amostra densamente a borda do envelope expandido, pois um retângulo lon/lat
        não é retangular na projeção geoestacionária.
        """
        w, s, e, n = geom.bounds
        w, s, e, n = w - margin_deg, s - margin_deg, e + margin_deg, n + margin_deg
        t = np.linspace(0, 1, 200)
        lons = np.concatenate([w + (e - w) * t, np.full_like(t, e), e - (e - w) * t, np.full_like(t, w)])
        lats = np.concatenate([np.full_like(t, s), s + (n - s) * t, np.full_like(t, n), n - (n - s) * t])
        xs, ys = self.to_geos.transform(lons, lats)
        xs, ys = np.asarray(xs), np.asarray(ys)
        ok = np.isfinite(xs) & np.isfinite(ys)
        return float(xs[ok].min()), float(ys[ok].min()), float(xs[ok].max()), float(ys[ok].max())
