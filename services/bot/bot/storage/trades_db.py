from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Optional

from bot.config import state_dir


def _db_path() -> Path:
    return state_dir() / "trades.sqlite"


def init_db() -> None:
    p = _db_path()
    con = sqlite3.connect(p)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts_ms INTEGER NOT NULL,
              symbol TEXT NOT NULL,
              side TEXT NOT NULL,
              qty REAL NOT NULL,
              score INTEGER NOT NULL,
              price_est REAL,
              reason TEXT,
              broker TEXT,
              mode TEXT
            );
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_trades_ts ON trades(ts_ms)")
        con.commit()
    finally:
        con.close()


def log_trade(
    symbol: str,
    side: str,
    qty: float,
    score: int,
    price_est: Optional[float],
    reason: str,
    broker: str,
    mode: str,
) -> None:
    con = sqlite3.connect(_db_path())
    try:
        con.execute(
            "INSERT INTO trades(ts_ms,symbol,side,qty,score,price_est,reason,broker,mode) VALUES(?,?,?,?,?,?,?,?,?)",
            (int(time.time() * 1000), symbol, side, float(qty), int(score), price_est, reason, broker, mode),
        )
        con.commit()
    finally:
        con.close()
