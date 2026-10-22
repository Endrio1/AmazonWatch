"""Ingestão e reprojeção de quadros de satélite True Color do CPTEC/INPE (DSAT).

Baixa os tiles do produto (ex: true_color_ch13_dsa) correspondentes à Amazônia Legal,
costura os tiles e reprojeta para coordenadas WGS-84 (EPSG:4326) para visualização
direta no Leaflet como ImageOverlay.
"""

import io
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.ingest.common import mark, processed_keys
from app.models import SatelliteFrame
from app.processing.geos import FD_PIXEL_RAD, FD_SIZE, GeosProjection
from app.region import Region

log = logging.getLogger(__name__)
SOURCE = "dsat_tiles"


def parse_dsat_time(dt_str: str) -> datetime:
    """Converte 'YYYYMMDDHHMM' para datetime UTC."""
    return datetime.strptime(dt_str, "%Y%m%d%H%M").replace(tzinfo=timezone.utc)


def format_dsat_time(dt: datetime) -> tuple[str, str]:
    """Retorna (YYYYMMDD, HHMM)."""
    return dt.strftime("%Y%m%d"), dt.strftime("%H%M")


def get_latest_dsat_time(client: httpx.Client, base_url: str, product: str) -> datetime | None:
    """Consulta o lastest.json do DSAT para obter o horário mais recente disponível."""
    url = f"{base_url.rstrip('/')}/json/{product}/lastest.json"
    try:
        resp = client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            return parse_dsat_time(data["date"])
    except Exception as e:
        log.warning("Falha ao consultar latest DSAT time: %s", e)
    return None


# Extensão continental cobrindo a América do Sul inteira e oceanos adjacentes (estilo DSAT do CPTEC)
CONTINENTAL_BOUNDS = {
    "west": -92.0,
    "south": -54.0,
    "east": -32.0,
    "north": 14.0,
}


def reproject_dsat_frame(
    client: httpx.Client,
    scan_time: datetime,
    s: Settings,
    region: Region,
    out_dir: Path,
) -> tuple[Path, dict[str, float]] | None:
    """Baixa toda a grade continental do Zoom 3 (6x6 tiles) e reprojeta para WGS-84."""
    date_str, time_str = format_dsat_time(scan_time)
    z = 3  # Zoom 3 cobre o disco da América do Sul em grade de 6x6 tiles
    scale = 2 ** (z - 5)

    base = s.dsat_tiles_url.rstrip("/")
    tile_size = 256
    stitched = Image.new("RGBA", (6 * tile_size, 6 * tile_size))
    downloaded = 0

    # Baixa toda a grade disponível no Zoom 3 cobrindo o continente sul-americano
    for ty in range(6):
        for tx in range(6):
            url = f"{base}/{date_str}/{s.dsat_product}/{time_str}/{z}/{tx}/{ty}.png"
            try:
                resp = client.get(url)
                if resp.status_code == 200:
                    tile = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                    stitched.paste(tile, (tx * tile_size, ty * tile_size))
                    downloaded += 1
            except Exception as e:
                log.debug("Tile %s indisponível: %s", url, e)

    if downloaded == 0:
        return None

    # Extensão continental cobrindo toda a América do Sul
    w = CONTINENTAL_BOUNDS["west"]
    s_lat = CONTINENTAL_BOUNDS["south"]
    e = CONTINENTAL_BOUNDS["east"]
    n = CONTINENTAL_BOUNDS["north"]

    out_w, out_h = 1400, 1500
    lons = np.linspace(w, e, out_w)
    lats = np.linspace(n, s_lat, out_h)  # topo para base
    lon_grid, lat_grid = np.meshgrid(lons, lats)

    proj = GeosProjection()
    xs, ys = proj.to_geos.transform(lon_grid, lat_grid)
    h = proj.h
    half_rad = FD_PIXEL_RAD * FD_SIZE / 2

    # Metros para pixel na grade Full Disk (5424x5424)
    px = (xs / h + half_rad) / FD_PIXEL_RAD
    py = (half_rad - ys / h) / FD_PIXEL_RAD

    # Escala para Zoom 3
    px_z = px * scale
    py_z = py * scale

    arr = np.array(stitched)
    valid = (
        np.isfinite(xs)
        & np.isfinite(ys)
        & (px_z >= 0)
        & (px_z < 6 * tile_size)
        & (py_z >= 0)
        & (py_z < 6 * tile_size)
    )

    out_channels = []
    for c in range(4):
        ch = map_coordinates(arr[:, :, c], [py_z, px_z], order=1, mode="constant", cval=0)
        ch[~valid] = 0
        out_channels.append(ch)

    out_img = Image.fromarray(np.stack(out_channels, axis=-1).astype(np.uint8))

    # Fundo escuro azul-noite (11, 15, 25) para o espaço fora do disco da Terra (blend com o basemap)
    rgb_img = Image.new("RGB", (out_w, out_h), (11, 15, 25))
    alpha_mask = out_img.split()[3]
    rgb_img.paste(out_img, mask=alpha_mask)

    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"satellite_{date_str}_{time_str}.jpg"
    out_path = out_dir / filename
    rgb_img.save(out_path, "JPEG", quality=88, optimize=True)
    return out_path, {"west": w, "south": s_lat, "east": e, "north": n}


def ingest_dsat_frames(
    db: Session,
    client: httpx.Client,
    s: Settings,
    region: Region,
) -> int:
    """Busca e processa quadros recentes de satélite."""
    latest_time = get_latest_dsat_time(client, s.dsat_tiles_url, s.dsat_product)
    if not latest_time:
        return 0

    # Gera horários em intervalos de 10 min dentro da janela de backfill
    window = timedelta(hours=s.frames_backfill_hours)
    start_time = latest_time - window

    candidate_times: list[datetime] = []
    cur = start_time
    while cur <= latest_time:
        candidate_times.append(cur)
        cur += timedelta(minutes=10)

    keys = [t.strftime("%Y%m%d%H%M") for t in candidate_times]
    done = processed_keys(db, SOURCE, keys)

    frames_dir = s.media_dir / "frames"
    total_new = 0

    for scan_time in candidate_times:
        key = scan_time.strftime("%Y%m%d%H%M")
        if key in done:
            continue

        try:
            res = reproject_dsat_frame(
                client=client,
                scan_time=scan_time,
                s=s,
                region=region,
                out_dir=frames_dir,
            )
            if not res:
                mark(db, SOURCE, key, "empty", "Nenhum tile disponível")
                db.commit()
                continue

            out_file, bounds = res
            rel_path = f"frames/{out_file.name}"

            existing = db.scalar(select(SatelliteFrame).where(SatelliteFrame.scan_time == scan_time))
            if existing:
                existing.file_path = rel_path
                existing.product = s.dsat_product
                existing.west = bounds["west"]
                existing.south = bounds["south"]
                existing.east = bounds["east"]
                existing.north = bounds["north"]
            else:
                db.add(
                    SatelliteFrame(
                        scan_time=scan_time,
                        product=s.dsat_product,
                        file_path=rel_path,
                        west=bounds["west"],
                        south=bounds["south"],
                        east=bounds["east"],
                        north=bounds["north"],
                    )
                )

            mark(db, SOURCE, key, "ok", f"Salvo em {rel_path}")
            db.commit()
            total_new += 1
            log.info("Quadro continental de satélite processado: %s", key)
        except Exception as exc:
            db.rollback()
            log.warning("Erro ao processar quadro %s: %s", key, exc)
            mark(db, SOURCE, key, "error", str(exc)[:500])
            db.commit()

    return total_new
