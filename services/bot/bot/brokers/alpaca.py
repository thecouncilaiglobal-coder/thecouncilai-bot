from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import requests

from bot.brokers.base import Account, Broker, Position

log = logging.getLogger("bot.broker.alpaca")


class AlpacaBroker(Broker):
    name = "alpaca"

    def __init__(self, api_key: str, api_secret: str, trading_base_url: str, data_base_url: str):
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        self.trading_base_url = trading_base_url.rstrip("/")
        self.data_base_url = data_base_url.rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def _headers(self) -> Dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "Content-Type": "application/json",
        }

    def is_market_open(self) -> bool:
        try:
            r = requests.get(f"{self.trading_base_url}/v2/clock", headers=self._headers(), timeout=10)
            if r.status_code != 200:
                return False
            return bool(r.json().get("is_open"))
        except Exception:
            return False

    def get_account(self) -> Account:
        r = requests.get(f"{self.trading_base_url}/v2/account", headers=self._headers(), timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"alpaca_account_failed status={r.status_code} body={r.text[:200]}")
        j = r.json()
        equity = float(j.get("equity") or 0.0)
        cash = float(j.get("cash") or 0.0)
        return Account(equity=equity, cash=cash)

    def list_positions(self) -> List[Position]:
        r = requests.get(f"{self.trading_base_url}/v2/positions", headers=self._headers(), timeout=15)
        if r.status_code == 404:
            return []
        if r.status_code != 200:
            raise RuntimeError(f"alpaca_positions_failed status={r.status_code} body={r.text[:200]}")
        out: List[Position] = []
        for p in r.json() or []:
            sym = str(p.get("symbol") or "").upper()
            qty = float(p.get("qty") or 0.0)
            side = "long" if qty >= 0 else "short"
            out.append(
                Position(
                    symbol=sym,
                    qty=abs(qty),
                    side=side,
                    avg_entry_price=float(p.get("avg_entry_price") or 0.0),
                    market_value=float(p.get("market_value") or 0.0),
                )
            )
        return out

    def latest_price(self, symbol: str) -> Optional[float]:
        symbol = symbol.upper()
        # Prefer quote midpoint.
        try:
            r = requests.get(
                f"{self.data_base_url}/v2/stocks/{symbol}/quotes/latest",
                headers=self._headers(),
                timeout=10,
            )
            if r.status_code == 200:
                q = (r.json() or {}).get("quote") or {}
                bp = q.get("bp")
                ap = q.get("ap")
                if bp is not None and ap is not None and float(bp) > 0 and float(ap) > 0:
                    return (float(bp) + float(ap)) / 2.0
                if bp is not None and float(bp) > 0:
                    return float(bp)
                if ap is not None and float(ap) > 0:
                    return float(ap)
        except Exception:
            pass

        # Fallback to last trade price.
        try:
            r = requests.get(
                f"{self.data_base_url}/v2/stocks/{symbol}/trades/latest",
                headers=self._headers(),
                timeout=10,
            )
            if r.status_code == 200:
                t = (r.json() or {}).get("trade") or {}
                p = t.get("p")
                if p is not None and float(p) > 0:
                    return float(p)
        except Exception:
            pass

        return None

    def place_entry_with_bracket(
        self,
        symbol: str,
        qty: float,
        stop_loss_pct: float,
        take_profit_pct: float,
        client_order_id: str,
    ) -> None:
        symbol = symbol.upper()
        qty_int = int(qty)
        if qty_int <= 0:
            raise RuntimeError("qty_must_be_positive")

        price = self.latest_price(symbol)
        if price is None:
            # No pricing -> do not trade.
            raise RuntimeError("no_price")

        stop_price = round(price * (1.0 - float(stop_loss_pct)), 2)
        take_price = round(price * (1.0 + float(take_profit_pct)), 2)

        payload: Dict[str, Any] = {
            "symbol": symbol,
            "qty": str(qty_int),
            "side": "buy",
            "type": "market",
            "time_in_force": "day",
            "order_class": "bracket",
            "take_profit": {"limit_price": str(take_price)},
            "stop_loss": {"stop_price": str(stop_price)},
        }
        if client_order_id:
            payload["client_order_id"] = client_order_id[:48]

        r = requests.post(f"{self.trading_base_url}/v2/orders", headers=self._headers(), json=payload, timeout=20)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"alpaca_order_failed status={r.status_code} body={r.text[:300]}")

    def close_position(self, symbol: str, qty: Optional[float] = None, client_order_id: str = "") -> None:
        symbol = symbol.upper()

        # Alpaca supports DELETE /v2/positions/{symbol} to close full position.
        if qty is None:
            r = requests.delete(f"{self.trading_base_url}/v2/positions/{symbol}", headers=self._headers(), timeout=20)
            if r.status_code not in (200, 204):
                raise RuntimeError(f"alpaca_close_failed status={r.status_code} body={r.text[:300]}")
            return

        qty_int = int(qty)
        if qty_int <= 0:
            return
        payload: Dict[str, Any] = {
            "symbol": symbol,
            "qty": str(qty_int),
            "side": "sell",
            "type": "market",
            "time_in_force": "day",
        }
        if client_order_id:
            payload["client_order_id"] = client_order_id[:48]

        r = requests.post(f"{self.trading_base_url}/v2/orders", headers=self._headers(), json=payload, timeout=20)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"alpaca_partial_close_failed status={r.status_code} body={r.text[:300]}")
