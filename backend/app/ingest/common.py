"""Utilitários comuns de ingestão: cliente HTTP e log de idempotência."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

import httpx

from app.config import get_settings
from app.models import IngestLog

USER_AGENT = "AmazonWatch/1.0 (+monitoramento de fumaca na Amazonia Legal)"


def make_client() -> httpx.Client:
    s = get_settings()
    return httpx.Client(
        timeout=httpx.Timeout(s.http_timeout_s, connect=15.0),
        transport=httpx.HTTPTransport(retries=3),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )


def processed_keys(db: Session, source: str, keys: list[str]) -> set[str]:
    """Chaves já processadas com sucesso (status ``ok`` ou ``empty``)."""
    if not keys:
        return set()
    rows = db.scalars(
        select(IngestLog.file_key).where(
            IngestLog.source == source,
            IngestLog.file_key.in_(keys),
            IngestLog.status.in_(("ok", "empty")),
        )
    )
    return set(rows)


def mark(db: Session, source: str, key: str, status: str, message: str | None = None) -> None:
    stmt = insert(IngestLog).values(source=source, file_key=key, status=status, message=message)
    stmt = stmt.on_conflict_do_update(
        index_elements=[IngestLog.source, IngestLog.file_key],
        set_={"status": status, "message": message, "processed_at": stmt.excluded.processed_at},
    )
    db.execute(stmt)
