"""Ingestão e processamento dos dados de fumaça NOAA GOES-19 (ABI-L2-ADPF).

Fonte pública S3: https://noaa-goes19.s3.amazonaws.com/
Prefixo: ABI-L2-ADPF/YYYY/DDD/HH/
Formato: NetCDF4 com variáveis Smoke, DQF, x, y, goes_imager_projection.
"""

import logging
import re
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import numpy as np
import xarray as xr
from sqlalchemy.orm import Session

from app.config import Settings
from app.ingest.common import mark, processed_keys
from app.models import SmokePlume, SmokeScan
from app.processing.association import associate_plume
from app.processing.geos import GeosProjection
from app.processing.smoke import extract_plumes
from app.region import Region

log = logging.getLogger(__name__)
SOURCE = "noaa_goes19"
FILE_RE = re.compile(
    r"OR_ABI-L2-ADPF-M\d+_G19_s(?P<year>\d{4})(?P<jday>\d{3})(?P<hour>\d{2})(?P<min>\d{2})(?P<sec>\d{2})\d+_.*\.nc"
)


def parse_adp_key_time(key: str) -> datetime | None:
    """Extrai o scan_time (UTC) do nome do arquivo NetCDF da NOAA."""
    m = FILE_RE.search(key)
    if not m:
        return None
    d = m.groupdict()
    dt = datetime.strptime(
        f"{d['year']}{d['jday']}{d['hour']}{d['min']}{d['sec']}", "%Y%j%H%M%S"
    ).replace(tzinfo=timezone.utc)
    return dt


def list_s3_files(
    client: httpx.Client,
    bucket_url: str,
    product: str,
    start_time: datetime,
    end_time: datetime,
) -> list[tuple[str, datetime]]:
    """Lista chaves NetCDF no bucket S3 público para o intervalo de tempo solicitado."""
    results: list[tuple[str, datetime]] = []
    bucket_url = bucket_url.rstrip("/")

    # Itera sobre cada hora entre start_time e end_time
    cur = start_time.replace(minute=0, second=0, microsecond=0)
    seen_prefixes = set()

    while cur <= end_time:
        year = cur.year
        jday = cur.timetuple().tm_yday
        hour = cur.hour
        prefix = f"{product}/{year}/{jday:03d}/{hour:02d}/"

        if prefix not in seen_prefixes:
            seen_prefixes.add(prefix)
            url = f"{bucket_url}/?list-type=2&prefix={prefix}"
            try:
                resp = client.get(url)
                if resp.status_code == 200:
                    root = ET.fromstring(resp.content)
                    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
                    for elem in root.findall(".//s3:Contents", ns):
                        k_elem = elem.find("s3:Key", ns)
                        if k_elem is not None and k_elem.text and k_elem.text.endswith(".nc"):
                            k = k_elem.text
                            st = parse_adp_key_time(k)
                            if st and start_time <= st <= end_time:
                                results.append((k, st))
            except Exception as e:
                log.warning("Falha ao listar S3 para prefixo %s: %s", prefix, e)

        cur += timedelta(hours=1)

    results.sort(key=lambda x: x[1])
    return results


