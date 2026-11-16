"""Adiciona recuperação de senha e versão da sessão do usuário.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("password_reset_digest", sa.String(64)))
    op.add_column("users", sa.Column("password_reset_expires_at", sa.DateTime(timezone=True)))
    op.create_index("ix_users_password_reset_digest", "users", ["password_reset_digest"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_password_reset_digest", table_name="users")
    op.drop_column("users", "password_reset_expires_at")
    op.drop_column("users", "password_reset_digest")
    op.drop_column("users", "password_version")
