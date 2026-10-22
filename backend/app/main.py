"""Ponto de entrada da aplicação FastAPI AmazonWatch."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("amazonwatch")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # Garante que os diretórios de mídia existem
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    (settings.media_dir / "frames").mkdir(parents=True, exist_ok=True)
    log.info("AmazonWatch API inicializada. Media dir: %s", settings.media_dir)
    yield
    log.info("AmazonWatch API encerrando...")


app = FastAPI(
    title="AmazonWatch API",
    description="Sistema de monitoramento e correlação de plumas de fumaça (NOAA GOES-19) e focos de incêndio (BDQueimadas/INPE) na Amazônia Legal.",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    # Origens explícitas (CORS_ORIGINS em JSON). Em produção o Nginx serve
    # frontend e API na mesma origem, então o CORS só importa no `npm run dev`.
    allow_origins=settings.cors_origins,
    allow_credentials=False,  # A API não usa cookies/sessão
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# Cria o diretório de mídia antes de montar se necessário
settings.media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(settings.media_dir), check_dir=False), name="media")

# Rotas da API
app.include_router(api_router)


@app.get("/", tags=["root"])
def root_info():
    return {
        "name": "AmazonWatch API",
        "description": "Rastreamento de plumas de fumaça e focos de queimada na Amazônia Legal",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
