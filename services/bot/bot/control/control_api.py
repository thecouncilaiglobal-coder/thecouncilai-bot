from __future__ import annotations

from typing import Any, Dict

import requests


class ControlApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def issue_token(self, pb_token: str, client_type: str = "bot") -> Dict[str, Any]:
        url = f"{self.base_url}/control/token"
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {pb_token}"},
            json={"client_type": client_type},
            timeout=15,
        )
        if r.status_code != 200:
            raise RuntimeError(f"control_token_failed status={r.status_code} body={r.text[:200]}")
        return r.json()
