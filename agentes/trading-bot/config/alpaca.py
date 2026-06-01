"""Credenciales y constantes de Alpaca, con doble cerrojo para trading real."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AlpacaSettings(BaseSettings):
    """Configuración del broker Alpaca.

    Seguridad: para operar con dinero real se exigen DOS condiciones a la vez:
    ``paper=False`` Y ``enable_live_trading=True``. Por defecto, paper trading.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_paper: bool = True
    enable_live_trading: bool = False

    @property
    def is_live(self) -> bool:
        """True solo si se cumplen ambas condiciones de seguridad para dinero real."""
        return (not self.alpaca_paper) and self.enable_live_trading

    @property
    def trading_allowed(self) -> bool:
        """¿Se permite enviar órdenes? En paper siempre; en real solo si is_live."""
        return self.alpaca_paper or self.is_live


@lru_cache
def get_alpaca_settings() -> AlpacaSettings:
    """Devuelve los settings (cacheados) de Alpaca."""
    return AlpacaSettings()
