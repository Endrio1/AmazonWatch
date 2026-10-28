"""Endpoints de gerenciamento de locais monitorados e alertas de fogo/fumaça."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.elements import WKTElement
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import AlertNotification, User, UserMonitoredLocation
from app.schemas import AlertNotificationOut, LocationCreate, LocationOut

router = APIRouter(prefix="/user", tags=["user_alerts"])


@router.get("/locations", response_model=list[LocationOut])
def list_locations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista todas as localizações monitoradas pelo usuário autenticado."""
    locations = (
        db.query(UserMonitoredLocation)
        .filter(UserMonitoredLocation.user_id == current_user.id)
        .order_by(UserMonitoredLocation.created_at.desc())
        .all()
    )
    return [LocationOut.model_validate(loc) for loc in locations]


@router.post("/locations", response_model=LocationOut, status_code=status.HTTP_201_CREATED)
def create_location(
    payload: LocationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Adiciona uma nova localização de interesse (raio padrão 50 km)."""
    if not payload.label.strip():
        raise HTTPException(status_code=400, detail="O nome do local é obrigatório")

    # Garante raio mínimo e máximo razoável (padrão 50 km)
    radius = max(5.0, min(float(payload.radius_km), 200.0))

    geom = WKTElement(f"POINT({payload.lon} {payload.lat})", srid=4326)

    location = UserMonitoredLocation(
        user_id=current_user.id,
        label=payload.label.strip(),
        lat=payload.lat,
        lon=payload.lon,
        geom=geom,
        radius_km=radius,
        notify_fire=payload.notify_fire,
        notify_smoke=payload.notify_smoke,
    )
    db.add(location)
    db.commit()
    db.refresh(location)

    # Avalia imediatamente para identificar focos ou plumas já existentes no raio
    try:
        from app.processing.alerts_engine import evaluate_user_alerts
        evaluate_user_alerts(db)
    except Exception:
        pass

    return LocationOut.model_validate(location)



@router.delete("/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_location(
    location_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove uma localização monitorada."""
    location = (
        db.query(UserMonitoredLocation)
        .filter(
            UserMonitoredLocation.id == location_id,
            UserMonitoredLocation.user_id == current_user.id,
        )
        .first()
    )
    if not location:
        raise HTTPException(status_code=404, detail="Localização não encontrada")

    db.delete(location)
    db.commit()


@router.get("/notifications", response_model=list[AlertNotificationOut])
def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista alertas de incêndio (<50km) e fumaça para o usuário autenticado."""
    query = (
        db.query(AlertNotification, UserMonitoredLocation.label.label("location_label"))
        .join(UserMonitoredLocation, AlertNotification.location_id == UserMonitoredLocation.id)
        .filter(AlertNotification.user_id == current_user.id)
    )

    if unread_only:
        query = query.filter(AlertNotification.read_at.is_(None))

    query = query.order_by(AlertNotification.created_at.desc()).limit(limit)

    results = []
    for alert, loc_label in query.all():
        item = AlertNotificationOut(
            id=alert.id,
            location_id=alert.location_id,
            location_label=loc_label,
            alert_type=alert.alert_type,
            title=alert.title,
            message=alert.message,
            distance_km=round(alert.distance_km, 1),
            entity_id=alert.entity_id,
            read_at=alert.read_at,
            created_at=alert.created_at,
        )
        results.append(item)
    return results


@router.patch("/notifications/{notification_id}/read", response_model=AlertNotificationOut)
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Marca uma notificação como lida."""
    alert = (
        db.query(AlertNotification)
        .filter(
            AlertNotification.id == notification_id,
            AlertNotification.user_id == current_user.id,
        )
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")

    if not alert.read_at:
        alert.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(alert)

    loc = db.query(UserMonitoredLocation).filter(UserMonitoredLocation.id == alert.location_id).first()
    return AlertNotificationOut(
        id=alert.id,
        location_id=alert.location_id,
        location_label=loc.label if loc else None,
        alert_type=alert.alert_type,
        title=alert.title,
        message=alert.message,
        distance_km=round(alert.distance_km, 1),
        entity_id=alert.entity_id,
        read_at=alert.read_at,
        created_at=alert.created_at,
    )


@router.post("/notifications/mark-all-read")
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Marca todas as notificações do usuário como lidas."""
    now = datetime.now(timezone.utc)
    updated = (
        db.query(AlertNotification)
        .filter(
            AlertNotification.user_id == current_user.id,
            AlertNotification.read_at.is_(None),
        )
        .update({"read_at": now})
    )
    db.commit()
    return {"updated_count": updated}
