"""Remove plumas de versões anteriores de um mesmo scan.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A ingestão antiga atualizava plume_count e inseria a última versão com IDs maiores.
    op.execute("""
        WITH ranked_plumes AS (
            SELECT p.id, s.plume_count,
                   row_number() OVER (PARTITION BY p.scan_time ORDER BY p.id DESC) AS position
            FROM smoke_plumes p
            JOIN smoke_scans s ON s.scan_time = p.scan_time
        )
        DELETE FROM smoke_plumes p
        USING ranked_plumes r
        WHERE p.id = r.id AND r.position > r.plume_count
    """)


def downgrade() -> None:
    # Migração de dados sem mudança de esquema. Os registros removidos não são restaurados.
    pass
