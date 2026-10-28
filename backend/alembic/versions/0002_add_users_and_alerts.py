"""Adiciona tabelas para cadastro de usuários, localizações monitoradas e notificações de alerta.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-23
"""

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Usuários
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 2. Localizações monitoradas pelo usuário (raio padrão 50 km)
    op.create_table(
        "user_monitored_locations",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("geom", Geometry("POINT", srid=4326, spatial_index=False), nullable=False),
        sa.Column("radius_km", sa.Float, nullable=False, server_default="50.0"),
        sa.Column("notify_fire", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("notify_smoke", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_user_monitored_locations_user_id", "user_monitored_locations", ["user_id"])
    op.create_index(
        "idx_user_monitored_locations_geom",
        "user_monitored_locations",
        ["geom"],
        postgresql_using="gist",
    )

    # 3. Notificações de alerta
    op.create_table(
        "alert_notifications",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "location_id",
            sa.BigInteger,
            sa.ForeignKey("user_monitored_locations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alert_type", sa.String(16), nullable=False),  # FIRE ou SMOKE
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("distance_km", sa.Float, nullable=False),
        sa.Column("entity_id", sa.BigInteger, nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("location_id", "alert_type", "entity_id", name="uq_alert_entity"),
    )
    op.create_index("ix_alerts_user_created", "alert_notifications", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("alert_notifications")
    op.drop_table("user_monitored_locations")
    op.drop_table("users")
