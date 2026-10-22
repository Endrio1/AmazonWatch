"""Modelos ORM (PostGIS, SRID 4326)."""

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class FireHotspot(Base):
    """Foco de calor do BDQueimadas."""

    __tablename__ = "fire_hotspots"
    __table_args__ = (
        UniqueConstraint("satellite", "detected_at", "lat", "lon", name="uq_hotspot"),
        Index("ix_fire_hotspots_detected_at", "detected_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    geom = mapped_column(Geometry("POINT", srid=4326, spatial_index=True), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    satellite: Mapped[str] = mapped_column(String(32), nullable=False)
    in_region: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_file: Mapped[str | None] = mapped_column(String(64))


class SmokeScan(Base):
    """Um scan ADP processado (mesmo que não contenha fumaça)."""

    __tablename__ = "smoke_scans"

    scan_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    source_file: Mapped[str] = mapped_column(String(160), nullable=False)
    smoke_pixels: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    plume_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SmokePlume(Base):
    """Pluma de fumaça poligonizada a partir da máscara ADP."""

    __tablename__ = "smoke_plumes"
    __table_args__ = (Index("ix_smoke_plumes_scan_time", "scan_time"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    scan_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), ForeignKey("smoke_scans.scan_time", ondelete="CASCADE"), nullable=False
    )
    geom = mapped_column(Geometry("MULTIPOLYGON", srid=4326, spatial_index=True), nullable=False)
    centroid = mapped_column(Geometry("POINT", srid=4326, spatial_index=False), nullable=False)
    area_km2: Mapped[float] = mapped_column(Float, nullable=False)
    pixel_count: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)  # fração de pixels alta/média confiança


class PlumeFireLink(Base):
    """Relação pluma ↔ foco com score de origem."""

    __tablename__ = "plume_fire_links"
    __table_args__ = (Index("ix_plume_fire_links_hotspot", "hotspot_id"),)

    plume_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("smoke_plumes.id", ondelete="CASCADE"), primary_key=True
    )
    hotspot_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("fire_hotspots.id", ondelete="CASCADE"), primary_key=True
    )
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    age_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    cluster_id: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    is_origin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SatelliteFrame(Base):
    """Imagem True Color + IR (DSAT/INPE) reprojetada para coordenadas WGS-84 da América do Sul."""

    __tablename__ = "satellite_frames"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, unique=True)
    product: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    west: Mapped[float] = mapped_column(Float, nullable=False)
    south: Mapped[float] = mapped_column(Float, nullable=False)
    east: Mapped[float] = mapped_column(Float, nullable=False)
    north: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngestLog(Base):
    """Controle de idempotência da ingestão."""

    __tablename__ = "ingest_log"

    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    file_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
