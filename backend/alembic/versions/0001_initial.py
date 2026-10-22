"""Schema inicial do AmazonWatch.

Revision ID: 0001
Revises:
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "fire_hotspots",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("geom", Geometry("POINT", srid=4326, spatial_index=False), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("satellite", sa.String(32), nullable=False),
        sa.Column("in_region", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("source_file", sa.String(64)),
        sa.UniqueConstraint("satellite", "detected_at", "lat", "lon", name="uq_hotspot"),
    )
    op.create_index("ix_fire_hotspots_detected_at", "fire_hotspots", ["detected_at"])
    op.create_index("idx_fire_hotspots_geom", "fire_hotspots", ["geom"], postgresql_using="gist")

    op.create_table(
        "smoke_scans",
        sa.Column("scan_time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("source_file", sa.String(160), nullable=False),
        sa.Column("smoke_pixels", sa.Integer, nullable=False, server_default="0"),
        sa.Column("plume_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "smoke_plumes",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "scan_time",
            sa.DateTime(timezone=True),
            sa.ForeignKey("smoke_scans.scan_time", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("geom", Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False),
        sa.Column("centroid", Geometry("POINT", srid=4326, spatial_index=False), nullable=False),
        sa.Column("area_km2", sa.Float, nullable=False),
        sa.Column("pixel_count", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
    )
    op.create_index("ix_smoke_plumes_scan_time", "smoke_plumes", ["scan_time"])
    op.create_index("idx_smoke_plumes_geom", "smoke_plumes", ["geom"], postgresql_using="gist")

    op.create_table(
        "plume_fire_links",
        sa.Column(
            "plume_id", sa.BigInteger, sa.ForeignKey("smoke_plumes.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column(
            "hotspot_id", sa.BigInteger, sa.ForeignKey("fire_hotspots.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("distance_km", sa.Float, nullable=False),
        sa.Column("age_minutes", sa.Float, nullable=False),
        sa.Column("cluster_id", sa.Integer, nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("is_origin", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_plume_fire_links_hotspot", "plume_fire_links", ["hotspot_id"])

    op.create_table(
        "satellite_frames",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scan_time", sa.DateTime(timezone=True), nullable=False, unique=True),
        sa.Column("product", sa.String(64), nullable=False),
        sa.Column("file_path", sa.String(255), nullable=False),
        sa.Column("west", sa.Float, nullable=False),
        sa.Column("south", sa.Float, nullable=False),
        sa.Column("east", sa.Float, nullable=False),
        sa.Column("north", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "ingest_log",
        sa.Column("source", sa.String(32), primary_key=True),
        sa.Column("file_key", sa.String(255), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("message", sa.Text),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in ("ingest_log", "satellite_frames", "plume_fire_links", "smoke_plumes", "smoke_scans", "fire_hotspots"):
        op.drop_table(table)
