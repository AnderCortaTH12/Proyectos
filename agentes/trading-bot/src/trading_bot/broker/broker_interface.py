"""Interfaz abstracta de broker (patrón template).

Cualquier broker —simulado (MockBroker) o real (AlpacaBroker)— implementa estos
métodos, de modo que el bot funciona igual sea cual sea el broker conectado.
"""
from abc import ABC, abstractmethod

from ..models import Account, Order, OrderRequest, Position


class BrokerInterface(ABC):
    """Contrato común de un broker para el bot de trading."""

    #: ¿Se permite enviar órdenes? (los brokers reales pueden bloquearlo).
    trading_allowed: bool = True

    @abstractmethod
    def get_account(self) -> Account:
        """Devuelve el estado de la cuenta (cash, equity, buying power...)."""

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Devuelve las posiciones abiertas con su P&L no realizado."""

    @abstractmethod
    def get_orders(self) -> list[Order]:
        """Devuelve el histórico de órdenes."""

    @abstractmethod
    def place_order(self, req: OrderRequest) -> Order:
        """Coloca una orden y devuelve la orden resultante."""
