from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import List, Optional

from ib_insync import IB, LimitOrder, MarketOrder, Stock, StopOrder, util

from bot.brokers.base import Account, Broker, Position

log = logging.getLogger("bot.broker.ibkr")


class IBKRBroker(Broker):
    name = "ibkr"

    def __init__(self, host: str, port: int, client_id: int):
        self.host = host
        self.port = int(port)
        self.client_id = int(client_id)
        self.ib = IB()
        self._last_connect = 0.0

    def is_configured(self) -> bool:
        # Credentials are handled by running TWS/IB Gateway; we only need connection params.
        return True

    def _ensure_connected(self) -> None:
        if self.ib.isConnected():
            return
        # Throttle reconnect attempts.
        if time.time() - self._last_connect < 5:
            return
        self._last_connect = time.time()
        try:
            self.ib.connect(self.host, self.port, clientId=self.client_id, timeout=3)
        except Exception as e:
            log.warning("ibkr_connect_failed err=%s", e)

    def is_market_open(self) -> bool:
        # Fallback heuristic: US equities regular session (Mon-Fri, 09:30-16:00 America/New_York).
        try:
            from zoneinfo import ZoneInfo

            now = datetime.now(ZoneInfo("America/New_York"))
            if now.weekday() >= 5:
                return False
            minutes = now.hour * 60 + now.minute
            return (9 * 60 + 30) <= minutes < (16 * 60)
        except Exception:
            return False

    def get_account(self) -> Account:
        self._ensure_connected()
        if not self.ib.isConnected():
            raise RuntimeError("ibkr_not_connected")
        summary = self.ib.accountSummary()
        # keys: 'TotalCashValue', 'NetLiquidation'
        cash = 0.0
        equity = 0.0
        for row in summary:
            if row.tag == "TotalCashValue":
                try:
                    cash = float(row.value)
                except Exception:
                    pass
            if row.tag == "NetLiquidation":
                try:
                    equity = float(row.value)
                except Exception:
                    pass
        return Account(equity=equity, cash=cash)

    def list_positions(self) -> List[Position]:
        self._ensure_connected()
        if not self.ib.isConnected():
            return []
        out: List[Position] = []
        for p in self.ib.positions():
            if p.contract.secType != "STK":
                continue
            sym = str(p.contract.symbol).upper()
            qty = float(p.position)
            side = "long" if qty >= 0 else "short"
            out.append(Position(symbol=sym, qty=abs(qty), side=side, avg_entry_price=None, market_value=None))
        return out

    def latest_price(self, symbol: str) -> Optional[float]:
        self._ensure_connected()
        if not self.ib.isConnected():
            return None
        try:
            contract = Stock(symbol.upper(), "SMART", "USD")
            self.ib.qualifyContracts(contract)
            ticker = self.ib.reqMktData(contract, "", False, False)
            self.ib.sleep(1)
            price = None
            if ticker.last is not None:
                price = float(ticker.last)
            elif ticker.marketPrice() is not None:
                price = float(ticker.marketPrice())
            self.ib.cancelMktData(contract)
            return price
        except Exception:
            return None

    def place_entry_with_bracket(
        self,
        symbol: str,
        qty: float,
        stop_loss_pct: float,
        take_profit_pct: float,
        client_order_id: str,
    ) -> None:
        """Market entry + broker-side OCO protection (take-profit + stop-loss).

        Goal: if the bot crashes / network drops, the broker still has an exit plan.
        We place a market entry and, once filled, place an OCO pair:
        - Take-profit (limit)
        - Stop-loss (stop)
        """
        self._ensure_connected()
        if not self.ib.isConnected():
            raise RuntimeError("ibkr_not_connected")

        q = int(qty)
        if q <= 0:
            raise RuntimeError("qty_must_be_positive")

        symbol = symbol.upper()
        contract = Stock(symbol, "SMART", "USD")
        self.ib.qualifyContracts(contract)

        # Cancel any stray open orders for this symbol (safety).
        self._cancel_open_orders_for_symbol(symbol)

        entry = MarketOrder("BUY", q)
        if client_order_id:
            entry.orderRef = client_order_id[:32]
        trade = self.ib.placeOrder(contract, entry)

        # Wait briefly for fill so protection orders match actual position.
        for _ in range(12):
            self.ib.sleep(0.5)
            st = trade.orderStatus.status
            if st in ("Filled", "Cancelled", "Inactive"):
                break

        if trade.orderStatus.status in ("Cancelled", "Inactive"):
            raise RuntimeError(f"ibkr_order_failed status={trade.orderStatus.status}")

        # Determine an approximate fill price.
        fill_px: Optional[float] = None
        try:
            fills = trade.fills or []
            if fills:
                total_qty = 0.0
                total_val = 0.0
                for f in fills:
                    px = float(f.execution.price)
                    qty_f = float(f.execution.shares)
                    total_qty += qty_f
                    total_val += px * qty_f
                if total_qty > 0:
                    fill_px = total_val / total_qty
        except Exception:
            fill_px = None

        if fill_px is None:
            try:
                ap = float(trade.orderStatus.avgFillPrice or 0.0)
                if ap > 0:
                    fill_px = ap
            except Exception:
                fill_px = None

        if fill_px is None:
            fill_px = self.latest_price(symbol)

        if not fill_px or fill_px <= 0:
            # If we can't price protection reliably, bail out after entry.
            log.warning("ibkr_no_fill_price_for_protection sym=%s", symbol)
            return

        stop_price = round(float(fill_px) * (1.0 - float(stop_loss_pct)), 2)
        take_price = round(float(fill_px) * (1.0 + float(take_profit_pct)), 2)

        oca = f"TCA_{symbol}_{int(time.time())}"

        tp = LimitOrder("SELL", q, take_price, tif="GTC")
        sl = StopOrder("SELL", q, stop_price, tif="GTC")
        tp.ocaGroup = oca
        sl.ocaGroup = oca
        tp.ocaType = 1
        sl.ocaType = 1
        if client_order_id:
            tp.orderRef = f"{client_order_id[:24]}_tp"
            sl.orderRef = f"{client_order_id[:24]}_sl"

        self.ib.placeOrder(contract, tp)
        self.ib.placeOrder(contract, sl)
        self.ib.sleep(0.2)

    def close_position(self, symbol: str, qty: Optional[float] = None, client_order_id: str = "") -> None:
        self._ensure_connected()
        if not self.ib.isConnected():
            raise RuntimeError("ibkr_not_connected")
        symbol = symbol.upper()

        # Cancel protective orders first to avoid accidental re-opening / shorting.
        self._cancel_open_orders_for_symbol(symbol)

        positions = {p.symbol.upper(): p for p in self.list_positions()}
        pos = positions.get(symbol)
        if not pos:
            return
        q = int(qty) if qty is not None else int(pos.qty)
        if q <= 0:
            return
        contract = Stock(symbol, "SMART", "USD")
        self.ib.qualifyContracts(contract)
        order = MarketOrder("SELL", q)
        if client_order_id:
            order.orderRef = client_order_id[:32]
        trade = self.ib.placeOrder(contract, order)
        self.ib.sleep(0.5)
        if trade.orderStatus.status in ("Cancelled", "Inactive"):
            raise RuntimeError(f"ibkr_close_failed status={trade.orderStatus.status}")

        # Best-effort: cancel any remaining orders for the symbol.
        self._cancel_open_orders_for_symbol(symbol)

    def _cancel_open_orders_for_symbol(self, symbol: str) -> None:
        """Cancel all open orders/trades for the given symbol."""
        try:
            symbol = symbol.upper()
            self._ensure_connected()
            if not self.ib.isConnected():
                return
            for tr in list(self.ib.openTrades() or []):
                try:
                    cs = getattr(tr.contract, "symbol", "")
                    if str(cs).upper() != symbol:
                        continue
                    st = getattr(tr.orderStatus, "status", "")
                    if st in ("Filled", "Cancelled"):
                        continue
                    self.ib.cancelOrder(tr.order)
                except Exception:
                    continue
            self.ib.sleep(0.1)
        except Exception:
            return
