from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from bot.config import state_dir


def _now_ms() -> int:
    return int(time.time() * 1000)


def _state_path() -> Path:
    return state_dir() / "runtime_state.json"


def load_state() -> Dict[str, Any]:
    p = _state_path()
    if not p.exists():
        return {
            "v": 1,
            "positions": {},
            "cooldowns": {},
            "opened_at_ms": {},
            "day": {},
            "health": {},
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        # Corruption fallback
        return {
            "v": 1,
            "positions": {},
            "cooldowns": {},
            "opened_at_ms": {},
            "day": {},
            "health": {},
        }


def save_state(state: Dict[str, Any]) -> None:
    p = _state_path()
    state["health"] = state.get("health") or {}
    state["health"]["saved_at_ms"] = _now_ms()

    # Keep last 3 backups
    try:
        if p.exists():
            for i in range(2, 0, -1):
                older = p.with_suffix(f".bak{i}.json")
                newer = p.with_suffix(f".bak{i+1}.json")
                if older.exists():
                    os.replace(older, newer)
            os.replace(p, p.with_suffix(".bak1.json"))
    except Exception:
        pass

    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, p)

    try:
        os.chmod(p, 0o600)
    except Exception:
        pass
