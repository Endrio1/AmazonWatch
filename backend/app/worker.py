"""Worker de ingestão periódica e limpeza de dados (APScheduler).

Executa:
1. Ingestão de focos do BDQueimadas (CSV de 10 min)
2. Ingestão de produtos de fumaça NOAA GOES-19 (ABI-L2-ADPF)
3. Ingestão de quadros de satélite True Color (CPTEC/DSAT)
4. Recálculo de associações recentes (focos que chegam após o scan da fumaça)
5. Limpeza de dados antigos conforme política de retenção
"""

import argparse
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import delete, select

from app.config import Settings, get_settings
from app.db import session_scope
from app.ingest.bdqueimadas import ingest_hotspots
from app.ingest.common import make_client
from app.ingest.dsat_frames import ingest_dsat_frames
from app.ingest.goes_adp import ingest_adp
from app.models import FireHotspot, IngestLog, SatelliteFrame, SmokeScan
from app.processing.association import reassociate_recent
from app.region import Region, get_region

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("amazonwatch.worker")


def cleanup_old_data(settings: Settings) -> None:
    """Aplica a retenção configurada para liberar espaço em disco e banco."""
    now = datetime.now(timezone.utc)
    cutoff_retention = now - timedelta(days=settings.retention_days)
    cutoff_frames = now - timedelta(hours=settings.frame_retention_hours)

    with session_scope() as db:
        # Remove quadros de satélite antigos do banco e do disco
        old_frames = db.scalars(
            select(SatelliteFrame).where(SatelliteFrame.scan_time < cutoff_frames)
        ).all()
        for f in old_frames:
            full_path = settings.media_dir / f.file_path
            if full_path.exists():
                try:
                    full_path.unlink()
                except OSError as e:
                    log.warning("Falha ao remover arquivo de frame %s: %s", full_path, e)
            db.delete(f)

        # Remove focos antigos
        db.execute(delete(FireHotspot).where(FireHotspot.detected_at < cutoff_retention))
        # Remove scans e plumas antigas (cascade remove plumes e links)
        db.execute(delete(SmokeScan).where(SmokeScan.scan_time < cutoff_retention))
        # Remove logs antigos
        db.execute(delete(IngestLog).where(IngestLog.processed_at < cutoff_retention))

    log.info("Limpeza de retenção concluída.")


def run_pipeline(settings: Settings | None = None, region: Region | None = None) -> None:
    """Executa um ciclo completo do pipeline de ingestão e processamento."""
    settings = settings or get_settings()
    region = region or get_region()

    log.info("Iniciando ciclo do pipeline AmazonWatch...")
    t0 = datetime.now(timezone.utc)

    with make_client() as client:
        # 1. BDQueimadas
        try:
            with session_scope() as db:
                n_hotspots = ingest_hotspots(db, client, settings, region)
            log.info("BDQueimadas concluído: %d focos novos", n_hotspots)
        except Exception as e:
            log.error("Erro na etapa BDQueimadas: %s", e, exc_info=True)

        # 2. NOAA GOES-19 ADP
        try:
            with session_scope() as db:
                n_plumes = ingest_adp(db, client, settings, region)
            log.info("NOAA GOES-19 ADP concluído: %d plumas", n_plumes)
        except Exception as e:
            log.error("Erro na etapa NOAA ADP: %s", e, exc_info=True)

        # 3. Quadros True Color (DSAT/INPE)
        try:
            with session_scope() as db:
                n_frames = ingest_dsat_frames(db, client, settings, region)
            log.info("Quadros DSAT concluídos: %d novos frames", n_frames)
        except Exception as e:
            log.error("Erro na etapa DSAT frames: %s", e, exc_info=True)

        # 4. Reassociação recente
        try:
            with session_scope() as db:
                n_reassoc = reassociate_recent(db, settings)
            log.info("Reassociação de plumas recentes concluída: %d plumas atualizadas", n_reassoc)
        except Exception as e:
            log.error("Erro na reassociação: %s", e, exc_info=True)

    # 5. Limpeza de retenção
    try:
        cleanup_old_data(settings)
    except Exception as e:
        log.error("Erro na limpeza de retenção: %s", e)

    duration = (datetime.now(timezone.utc) - t0).total_seconds()
    log.info("Ciclo do pipeline finalizado em %.1fs.", duration)


def main():
    parser = argparse.ArgumentParser(description="AmazonWatch Ingestion Worker")
    parser.add_argument("--once", action="store_true", help="Executa o pipeline uma única vez e encerra")
    args = parser.parse_args()

    settings = get_settings()
    region = get_region()

    if args.once:
        run_pipeline(settings, region)
        return

    log.info(
        "Iniciando agendador do worker a cada %d minutos...",
        settings.pipeline_interval_minutes,
    )
    scheduler = BlockingScheduler()
    # Executa imediatamente na inicialização
    scheduler.add_job(
        run_pipeline,
        "date",
        run_date=datetime.now(),
        args=[settings, region],
    )
    # E agenda periodicamente
    scheduler.add_job(
        run_pipeline,
        "interval",
        minutes=settings.pipeline_interval_minutes,
        args=[settings, region],
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Worker encerrado.")


if __name__ == "__main__":
    main()
