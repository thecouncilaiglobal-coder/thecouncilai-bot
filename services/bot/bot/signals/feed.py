from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional

import requests
import websockets

log = logging.getLogger("bot.signals")


class SignalFeed:
    """Maintains the latest public score map (symbol -> score) using:

    1) Centrifugo WS channel `signals:delta` if possible
    2) Fallback polling of Brain API `/snapshot`

    The public payload remains minimal: only the single score per symbol.
    """

    def __init__(
        self,
        brain_api_url: str,
        centrifugo_ws_url: str,
        centrifugo_token: str,
        poll_seconds: float = 20.0,
    ):
        self.brain_api_url = brain_api_url.rstrip("/")
        self.ws_url = centrifugo_ws_url
        self.token = centrifugo_token
        self.poll_seconds = poll_seconds

        self.scores: Dict[str, int] = {}
        self.epoch: Optional[int] = None
        self.last_update_ms: Optional[int] = None

        self._stop = asyncio.Event()
        self._ws_ok = False

    @property
    def ws_ok(self) -> bool:
        return self._ws_ok

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        # Start polling loop always, but when WS works it becomes lightweight.
        ws_task = asyncio.create_task(self._ws_loop())
        poll_task = asyncio.create_task(self._poll_loop())
        await self._stop.wait()
        ws_task.cancel()
        poll_task.cancel()

    async def _poll_loop(self) -> None:
        # Initial snapshot so we have a baseline.
        while not self._stop.is_set():
            try:
                snap = requests.get(f"{self.brain_api_url}/snapshot", timeout=15).json()
                # Expected format: {e, t, m:[[sym,score],...]}
                epoch = snap.get("e")
                ts = snap.get("t")
                m = snap.get("m") or []
                for sym, sc in m:
                    self.scores[str(sym).upper()] = int(sc)
                self.epoch = int(epoch) if epoch is not None else self.epoch
                self.last_update_ms = int(ts) if ts is not None else int(time.time() * 1000)
                if not self._ws_ok:
                    log.info("snapshot_ok symbols=%d epoch=%s", len(self.scores), self.epoch)
            except Exception as e:
                log.warning("snapshot_failed err=%s", e)

            await asyncio.sleep(self.poll_seconds)

    async def _ws_loop(self) -> None:
        # Best-effort Centrifugo protocol v2.
        # If protocol changes, we keep working via snapshot polling.
        backoff = 2.0
        while not self._stop.is_set():
            try:
                async with websockets.connect(self.ws_url, ping_interval=20, ping_timeout=20) as ws:
                    self._ws_ok = True
                    backoff = 2.0
                    # connect
                    await ws.send(json.dumps({"id": 1, "connect": {"token": self.token, "name": "thecouncilai-bot"}}))
                    log.info("ws_connected")

                    while not self._stop.is_set():
                        raw = await ws.recv()
                        msg = json.loads(raw)

                        # Ping handling (protocol tolerant)
                        if "ping" in msg:
                            mid = msg.get("id")
                            if mid is not None:
                                await ws.send(json.dumps({"id": mid, "pong": {}}))
                            continue

                        # Publications can arrive as push->pub or push->publication.
                        push = msg.get("push")
                        if not push:
                            continue

                        pub = push.get("pub") or push.get("publication")
                        if not pub:
                            continue

                        data = pub.get("data")
                        if not isinstance(data, dict):
                            continue

                        # Expected delta payload: {e, t, d:[[sym,score],...]}
                        epoch = data.get("e")
                        ts = data.get("t")
                        d = data.get("d") or []
                        for sym, sc in d:
                            self.scores[str(sym).upper()] = int(sc)
                        if epoch is not None:
                            self.epoch = int(epoch)
                        if ts is not None:
                            self.last_update_ms = int(ts)

            except asyncio.CancelledError:
                return
            except Exception as e:
                self._ws_ok = False
                log.warning("ws_failed err=%s", e)
                await asyncio.sleep(backoff)
                backoff = min(60.0, backoff * 1.8)
