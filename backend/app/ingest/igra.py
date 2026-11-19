"""Coleta automática IGRA v2 e perfis de vento em níveis de pressão."""
import io
import json
import logging
import math
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

log = logging.getLogger(__name__)
BASE_URL = "https://www.ncei.noaa.gov/pub/data/igra"


def parse_soundings(content, station, cutoff):
    profiles = []
    current = None
    for line in content.splitlines():
        if line.startswith("#"):
            current = None
            if line[1:12] != station:
                raise ValueError("Identificador IGRA inesperado")
            hour = int(line[24:26])
            if hour == 99:
                continue
            observed = datetime(int(line[13:17]), int(line[18:20]), int(line[21:23]), hour, tzinfo=timezone.utc)
            if observed >= cutoff:
                current = {"station": station, "time": observed.isoformat(), "levels": []}
                profiles.append(current)
        elif current is not None and line.strip():
            pressure = int(line[9:15])
            direction = int(line[40:45])
            speed = int(line[46:51])
            if pressure > 0 and 0 <= direction <= 360 and speed >= 0:
                angle = math.radians(direction)
                current["levels"].append({"pressure": pressure / 100,
                    "u": -speed / 10 * math.sin(angle), "v": -speed / 10 * math.cos(angle)})
    return [profile for profile in profiles if profile["levels"]]


def refresh_igra(client, settings):
    """Atualiza snapshot atomicamente; falhas por estação preservam os dados anteriores."""
    path = settings.igra_cache_dir / "profiles.json"
    now = datetime.now(timezone.utc)
    previous = json.loads(path.read_text()) if path.exists() else {"profiles": [], "updated": None}
    if previous["updated"] and (now - datetime.fromisoformat(previous["updated"])).total_seconds() < settings.igra_refresh_minutes * 60:
        return
    response = client.get(BASE_URL + "/igra2-station-list.txt", timeout=30)
    response.raise_for_status()
    stations = []
    for line in response.text.splitlines():
        lat, lon = float(line[12:20]), float(line[21:30])
        if -22 <= lat <= 10 and -82 <= lon <= -40 and int(line[77:81]) >= now.year - 1:
            stations.append((line[:11], lat, lon))
    if not stations:
        raise ValueError("Nenhuma estação IGRA disponível na região")
    cutoff = now - timedelta(days=settings.retention_days + 2)
    profiles = [p for p in previous["profiles"] if datetime.fromisoformat(p["time"]) >= cutoff]
    successes = 0
    for station, lat, lon in stations:
        try:
            response = client.get(f"{BASE_URL}/data/data-y2d/{station}-data.txt.zip", timeout=30)
            response.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                content = archive.read(f"{station}-data.txt").decode("ascii")
            fresh = parse_soundings(content, station, cutoff)
            for profile in fresh:
                profile.update(lat=lat, lon=lon)
            profiles = [p for p in profiles if p["station"] != station] + fresh
            successes += 1
        except (httpx.HTTPError, ValueError, KeyError, zipfile.BadZipFile):
            log.exception("Falha ao atualizar IGRA %s", station)
    if successes == 0:
        raise ValueError("Falha em todas as estações IGRA")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"updated": now.isoformat(), "profiles": profiles}))
    temporary.replace(path)
    log.info("IGRA atualizado: %d estações, %d perfis", successes, len(profiles))
