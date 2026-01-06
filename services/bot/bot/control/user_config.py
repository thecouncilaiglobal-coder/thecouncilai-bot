from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from bot.control.pocketbase import PocketBaseClient

log = logging.getLogger("bot.usercfg")


@dataclass
class UserConfig:
    risk_profile: str = "balanced"
    panic: bool = False
    bot_paired: bool = True
    trade_mode: str = "paper"  # app-managed; bot uses for base URL selection in future


class UserConfigWatcher:
    def __init__(self, pb: PocketBaseClient, fallback_risk_profile: str = "balanced"):
        self.pb = pb
        self.fallback_risk_profile = fallback_risk_profile
        self.latest: UserConfig = UserConfig(risk_profile=fallback_risk_profile)
        self._last_fetch_ms: int = 0

    async def run(self) -> None:
        interval = 10
        while True:
            try:
                self.refresh()
            except Exception as e:
                log.warning("user_config_refresh_failed err=%s", e)
            await asyncio.sleep(interval)

    def refresh(self) -> None:
        rec = self.pb.get_me()
        rp = (rec.get("risk_profile") or rec.get("bot_risk_profile") or self.fallback_risk_profile)
        panic = bool(rec.get("panic") or rec.get("bot_panic") or False)
        paired = rec.get("bot_paired")
        if paired is None:
            paired = True  # backwards compatibility
        mode = (rec.get("trade_mode") or rec.get("bot_trade_mode") or "paper")

        self.latest = UserConfig(
            risk_profile=str(rp),
            panic=panic,
            bot_paired=bool(paired),
            trade_mode=str(mode),
        )
        self._last_fetch_ms = int(time.time() * 1000)
