"""Configuração da aplicação via variáveis de ambiente."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Segredos que já foram expostos no repositório e nunca devem ser aceitos.
_KNOWN_INSECURE_JWT_SECRETS = frozenset({
    "amazonwatch_super_secret_jwt_key_2026_x89f4",
})


class Settings(BaseSettings):
    # Procura o .env na raiz do projeto (execução local a partir de backend/) e no
    # diretório atual; em caso de conflito, o último arquivo da tupla tem prioridade.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    # Banco de dados
    database_url: str = "postgresql+psycopg://amazonwatch:amazonwatch@localhost:5433/amazonwatch"

    # Diretório onde o worker grava as imagens (servido em /media pela API)
    media_dir: Path = Path("/data/media")

    # CORS (útil ao rodar o frontend com `npm run dev`)
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]

    # Autenticação e Segurança JWT
    # Obrigatório e sem valor padrão: a aplicação não inicia sem um JWT_SECRET
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_access_token_expire_minutes: int = 10080

    @field_validator("jwt_secret")
    @classmethod
    def _reject_known_jwt_secrets(cls, v: SecretStr) -> SecretStr:
        """Recusa segredos públicos (antigo padrão do código e placeholder do .env.example)."""
        value = v.get_secret_value()
        if value in _KNOWN_INSECURE_JWT_SECRETS or "exemplo" in value.lower():
            raise ValueError(
                "JWT_SECRET usa um valor público/de exemplo. Gere um novo com: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return v

    # --- Fontes de dados

    bdqueimadas_base_url: str = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/10min/"
    goes_bucket_url: str = "https://noaa-goes19.s3.amazonaws.com"
    goes_adp_product: str = "ABI-L2-ADPF"
    dsat_tiles_url: str = "https://s1.cptec.inpe.br/goes/goes16/web_tiles"
    dsat_product: str = "true_color_ch13_dsa"
    dsat_zoom: int = 5  # 5 = resolução nativa de 2 km, 6 = 1 km
    http_timeout_s: float = 60.0

    # --- Janelas de ingestão (dados recentes)
    hotspots_backfill_hours: int = 24
    adp_backfill_hours: int = 6
    frames_backfill_hours: int = 3
    region_margin_deg: float = 1.0

    # --- Detecção de fumaça (máscara ADP da NOAA)
    smoke_min_confidence: str = "low"  # low | medium | high
    smoke_closing_iterations: int = 1
    smoke_min_pixels: int = 10
    smoke_simplify_deg: float = 0.01

    # --- Associação pluma ↔ foco
    assoc_max_distance_km: float = 25.0
    assoc_window_before_hours: float = 6.0
    assoc_window_after_minutes: float = 10.0
    assoc_cluster_eps_km: float = 5.0
    assoc_distance_scale_km: float = 10.0
    assoc_age_scale_hours: float = 3.0
    assoc_origin_rel_threshold: float = 0.5
    assoc_max_origin_clusters: int = 3
    assoc_recompute_hours: float = 2.0

    # --- Agendamento e retenção
    pipeline_interval_minutes: int = 5
    retention_days: int = 7
    frame_retention_hours: int = 24


@lru_cache
def get_settings() -> Settings:
    return Settings()
