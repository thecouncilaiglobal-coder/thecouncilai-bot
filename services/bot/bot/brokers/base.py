from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Position:
    symbol: str
    qty: float
    side: str  # "long" or "short"
    avg_entry_price: Optional[float] = None
    market_value: Optional[float] = None


@dataclass
class Account:
    equity: float
    cash: float


class Broker:
    name: str = ""

    def is_configured(self) -> bool:
        raise NotImplementedError

    def is_market_open(self) -> bool:
        """Best-effort market open check.

        The bot will only panic on signal loss **during market hours**.
        """
        raise NotImplementedError

    def get_account(self) -> Account:
        raise NotImplementedError

    def list_positions(self) -> List[Position]:
        raise NotImplementedError

    def latest_price(self, symbol: str) -> Optional[float]:
        raise NotImplementedError

    def place_entry_with_bracket(
        self,
        symbol: str,
        qty: float,
        stop_loss_pct: float,
        take_profit_pct: float,
        client_order_id: str,
    ) -> None:
        """Open position (long) with broker-side risk orders where supported."""
        raise NotImplementedError

    def close_position(self, symbol: str, qty: Optional[float] = None, client_order_id: str = "") -> None:
        raise NotImplementedError
