from __future__ import annotations

import asyncio
import logging
import os
import random
import time
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from bot.brokers.base import Broker, Position
from bot.risk.profile import ProfileParams, params_for
from bot.signals.feed import SignalFeed
from bot.storage.state import load_state, save_state
from bot.storage.trades_db import log_trade

log = logging.getLogger("bot.engine")


@dataclass
class Candidate:
    symbol: str
    score: int


class BotEngine:
    def __init__(
        self,
        broker: Broker,
        feed: SignalFeed,
        profile_name: str,
        # Optional hooks
        get_panic: callable,
        get_profile: callable,
    ):
        self.broker = broker
        self.feed = feed

        self.get_panic = get_panic
        self.get_profile = get_profile

        self._profile: ProfileParams = params_for(profile_name)  # placeholder until first tick

        self.state = load_state()
        self._above_since: Dict[str, int] = self.state.get("above_since", {})
        self._below_since: Dict[str, int] = self.state.get("below_since", {})
        self._missing_since: Dict[str, int] = self.state.get("missing_since", {})

        self._last_decision_ms: int = 0
        self._last_account_poll_ms: int = 0
        self._cached_equity: Optional[float] = None
        self._cached_cash: Optional[float] = None

    async def run(self) -> None:
        interval = float(os.getenv("BOT_DECISION_SECONDS", "12"))
        while True:
            try:
                await self._tick()
            except Exception as e:
                log.exception("tick_failed err=%s", e)
            await asyncio.sleep(interval)

    async def _tick(self) -> None:
        now_ms = int(time.time() * 1000)

        # Refresh profile/panic from control plane.
        profile_name = (self.get_profile() or "balanced").strip()
        self._profile = params_for(profile_name)  # type: ignore
        panic = bool(self.get_panic())

        # Basic liveness info
        self.state.setdefault("health", {})
        self.state["health"]["last_tick_ms"] = now_ms
        self.state["health"]["ws_ok"] = self.feed.ws_ok
        self.state["health"]["signal_last_ms"] = self.feed.last_update_ms
        self.state["health"]["profile"] = self._profile.name

        if not self.broker.is_configured():
            self.state["health"]["mode"] = "needs_broker_config"
            save_state(self._persist())
            return

        market_open = self.broker.is_market_open()
        self.state["health"]["market_open"] = market_open

        # Panic has priority during market hours.
        if panic and market_open:
            self.state["health"]["mode"] = "panic"
            await self._panic_close_all()
            save_state(self._persist())
            return

        # Signal freshness guard (only matters during market hours)
        stale_s = float(os.getenv("BOT_SIGNAL_STALE_SECONDS", "480"))
        if market_open:
            if self.feed.last_update_ms is None:
                self.state["health"]["mode"] = "waiting_signals"
                save_state(self._persist())
                return
            age_s = (now_ms - int(self.feed.last_update_ms)) / 1000.0
            self.state["health"]["signal_age_s"] = round(age_s, 1)
            # If signals recovered, clear any stale-safety state.
            if age_s <= stale_s:
                self.state.pop("safe_signal", None)
            if age_s > stale_s:
                self.state["health"]["mode"] = "safe_signal_stale"
                await self._safe_reduce_on_stale(now_ms=now_ms, age_s=age_s)
                save_state(self._persist())
                return

        # No trading outside market hours; keep state warm.
        if not market_open:
            self.state["health"]["mode"] = "market_closed"
            save_state(self._persist())
            return

        # Account polling
        if now_ms - self._last_account_poll_ms > 20_000 or self._cached_equity is None:
            acct = self.broker.get_account()
            self._cached_equity = float(acct.equity)
            self._cached_cash = float(acct.cash)
            self._last_account_poll_ms = now_ms

            # Daily drawdown guard
            day = self.state.get("day") or {}
            day_id = day.get("id")
            # Use UTC date for consistency
            utc_day = time.strftime("%Y-%m-%d", time.gmtime())
            if day_id != utc_day:
                day = {"id": utc_day, "equity_start": self._cached_equity}
                self.state["day"] = day
            dd = 0.0
            try:
                dd = (float(day.get("equity_start", self._cached_equity)) - self._cached_equity) / float(day.get("equity_start", self._cached_equity))
            except Exception:
                dd = 0.0
            self.state["health"]["day_drawdown"] = round(dd, 4)
            if dd > self._profile.daily_max_drawdown_pct:
                self.state["health"]["mode"] = "safe_daily_drawdown"
                await self._safe_close_all(reason=f"daily_drawdown_{round(dd*100,2)}%")
                save_state(self._persist())
                return

        # Sync positions
        positions = {p.symbol: p for p in self.broker.list_positions() if p.side == "long"}

        # Update confirmation trackers
        self._update_confirmation(now_ms, positions)

        # Exits first
        exits = self._decide_exits(now_ms, positions)
        for sym, reason in exits:
            await self._close(sym, positions.get(sym), reason)
            positions.pop(sym, None)

        # Entries / rotations
        await self._entries_and_rotation(now_ms, positions)

        self.state["health"]["mode"] = "running"
        self.state["health"]["positions"] = list(sorted(positions.keys()))
        save_state(self._persist())

    def _update_confirmation(self, now_ms: int, positions: Dict[str, Position]) -> None:
        scores = self.feed.scores
        entry_th = self._profile.entry
        exit_th = self._profile.exit

        # Track above threshold for entries
        for sym, sc in scores.items():
            if sc >= entry_th:
                self._above_since.setdefault(sym, now_ms)
            else:
                self._above_since.pop(sym, None)

        # Track below threshold for exits (held positions)
        for sym in list(positions.keys()):
            sc = scores.get(sym)
            if sc is None:
                # symbol missing from public top list
                self._missing_since.setdefault(sym, now_ms)
                continue
            self._missing_since.pop(sym, None)
            if sc <= exit_th:
                self._below_since.setdefault(sym, now_ms)
            else:
                self._below_since.pop(sym, None)

    def _decide_exits(self, now_ms: int, positions: Dict[str, Position]) -> List[Tuple[str, str]]:
        exits: List[Tuple[str, str]] = []

        # Missing symbols (feed limited to top N): reduce churn by exiting *gradually*.
        # If a held symbol disappears from the feed, it may be benign. We therefore:
        # - wait a grace period
        # - then close at most ONE missing-held symbol per cycle
        missing_grace_s = int(os.getenv("BOT_MISSING_SYMBOL_GRACE_SECONDS", "180"))
        missing_candidates: List[Tuple[float, str]] = []
        for sym, since in list(self._missing_since.items()):
            if sym in positions:
                age = (now_ms - int(since)) / 1000.0
                if age >= missing_grace_s:
                    missing_candidates.append((age, sym))

        if missing_candidates:
            # Close the longest-missing first (kademeli azaltma).
            missing_candidates.sort(key=lambda x: x[0], reverse=True)
            _, sym = missing_candidates[0]
            exits.append((sym, "symbol_missing"))
            self._missing_since.pop(sym, None)

        # Confirmed below threshold
        for sym, since in list(self._below_since.items()):
            if sym not in positions:
                self._below_since.pop(sym, None)
                continue
            if (now_ms - int(since)) / 1000.0 >= self._profile.exit_confirm_s:
                exits.append((sym, "score_exit"))
                self._below_since.pop(sym, None)

        return exits

    async def _entries_and_rotation(self, now_ms: int, positions: Dict[str, Position]) -> None:
        scores = self.feed.scores

        # Build eligible candidates
        eligible: List[Candidate] = []
        for sym, since in self._above_since.items():
            sc = scores.get(sym)
            if sc is None:
                continue
            if (now_ms - int(since)) / 1000.0 >= self._profile.entry_confirm_s:
                eligible.append(Candidate(symbol=sym, score=int(sc)))

        eligible.sort(key=lambda c: c.score, reverse=True)

        # Remove already held
        eligible = [c for c in eligible if c.symbol not in positions]

        if not eligible:
            return

        max_pos = self._profile.max_positions

        # Rotation logic if full
        if len(positions) >= max_pos:
            worst = self._worst_position(scores, positions)
            if worst is None:
                return
            worst_sym, worst_score = worst
            best_new = eligible[0]

            # Only rotate if margin met and min hold satisfied
            opened_at = int((self.state.get("opened_at_ms") or {}).get(worst_sym, 0))
            held_s = (now_ms - opened_at) / 1000.0 if opened_at else 1e9
            if best_new.score >= (worst_score + self._profile.rotation_margin) and held_s >= self._profile.min_hold_s:
                out_pos = positions.get(worst_sym)
                if out_pos and self._rotation_worth_it(
                    out_symbol=worst_sym,
                    out_score=worst_score,
                    out_pos=out_pos,
                    in_symbol=best_new.symbol,
                    in_score=best_new.score,
                ):
                    log.info("rotate out=%s(%s) in=%s(%s)", worst_sym, worst_score, best_new.symbol, best_new.score)
                    await self._close(worst_sym, out_pos, reason="rotate")
                    positions.pop(worst_sym, None)
                    await self._open(best_new.symbol, best_new.score)
                else:
                    log.info("rotate_skip_cost out=%s(%s) in=%s(%s)", worst_sym, worst_score, best_new.symbol, best_new.score)
            return

        # Otherwise, open until capacity
        slots = max_pos - len(positions)
        picks = eligible[:slots]
        for c in picks:
            await self._open(c.symbol, c.score)

    def _worst_position(self, scores: Dict[str, int], positions: Dict[str, Position]) -> Optional[Tuple[str, int]]:
        worst_sym = None
        worst_score = 10**9
        for sym in positions.keys():
            sc = scores.get(sym, 50)  # if missing, treat as mediocre
            if sc < worst_score:
                worst_score = sc
                worst_sym = sym
        if worst_sym is None:
            return None
        return worst_sym, int(worst_score)

    def _rotation_worth_it(
        self,
        out_symbol: str,
        out_score: int,
        out_pos: Position,
        in_symbol: str,
        in_score: int,
    ) -> bool:
        """Commission/slippage-aware rotation gate.

        We only have a single score, so we use a conservative heuristic:
        - Convert score improvement into an *expected edge* (bps).
        - Compare to estimated round-trip cost (slippage + commissions) for closing+opening.
        """

        try:
            out_px = self.broker.latest_price(out_symbol) or out_pos.avg_entry_price or 0.0
            out_notional = max(0.0, float(out_pos.qty) * float(out_px))
        except Exception:
            out_notional = 0.0

        if out_notional <= 0:
            # If we can't estimate costs, default to *not* rotating.
            return False

        delta = max(0, int(in_score) - int(out_score))

        score_point_bps = float(os.getenv("BOT_SCORE_POINT_VALUE_BPS", "4.0"))
        # Estimated benefit in $ (very conservative)
        est_benefit = out_notional * (delta * score_point_bps) / 10_000.0

        # Costs
        default_comm = "0.0" if getattr(self.broker, "name", "") == "alpaca" else "1.0"
        commission = float(os.getenv("BOT_COMMISSION_PER_TRADE", default_comm))
        slippage_bps = float(os.getenv("BOT_SLIPPAGE_BPS", "2.5"))
        est_slip = out_notional * (slippage_bps / 10_000.0) * 2.0
        est_cost = est_slip + (commission * 2.0)

        mult = float(os.getenv("BOT_SWITCH_COST_MULTIPLIER", "1.5"))
        return est_benefit >= (est_cost * mult)

    def _desired_weight(self, score: int) -> float:
        # Map score to weight in [minW, maxW] with a convex shape for selectivity.
        min_w = float(os.getenv("BOT_MIN_WEIGHT_PER_POS", "0.08"))
        max_w = float(self._profile.max_weight_per_pos)
        entry = float(self._profile.entry)
        if score <= entry:
            return min_w
        strength = (float(score) - entry) / max(1.0, (100.0 - entry))
        strength = max(0.0, min(1.0, strength))
        # Convex: stronger scores ramp faster
        strength = strength * strength
        return min_w + (max_w - min_w) * strength

    async def _open(self, symbol: str, score: int) -> None:
        now_ms = int(time.time() * 1000)
        cds = self.state.get("cooldowns") or {}
        cd_until = int(cds.get(symbol, 0))
        if cd_until and now_ms < cd_until:
            return

        if self._cached_equity is None or self._cached_cash is None:
            return

        # Dynamic sizing based on score quality
        weight = self._desired_weight(score)
        alloc = self._cached_equity * min(weight, self._profile.max_exposure)

        # Keep a small cash buffer
        cash_buffer = float(os.getenv("BOT_CASH_BUFFER", "0.05"))
        max_spend = max(0.0, self._cached_cash - self._cached_equity * cash_buffer)
        alloc = min(alloc, max_spend)
        if alloc <= 50:
            return

        price = self.broker.latest_price(symbol)
        if not price or price <= 0:
            return

        qty = int(alloc / price)
        if qty <= 0:
            return

        cid = f"tca_{uuid.uuid4().hex[:10]}"
        try:
            self.broker.place_entry_with_bracket(
                symbol=symbol,
                qty=qty,
                stop_loss_pct=self._profile.stop_loss_pct,
                take_profit_pct=self._profile.take_profit_pct,
                client_order_id=cid,
            )
            log_trade(symbol, "BUY", qty, score, price, "entry", self.broker.name, "paper")
            self.state.setdefault("opened_at_ms", {})
            self.state["opened_at_ms"][symbol] = int(time.time() * 1000)

            # Cooldown to avoid rapid re-entries on noisy signals
            cooldown_s = int(os.getenv("BOT_COOLDOWN_SECONDS", "240"))
            self.state.setdefault("cooldowns", {})
            self.state["cooldowns"][symbol] = int(time.time() * 1000 + cooldown_s * 1000)

            # Update cash estimate pessimistically
            self._cached_cash = max(0.0, self._cached_cash - qty * price)
            log.info("opened %s qty=%s score=%s est_price=%.2f", symbol, qty, score, price)
        except Exception as e:
            log.warning("open_failed %s err=%s", symbol, e)

    async def _close(self, symbol: str, pos: Optional[Position], reason: str) -> None:
        symbol = symbol.upper()
        cid = f"tca_{uuid.uuid4().hex[:10]}"
        try:
            if pos is None:
                self.broker.close_position(symbol, qty=None, client_order_id=cid)
                qty = 0
            else:
                self.broker.close_position(symbol, qty=None, client_order_id=cid)
                qty = pos.qty

            sc = int(self.feed.scores.get(symbol, 50))
            pe = self.broker.latest_price(symbol)
            log_trade(symbol, "SELL", qty, sc, pe, reason, self.broker.name, "paper")
            log.info("closed %s reason=%s", symbol, reason)
        except Exception as e:
            log.warning("close_failed %s err=%s", symbol, e)

    async def _panic_close_all(self) -> None:
        try:
            positions = self.broker.list_positions()
        except Exception:
            positions = []
        for p in positions:
            if p.side != "long":
                continue
            await self._close(p.symbol, p, reason="panic")

    async def _safe_reduce_on_stale(self, now_ms: int, age_s: float) -> None:
        """When signal feed is stale during market hours, reduce exposure gradually.

        Rationale:
        - If the bot loses the signal stream, we don't want to instantly flatten everything
          (can overreact during brief network hiccups, and increases costs).
        - We *do* want to actively reduce risk if the outage persists.

        Strategy (defaults are intentionally conservative; configurable via env):
        - Close up to N worst positions per step (score ascending), at most once per STEP seconds.
        - If outage persists beyond ESCALATE seconds, close all remaining positions.
        """

        step_s = int(os.getenv("BOT_SAFE_REDUCE_STEP_SECONDS", "60"))
        per_step = int(os.getenv("BOT_SAFE_REDUCE_PER_STEP", "1"))
        escalate_s = float(os.getenv("BOT_SAFE_STALE_ESCALATE_SECONDS", "900"))

        safe = self.state.setdefault("safe_signal", {})
        last_ms = int(safe.get("last_reduce_ms", 0))
        if last_ms and (now_ms - last_ms) < step_s * 1000:
            return

        # Snapshot positions (best-effort)
        try:
            pos_list = [p for p in (self.broker.list_positions() or []) if p.side == "long"]
        except Exception:
            pos_list = []

        if not pos_list:
            safe["last_reduce_ms"] = now_ms
            return

        if age_s >= escalate_s:
            safe["escalated_ms"] = now_ms
            await self._safe_close_all(reason=f"signal_stale_{int(age_s)}s")
            safe["last_reduce_ms"] = now_ms
            return

        # Close worst positions first (lowest score). If scores are unavailable, close random.
        def _score(sym: str) -> int:
            try:
                return int(self.feed.scores.get(sym.upper(), 50))
            except Exception:
                return 50

        if self.feed.scores:
            pos_list.sort(key=lambda p: _score(p.symbol))
        else:
            random.shuffle(pos_list)

        batch = pos_list[: max(1, per_step)]
        for p in batch:
            await self._close(p.symbol, p, reason=f"signal_stale_reduce_{int(age_s)}s")

        safe["last_reduce_ms"] = now_ms

    async def _safe_close_all(self, reason: str) -> None:
        # Safety mode: close positions rather than trying to adjust stops without reliable data.
        try:
            positions = self.broker.list_positions()
        except Exception:
            positions = []
        for p in positions:
            if p.side != "long":
                continue
            await self._close(p.symbol, p, reason=reason)

    def _persist(self) -> Dict:
        # Persist internal trackers with retention.
        self.state["above_since"] = self._above_since
        self.state["below_since"] = self._below_since
        self.state["missing_since"] = self._missing_since
        return self.state
