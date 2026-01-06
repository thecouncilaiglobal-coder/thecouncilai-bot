from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import requests


class PocketBaseClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.token: str = ""
        self.user_id: str = ""

    def auth_with_password(self, email: str, password: str) -> Dict[str, Any]:
        url = f"{self.base_url}/api/collections/users/auth-with-password"
        r = requests.post(url, json={"identity": email, "password": password}, timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"pb_auth_failed status={r.status_code} body={r.text[:200]}")
        data = r.json()
        self.token = data.get("token") or ""
        rec = data.get("record") or {}
        self.user_id = rec.get("id") or ""
        return data

    def auth_refresh(self) -> Dict[str, Any]:
        url = f"{self.base_url}/api/collections/users/auth-refresh"
        r = requests.post(url, headers=self._auth_headers(), timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"pb_refresh_failed status={r.status_code} body={r.text[:200]}")
        data = r.json()
        self.token = data.get("token") or self.token
        rec = data.get("record") or {}
        self.user_id = rec.get("id") or self.user_id
        return data

    def get_me(self) -> Dict[str, Any]:
        # For auth records, record ID is user id.
        url = f"{self.base_url}/api/collections/users/records/{self.user_id}"
        r = requests.get(url, headers=self._auth_headers(), timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"pb_get_me_failed status={r.status_code} body={r.text[:200]}")
        return r.json()

    def update_me(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/api/collections/users/records/{self.user_id}"
        r = requests.patch(url, headers=self._auth_headers(), json=fields, timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"pb_update_me_failed status={r.status_code} body={r.text[:200]}")
        return r.json()

    def _auth_headers(self) -> Dict[str, str]:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}