def process_adp_file(
    db: Session,
    nc_path: Path,
    key: str,
    scan_time: datetime,
    s: Settings,
    region: Region,
) -> tuple[int, int]:
    """Abre o NetCDF, extrai as plumas de fumaça na Amazônia Legal e salva no PostGIS.

    Retorna (total_smoke_pixels, num_plumes).
    """
    with xr.open_dataset(nc_path, engine="h5netcdf", mask_and_scale=True) as ds:
        p_attrs = ds.goes_imager_projection.attrs
        proj = GeosProjection.from_attrs(p_attrs)

        # Determina os limites de recorte da região em metros geoestacionários
        xmin, ymin, xmax, ymax = proj.region_bounds_m(region.geometry, margin_deg=s.region_margin_deg)

        h = proj.h
        x_m = ds.x.values * h
        y_m = ds.y.values * h

        # Localiza os índices correspondentes
        col_idx = np.where((x_m >= xmin) & (x_m <= xmax))[0]
        row_idx = np.where((y_m >= ymin) & (y_m <= ymax))[0]

        if col_idx.size == 0 or row_idx.size == 0:
            log.warning("Recorte de x/y vazio para %s", key)
            return 0, 0

        r0, r1 = int(row_idx[0]), int(row_idx[-1]) + 1
        c0, c1 = int(col_idx[0]), int(col_idx[-1]) + 1

        sub_x_m = x_m[c0:c1]
        sub_y_m = y_m[r0:r1]
        sub_smoke = ds.Smoke.values[r0:r1, c0:c1]
        sub_dqf = ds.DQF.values[r0:r1, c0:c1]

    plumes, smoke_pixels = extract_plumes(
        smoke=sub_smoke,
        dqf=sub_dqf,
        x_m=sub_x_m,
        y_m=sub_y_m,
        proj=proj,
        region=region.prepared,
        min_confidence=s.smoke_min_confidence,
        closing_iterations=s.smoke_closing_iterations,
        min_pixels=s.smoke_min_pixels,
        simplify_deg=s.smoke_simplify_deg,
    )

    # Cria ou substitui o scan
    scan = db.get(SmokeScan, scan_time)
    if scan:
        scan.source_file = key
        scan.smoke_pixels = smoke_pixels
        scan.plume_count = len(plumes)
    else:
        scan = SmokeScan(
            scan_time=scan_time,
            source_file=key,
            smoke_pixels=smoke_pixels,
            plume_count=len(plumes),
        )
        db.add(scan)
    db.flush()

    # Adiciona as plumas
    created_plumes: list[SmokePlume] = []
    for p in plumes:
        sp = SmokePlume(
            scan_time=scan_time,
            geom=f"SRID=4326;{p.geometry.wkt}",
            centroid=f"SRID=4326;{p.centroid.wkt}",
            area_km2=p.area_km2,
            pixel_count=p.pixel_count,
            confidence=p.confidence,
        )
        db.add(sp)
        created_plumes.append(sp)
    db.flush()

    # Executa a associação pluma ↔ focos para cada pluma criada
    for sp in created_plumes:
        associate_plume(db, sp.id, s)

    return smoke_pixels, len(plumes)


def ingest_adp(
    db: Session,
    client: httpx.Client,
    s: Settings,
    region: Region,
) -> int:
    """Busca scans recentes de GOES-19 ADP no S3 e processa os novos.

    Retorna o número de plumas identificadas.
    """
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=s.adp_backfill_hours)

    all_files = list_s3_files(
        client=client,
        bucket_url=s.goes_bucket_url,
        product=s.goes_adp_product,
        start_time=start_time,
        end_time=now,
    )

    keys = [k for k, _ in all_files]
    done = processed_keys(db, SOURCE, keys)

    bucket_url = s.goes_bucket_url.rstrip("/")
    total_plumes = 0

    for key, scan_time in all_files:
        if key in done:
            continue

        url = f"{bucket_url}/{key}"
        try:
            with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    for chunk in resp.iter_bytes(chunk_size=128 * 1024):
                        tmp.write(chunk)

            smoke_px, n_plumes = process_adp_file(
                db=db,
                nc_path=tmp_path,
                key=key,
                scan_time=scan_time,
                s=s,
                region=region,
            )
            mark(
                db,
                SOURCE,
                key,
                "ok" if n_plumes > 0 else "empty",
                f"{smoke_px} pixels de fumaça, {n_plumes} plumas",
            )
            db.commit()
            total_plumes += n_plumes
            log.info("Processado %s: %d plumas", key, n_plumes)
        except Exception as exc:
            db.rollback()
            log.error("Erro ao processar ADP %s: %s", key, exc, exc_info=True)
            mark(db, SOURCE, key, "error", str(exc)[:500])
            db.commit()
        finally:
            if "tmp_path" in locals() and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    return total_plumes
