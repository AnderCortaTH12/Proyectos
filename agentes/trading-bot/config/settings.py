"""Settings generales de la aplicación, cargados desde variables de entorno/.env."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Configuración general (IA, caché, parámetros por defecto del bot)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Anthropic
    anthropic_api_key: str = ""
    model_planner: str = "claude-haiku-4-5"
    model_reasoner: str = "claude-sonnet-4-6"

    # Parámetros por defecto del bot
    default_score_threshold: float = 7.5
    default_max_position_pct: float = 0.05
    default_interval_minutes: int = 60
    default_max_open_positions: int = 10

    # Caché / almacenamiento
    cache_ttl_hours: int = 12
    cache_db_path: str = "data/cache.duckdb"
    log_db_path: str = "data/trades.duckdb"


@lru_cache
def get_settings() -> AppSettings:
    """Devuelve los settings (cacheados) de la aplicación."""
    return AppSettings()
