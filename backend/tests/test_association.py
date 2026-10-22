"""Testes unitários da lógica de associação e scoring de focos com plumas."""

from app.processing.association import (
    AssociationParams,
    Candidate,
    hotspot_score,
    score_candidates,
)


def test_hotspot_score_decay():
    params = AssociationParams(distance_scale_km=10.0, age_scale_hours=3.0)

    # Foco dentro da pluma (distância 0) e detectado exatamente no momento do scan
    c0 = Candidate(hotspot_id=1, distance_km=0.0, age_minutes=0.0, cluster_id=1)
    s0 = hotspot_score(c0, params)
    assert abs(s0 - 1.0) < 1e-4

    # Foco a 10 km (1 scale de distância) deve decair em 1/e ≈ 0.3678
    c1 = Candidate(hotspot_id=2, distance_km=10.0, age_minutes=0.0, cluster_id=1)
    s1 = hotspot_score(c1, params)
    assert abs(s1 - (1.0 / 2.71828)) < 0.01

    # Foco a 3 horas de diferença (1 scale de tempo)
    c2 = Candidate(hotspot_id=3, distance_km=0.0, age_minutes=180.0, cluster_id=1)
    s2 = hotspot_score(c2, params)
    assert abs(s2 - (1.0 / 2.71828)) < 0.01


def test_score_candidates_cluster_origin():
    params = AssociationParams(
        distance_scale_km=10.0,
        age_scale_hours=3.0,
        rel_threshold=0.5,
        max_origin_clusters=2,
    )

    # Cluster 1: 3 focos ativos muito próximos (alto score combinado)
    c1a = Candidate(hotspot_id=10, distance_km=0.0, age_minutes=10.0, cluster_id=1)
    c1b = Candidate(hotspot_id=11, distance_km=1.0, age_minutes=20.0, cluster_id=1)
    c1c = Candidate(hotspot_id=12, distance_km=2.0, age_minutes=5.0, cluster_id=1)

    # Cluster 2: 1 foco mais distante e antigo (menor score)
    c2 = Candidate(hotspot_id=20, distance_km=20.0, age_minutes=180.0, cluster_id=2)

    results = score_candidates([c1a, c1b, c1c, c2], params)
    assert len(results) == 4

    by_id = {r.candidate.hotspot_id: r for r in results}
    # Focos do cluster 1 devem ser marcados como origem
    assert by_id[10].is_origin is True
    assert by_id[11].is_origin is True
    assert by_id[12].is_origin is True

    # Foco do cluster 2 não deve ser marcado como origem
    assert by_id[20].is_origin is False
    assert by_id[10].score > by_id[20].score
