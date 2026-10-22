"""Roteador principal agregando todas as rotas sob o prefixo /api."""

from fastapi import APIRouter

from app.api.frames import router as frames_router
from app.api.health import router as health_router
from app.api.hotspots import router as hotspots_router
from app.api.plumes import router as plumes_router
from app.api.region import router as region_router
from app.api.stats import router as stats_router

api_router = APIRouter(prefix="/api")

api_router.include_router(health_router)
api_router.include_router(region_router)
api_router.include_router(stats_router)
api_router.include_router(hotspots_router)
api_router.include_router(plumes_router)
api_router.include_router(frames_router)
