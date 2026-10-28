"""Motor de avaliação e despacho de alertas espaciais para usuários.

Monitora focos de incêndio e plumas de fumaça em um raio configurado (padrão 50 km)
em torno das coordenadas cadastradas pelos usuários.
"""

import logging
from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger("amazonwatch.alerts_engine")


def evaluate_user_alerts(db: Session) -> int:
    """Verifica focos de incêndio e fumaça próximos aos locais monitorados pelos usuários.

    Gera notificações para eventos ocorridos nas últimas 24 horas a menos de radius_km
    (padrão 50 km), evitando alertas duplicados através de chave única.
    """
    total_created = 0

    # 1. Alertas de Focos de Incêndio (raio <= radius_km, padrão 50km)
    fire_query = text(
        """
        SELECT 
            l.user_id,
            l.id AS location_id,
            l.label AS location_label,
            h.id AS entity_id,
            ROUND((ST_Distance(h.geom::geography, l.geom::geography) / 1000.0)::numeric, 1) AS distance_km,
            h.satellite,
            h.detected_at
        FROM user_monitored_locations l
        JOIN fire_hotspots h 
          ON ST_DWithin(h.geom::geography, l.geom::geography, l.radius_km * 1000.0)
        WHERE l.notify_fire = true
          AND h.detected_at >= NOW() - INTERVAL '24 hours'
          AND NOT EXISTS (
              SELECT 1 FROM alert_notifications a 
              WHERE a.location_id = l.id 
                AND a.alert_type = 'FIRE' 
                AND a.entity_id = h.id
          )
        ORDER BY h.detected_at DESC
        LIMIT 500
        """
    )

    fire_rows = db.execute(fire_query).fetchall()
    for row in fire_rows:
        try:
            insert_stmt = text(
                """
                INSERT INTO alert_notifications (
                    user_id, location_id, alert_type, title, message, distance_km, entity_id
                ) VALUES (
                    :user_id, :location_id, 'FIRE', :title, :message, :distance_km, :entity_id
                )
                ON CONFLICT (location_id, alert_type, entity_id) DO NOTHING
                """
            )
            dist = float(row.distance_km)
            det_str = row.detected_at.strftime("%d/%m %H:%M UTC") if row.detected_at else "recente"
            title = f"Incêndio a {dist:.1f} km de {row.location_label}"
            message = (
                f"Satélite {row.satellite} detectou foco de calor a {dist:.1f} km da sua localização "
                f"monitorada '{row.location_label}' em {det_str}."
            )
            db.execute(
                insert_stmt,
                {
                    "user_id": row.user_id,
                    "location_id": row.location_id,
                    "title": title,
                    "message": message,
                    "distance_km": dist,
                    "entity_id": row.entity_id,
                },
            )
            total_created += 1
        except Exception as e:
            log.warning("Falha ao criar alerta de incêndio: %s", e)

    # 2. Alertas de Plumas de Fumaça (raio <= radius_km, padrão 50km ou interseção)
    smoke_query = text(
        """
        SELECT 
            l.user_id,
            l.id AS location_id,
            l.label AS location_label,
            p.id AS entity_id,
            ROUND((ST_Distance(p.geom::geography, l.geom::geography) / 1000.0)::numeric, 1) AS distance_km,
            p.area_km2,
            p.scan_time
        FROM user_monitored_locations l
        JOIN smoke_plumes p 
          ON ST_DWithin(p.geom::geography, l.geom::geography, l.radius_km * 1000.0)
        WHERE l.notify_smoke = true
          AND p.scan_time >= NOW() - INTERVAL '24 hours'
          AND NOT EXISTS (
              SELECT 1 FROM alert_notifications a 
              WHERE a.location_id = l.id 
                AND a.alert_type = 'SMOKE' 
                AND a.entity_id = p.id
          )
        ORDER BY p.scan_time DESC
        LIMIT 500
        """
    )

    smoke_rows = db.execute(smoke_query).fetchall()
    for row in smoke_rows:
        try:
            insert_stmt = text(
                """
                INSERT INTO alert_notifications (
                    user_id, location_id, alert_type, title, message, distance_km, entity_id
                ) VALUES (
                    :user_id, :location_id, 'SMOKE', :title, :message, :distance_km, :entity_id
                )
                ON CONFLICT (location_id, alert_type, entity_id) DO NOTHING
                """
            )
            dist = float(row.distance_km)
            area = float(row.area_km2) if row.area_km2 else 0.0
            scan_str = row.scan_time.strftime("%d/%m %H:%M UTC") if row.scan_time else "recente"
            if dist <= 1.0:
                title = f"Fumaça cobrindo a região de {row.location_label}"
                message = f"Pluma de fumaça densa ({area:.0f} km²) cobrindo '{row.location_label}' em {scan_str}."
            else:
                title = f"Fumaça a {dist:.1f} km de {row.location_label}"
                message = (
                    f"Pluma de fumaça ({area:.0f} km²) detectada a {dist:.1f} km de '{row.location_label}' em {scan_str}."
                )

            db.execute(
                insert_stmt,
                {
                    "user_id": row.user_id,
                    "location_id": row.location_id,
                    "title": title,
                    "message": message,
                    "distance_km": dist,
                    "entity_id": row.entity_id,
                },
            )
            total_created += 1
        except Exception as e:
            log.warning("Falha ao criar alerta de fumaça: %s", e)

    db.commit()
    return total_created
