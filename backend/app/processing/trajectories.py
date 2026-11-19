"""Advecção horizontal aproximada com o vento observado de uma radiossondagem."""
import json
import math
from functools import lru_cache
from datetime import datetime

from pyproj import Geod
from sqlalchemy import text

GEOD = Geod(ellps="WGS84")


def wind_at_pressure(levels, pressure):
    levels = sorted({level["pressure"]: level for level in levels}.values(), key=lambda level: level["pressure"])
    for level in levels:
        if level["pressure"] == pressure:
            return level["u"], level["v"]
    for lower, upper in zip(levels, levels[1:]):
        if lower["pressure"] < pressure < upper["pressure"]:
            fraction = (pressure - lower["pressure"]) / (upper["pressure"] - lower["pressure"])
            return tuple(lower[key] + fraction * (upper[key] - lower[key]) for key in ("u", "v"))
    return None


def backward_points(lat, lon, u, v, hours):
    # O perfil é assumido constante no espaço e tempo, em pressão fixa.
    bearing = math.degrees(math.atan2(-u, -v))
    speed = math.hypot(u, v)
    points = []
    for minute in range(0, hours * 60 + 1, 10):
        x, y, _ = GEOD.fwd(lon, lat, bearing, speed * minute * 60)
        points.append(dict(lon=x, lat=y, age=-minute / 60))
    return points


@lru_cache(maxsize=2)
def load_snapshot(path, modified_ns):
    return json.loads(path.read_text())


def run_trajectories(db, plume_id, settings):
    plume = db.execute(text("""
        SELECT scan_time, ST_Y(ST_PointOnSurface(geom)) AS lat,
               ST_X(ST_PointOnSurface(geom)) AS lon
        FROM smoke_plumes WHERE id = :id
    """), {"id": plume_id}).one()
    path = settings.igra_cache_dir / "profiles.json"
    snapshot = load_snapshot(path, path.stat().st_mtime_ns)
    eligible = []
    for profile in snapshot["profiles"]:
        age = (plume.scan_time - datetime.fromisoformat(profile["time"])).total_seconds() / 3600
        distance = GEOD.inv(plume.lon, plume.lat, profile["lon"], profile["lat"])[2] / 1000
        if 0 <= age <= settings.igra_max_age_hours and distance <= settings.igra_max_station_distance_km:
            eligible.append((distance, age, profile))
    for _, _, profile in sorted(eligible, key=lambda item: (item[0], item[1])):
        points = []
        for pressure in settings.igra_pressure_levels_hpa:
            wind = wind_at_pressure(profile["levels"], pressure)
            if wind is not None:
                points.extend(backward_points(plume.lat, plume.lon, *wind, settings.igra_duration_hours))
        if points:
            return points
    raise ValueError("Sem sondagem IGRA recente e próxima com vento nos níveis solicitados")


TRAJECTORY_CANDIDATES = text("""
WITH p AS (SELECT geom, scan_time FROM smoke_plumes WHERE id = :id),
points AS (
 SELECT ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography AS geog,
        age FROM jsonb_to_recordset(CAST(:points AS jsonb)) AS x(lon float, lat float, age float)
), candidates AS (
 SELECT h.id AS hotspot_id, h.geom,
        ST_Distance(h.geom::geography, p.geom::geography)/1000 AS distance_km,
        EXTRACT(EPOCH FROM (p.scan_time-h.detected_at))/60 AS age_minutes,
        MAX(EXP(-ST_Distance(h.geom::geography, points.geog)/:scale_m)
          * EXP(-ABS(EXTRACT(EPOCH FROM (h.detected_at-p.scan_time))-points.age*3600)/:time_s)) AS transport_score
 FROM fire_hotspots h CROSS JOIN p CROSS JOIN points
 WHERE h.detected_at BETWEEN p.scan_time - make_interval(hours => :hours) AND p.scan_time
   AND ABS(EXTRACT(EPOCH FROM (h.detected_at-p.scan_time))-points.age*3600) <= :tolerance_s
   AND ST_DWithin(h.geom::geography, points.geog, :radius_m)
 GROUP BY h.id, h.geom, p.geom, p.scan_time
)
SELECT *, ST_ClusterDBSCAN(ST_Transform(geom, 5880), eps := :eps_m, minpoints := 1) OVER () AS cluster_id
FROM candidates
""")


def trajectory_candidates(db, plume_id, settings):
    points = run_trajectories(db, plume_id, settings)
    return db.execute(TRAJECTORY_CANDIDATES, dict(
        id=plume_id, points=json.dumps(points), hours=settings.igra_duration_hours,
        scale_m=settings.assoc_distance_scale_km * 1000,
        time_s=settings.assoc_age_scale_hours * 3600,
        tolerance_s=settings.igra_time_tolerance_minutes * 60,
        radius_m=settings.igra_corridor_km * 1000,
        eps_m=settings.assoc_cluster_eps_km * 1000,
    )).all()
