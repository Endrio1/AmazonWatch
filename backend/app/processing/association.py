"""Associação entre plumas de fumaça e focos de incêndio.

Metodologia
-----------
Para cada pluma (scan ``t``):

1. **Candidatos**: focos detectados em ``[t - janela_antes, t + janela_depois]`` que estão
   dentro da pluma ou a até ``max_distance_km`` de sua borda (PostGIS, geografia).
2. **Agrupamento**: os candidatos são agrupados com ``ST_ClusterDBSCAN`` (eps em km,
   projeção SIRGAS 2000 / Brazil Polyconic, EPSG:5880). Detecções repetidas do mesmo
   incêndio (vários satélites / passagens) caem no mesmo grupo.
3. **Score por foco**: ``exp(-d / D0) * exp(-|Δt| / T0)``, onde ``d`` é a distância à
   pluma (0 se dentro) e ``Δt`` a diferença de tempo para o scan.
4. **Score do grupo**: soma dos scores dos focos (incêndios persistentes e intensos
   pesam mais). O grupo de maior score é a **origem provável**; grupos com score
   ≥ ``rel_threshold`` × máximo (até ``max_origin_clusters``) também são marcados
   como origem, pois grandes plumas costumam ter várias fontes.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import PlumeFireLink, SmokePlume


@dataclass(frozen=True)
class Candidate:
    hotspot_id: int
    distance_km: float
    age_minutes: float  # positivo = foco anterior ao scan
    cluster_id: int


@dataclass(frozen=True)
class AssociationParams:
    distance_scale_km: float = 10.0
    age_scale_hours: float = 3.0
    rel_threshold: float = 0.5
    max_origin_clusters: int = 3

    @classmethod
    def from_settings(cls, s: Settings) -> "AssociationParams":
        return cls(
            distance_scale_km=s.assoc_distance_scale_km,
            age_scale_hours=s.assoc_age_scale_hours,
            rel_threshold=s.assoc_origin_rel_threshold,
            max_origin_clusters=s.assoc_max_origin_clusters,
        )


@dataclass(frozen=True)
class LinkResult:
    candidate: Candidate
    score: float
    is_origin: bool


def hotspot_score(c: Candidate, p: AssociationParams) -> float:
    d = max(c.distance_km, 0.0)
    age_h = abs(c.age_minutes) / 60.0
    return math.exp(-d / p.distance_scale_km) * math.exp(-age_h / p.age_scale_hours)


def score_candidates(candidates: list[Candidate], params: AssociationParams) -> list[LinkResult]:
    """Calcula scores e marca os grupos de origem. Função pura (testável sem banco)."""
    if not candidates:
        return []
    scores = {c.hotspot_id: hotspot_score(c, params) for c in candidates}
    cluster_score: dict[int, float] = {}
    for c in candidates:
        cluster_score[c.cluster_id] = cluster_score.get(c.cluster_id, 0.0) + scores[c.hotspot_id]

    ranked = sorted(cluster_score.items(), key=lambda kv: kv[1], reverse=True)
    best = ranked[0][1]
    origin_clusters = {
        cid for cid, sc in ranked[: params.max_origin_clusters] if sc >= params.rel_threshold * best
    }
    return [
        LinkResult(candidate=c, score=scores[c.hotspot_id], is_origin=c.cluster_id in origin_clusters)
        for c in candidates
    ]


_CANDIDATES_SQL = text(
    """
    WITH p AS (
        SELECT id, geom, geom::geography AS geog, scan_time FROM smoke_plumes WHERE id = :plume_id
    ),
    c AS (
        SELECT h.id AS hotspot_id,
               h.geom,
               ST_Distance(h.geom::geography, p.geog) / 1000.0 AS distance_km,
               EXTRACT(EPOCH FROM (p.scan_time - h.detected_at)) / 60.0 AS age_minutes
        FROM fire_hotspots h, p
        WHERE h.detected_at BETWEEN p.scan_time - make_interval(secs => :before_s)
                                AND p.scan_time + make_interval(secs => :after_s)
          AND h.geom && ST_Expand(p.geom, :expand_deg)
          AND ST_DWithin(h.geom::geography, p.geog, :max_m)
    )
    SELECT hotspot_id, distance_km, age_minutes,
           ST_ClusterDBSCAN(ST_Transform(geom, 5880), eps := :eps_m, minpoints := 1) OVER () AS cluster_id
    FROM c
    """
)


def find_candidates(db: Session, plume_id: int, s: Settings) -> list[Candidate]:
    rows = db.execute(
        _CANDIDATES_SQL,
        {
            "plume_id": plume_id,
            "before_s": s.assoc_window_before_hours * 3600,
            "after_s": s.assoc_window_after_minutes * 60,
            "expand_deg": s.assoc_max_distance_km / 100.0,
            "max_m": s.assoc_max_distance_km * 1000.0,
            "eps_m": s.assoc_cluster_eps_km * 1000.0,
        },
    ).all()
    return [
        Candidate(
            hotspot_id=r.hotspot_id,
            distance_km=float(r.distance_km),
            age_minutes=float(r.age_minutes),
            cluster_id=int(r.cluster_id),
        )
        for r in rows
    ]


def associate_plume(db: Session, plume_id: int, s: Settings) -> int:
    """(Re)calcula os vínculos de uma pluma. Retorna o número de focos vinculados."""
    db.execute(delete(PlumeFireLink).where(PlumeFireLink.plume_id == plume_id))
    results = score_candidates(find_candidates(db, plume_id, s), AssociationParams.from_settings(s))
    db.add_all(
        PlumeFireLink(
            plume_id=plume_id,
            hotspot_id=r.candidate.hotspot_id,
            distance_km=r.candidate.distance_km,
            age_minutes=r.candidate.age_minutes,
            cluster_id=r.candidate.cluster_id,
            score=r.score,
            is_origin=r.is_origin,
        )
        for r in results
    )
    return len(results)


def reassociate_recent(db: Session, s: Settings) -> int:
    """Recalcula plumas recentes: focos chegam com atraso (~20–30 min) em relação ao ADP."""
    since = datetime.now(timezone.utc) - timedelta(hours=s.assoc_recompute_hours)
    ids = db.scalars(select(SmokePlume.id).where(SmokePlume.scan_time >= since)).all()
    for pid in ids:
        associate_plume(db, pid, s)
    return len(ids)
