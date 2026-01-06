from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

RiskProfile = Literal["conservative", "balanced", "aggressive"]
BrokerName = Literal["alpaca", "ibkr"]


class AlpacaCreds(BaseModel):
    api_key: str = ""
    api_secret: str = ""
    # Trading endpoint; keep paper by default. App can later switch it.
    trading_base_url: str = "https://paper-api.alpaca.markets"


class IBKRCreds(BaseModel):
    # ib_insync connection (user must run IB Gateway/TWS separately)
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 7


class LocalConfig(BaseModel):
    version: int = 1

    # PocketBase user auth (same as mobile app)
    email: str = ""
    password: str = ""

    # Pairing
    device_id: str = ""

    # Trading
    broker: BrokerName = "alpaca"
    alpaca: AlpacaCreds = Field(default_factory=AlpacaCreds)
    ibkr: IBKRCreds = Field(default_factory=IBKRCreds)

    # Default risk profile if server-side value is empty
    risk_profile: RiskProfile = "balanced"


def state_dir() -> Path:
    d = Path(os.getenv("BOT_STATE_DIR", "/shared/bot")).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return state_dir() / "config.json"


def load_config() -> LocalConfig:
    p = config_path()
    if not p.exists():
        return LocalConfig()
    data = json.loads(p.read_text(encoding="utf-8"))
    return LocalConfig.model_validate(data)


def save_config(cfg: LocalConfig) -> None:
    p = config_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg.model_dump(), indent=2), encoding="utf-8")
    os.replace(tmp, p)

    # Best-effort permission hardening
    try:
        os.chmod(p, 0o600)
    except Exception:
        pass
