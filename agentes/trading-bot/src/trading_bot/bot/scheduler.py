"""Scheduler periódico del bot basado en APScheduler (jobs en segundo plano)."""
from collections.abc import Callable
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from .trading_bot import TradingBot


class BotScheduler:
    """Ejecuta TradingBot.run_once() cada N minutos en un hilo de fondo."""

    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler()
        self._job = None

    @property
    def running(self) -> bool:
        return self._job is not None

    def start(
        self,
        bot: TradingBot,
        interval_minutes: int,
        on_run: Optional[Callable] = None,
        run_immediately: bool = True,
    ) -> None:
        """Programa el bot. `on_run` recibe el BotRunRecord tras cada ejecución."""
        if not self._scheduler.running:
            self._scheduler.start()

        def _job() -> None:
            record = bot.run_once()
            if on_run:
                on_run(record)

        self.stop()  # evita jobs duplicados
        self._job = self._scheduler.add_job(
            _job, "interval", minutes=interval_minutes, id="trading_bot", replace_existing=True
        )
        if run_immediately:
            _job()

    def stop(self) -> None:
        """Detiene/elimina el job activo (si lo hay)."""
        if self._job is not None:
            try:
                self._scheduler.remove_job("trading_bot")
            except Exception:  # noqa: BLE001
                pass
            self._job = None

    def shutdown(self) -> None:
        self.stop()
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
