"""Ingestão dos focos de calor do BDQueimadas (INPE) — arquivos CSV de 10 minutos.

Fonte: https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/10min/
Formato: ``lat,lon,satelite,data`` com horário em UTC.
"""

import csv
import io
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import Settings
from app.ingest.common import mark, processed_keys
from app.models import FireHotspot
from app.region import Region

log = logging.getLogger(__name__)
SOURCE = "bdqueimadas"
FILE_RE = re.compile(r"focos_10min_(\d{8})_(\d{4})\.csv")


@dataclass(frozen=True)
class HotspotRecord:
    lat: float
    lon: float
    satellite: str
    detected_at: datetime


def parse_file_time(name: str) -> datetime | None:
    m = FILE_RE.fullmatch(name)
    if not m:
        return None
    return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M").replace(tzinfo=timezone.utc)


def list_files(html: str) -> list[tuple[str, datetime]]:
    """Extrai (nome, horário) da listagem do diretório, ordenado por horário."""
    found = {m.group(0) for m in FILE_RE.finditer(html)}
    out = [(name, t) for name in found if (t := parse_file_time(name)) is not None]
    return sorted(out, key=lambda x: x[1])


def parse_csv(content: str) -> list[HotspotRecord]:
    """Lê o CSV de focos, ignorando linhas malformadas."""
    records: list[HotspotRecord] = []
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames:
        reader.fieldnames = [f.strip().lower() for f in reader.fieldnames]
    for row in reader:
        try:
            lat = float(row["lat"].strip())
            lon = float(row["lon"].strip())
            sat = row["satelite"].strip()
            dt = datetime.strptime(row["data"].strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError, AttributeError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180) or not sat:
            continue
        records.append(HotspotRecord(lat=lat, lon=lon, satellite=sat[:32], detected_at=dt))
    return records


def store_records(db: Session, records: list[HotspotRecord], region: Region, source_file: str) -> int:
    rows = [
        {
            "lat": r.lat,
            "lon": r.lon,
            "geom": f"SRID=4326;POINT({r.lon} {r.lat})",
            "detected_at": r.detected_at,
            "satellite": r.satellite,
            "in_region": region.contains(r.lon, r.lat),
            "source_file": source_file,
        }
        for r in records
        if region.in_margin_bbox(r.lon, r.lat)
    ]
    if not rows:
        return 0
    stmt = insert(FireHotspot).on_conflict_do_nothing(constraint="uq_hotspot")
    result = db.execute(stmt, rows)
    rowcount = getattr(result, "rowcount", None)
    return rowcount if (rowcount is not None and rowcount > 0) else len(rows)


def ingest_hotspots(db: Session, client: httpx.Client, s: Settings, region: Region) -> int:
    """Baixa os CSVs recentes ainda não processados. Retorna o total de focos lidos na região."""
    base = s.bdqueimadas_base_url.rstrip("/") + "/"
    listing = client.get(base)
    listing.raise_for_status()
    since = datetime.now(timezone.utc) - timedelta(hours=s.hotspots_backfill_hours)
    files = [(n, t) for n, t in list_files(listing.text) if t >= since]
    done = processed_keys(db, SOURCE, [n for n, _ in files])

    total = 0
    for name, _ in files:
        if name in done:
            continue
        try:
            resp = client.get(base + name)
            resp.raise_for_status()
            records = parse_csv(resp.content.decode("utf-8", errors="replace"))
            n = store_records(db, records, region, name)
            mark(db, SOURCE, name, "ok" if n else "empty", f"{len(records)} focos no arquivo, {n} na região")
            db.commit()
            total += n
        except Exception as exc:  # noqa: BLE001 - registra e segue para o próximo arquivo
            db.rollback()
            log.warning("Falha ao processar %s: %s", name, exc)
            mark(db, SOURCE, name, "error", str(exc)[:500])
            db.commit()
    log.info("BDQueimadas: %d arquivos novos, %d focos na região", len(files) - len(done), total)
    return total
