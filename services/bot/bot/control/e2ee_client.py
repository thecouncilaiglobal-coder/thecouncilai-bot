"""
E2EE Client for Bot

Handles X25519 key exchange and AES-GCM encryption for secure
app-bot communication.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

import requests

log = logging.getLogger("bot.e2ee")


@dataclass
class E2EEConfig:
    """E2EE configuration stored locally."""
    private_key_b64: str = ""
    public_key_b64: str = ""
    shared_secret_b64: str = ""
    app_public_key_b64: str = ""
    paired: bool = False
    device_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "private_key_b64": self.private_key_b64,
            "public_key_b64": self.public_key_b64,
            "shared_secret_b64": self.shared_secret_b64,
            "app_public_key_b64": self.app_public_key_b64,
            "paired": self.paired,
            "device_id": self.device_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "E2EEConfig":
        return cls(
            private_key_b64=data.get("private_key_b64", ""),
            public_key_b64=data.get("public_key_b64", ""),
            shared_secret_b64=data.get("shared_secret_b64", ""),
            app_public_key_b64=data.get("app_public_key_b64", ""),
            paired=data.get("paired", False),
            device_id=data.get("device_id", ""),
        )


class E2EEClient:
    """E2EE client for bot communication."""
    
    CONFIG_FILE = os.path.expanduser("~/.thecouncilai/e2ee_config.json")
    
    def __init__(self):
        self.config = self._load_config()
        self._shared_secret: Optional[bytes] = None
        
        if self.config.shared_secret_b64:
            self._shared_secret = base64.b64decode(self.config.shared_secret_b64)
    
    def _load_config(self) -> E2EEConfig:
        """Load E2EE config from file."""
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, "r") as f:
                    return E2EEConfig.from_dict(json.load(f))
        except Exception as e:
            log.warning("e2ee_config_load_failed: %s", e)
        return E2EEConfig()
    
    def _save_config(self):
        """Save E2EE config to file."""
        os.makedirs(os.path.dirname(self.CONFIG_FILE), exist_ok=True)
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(self.config.to_dict(), f, indent=2)
    
    def generate_keypair(self) -> str:
        """
        Generate X25519 key pair.
        Returns public key as base64.
        """
        private_key = X25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Serialize keys
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        
        self.config.private_key_b64 = base64.b64encode(private_bytes).decode()
        self.config.public_key_b64 = base64.b64encode(public_bytes).decode()
        self._save_config()
        
        return self.config.public_key_b64
    
    def derive_shared_secret(self, app_public_key_b64: str):
        """
        Derive shared secret from app's public key.
        Uses X25519 key exchange + HKDF.
        """
        if not self.config.private_key_b64:
            raise ValueError("No private key - call generate_keypair first")
        
        # Load keys
        private_bytes = base64.b64decode(self.config.private_key_b64)
        app_public_bytes = base64.b64decode(app_public_key_b64)
        
        private_key = X25519PrivateKey.from_private_bytes(private_bytes)
        app_public_key = X25519PublicKey.from_public_bytes(app_public_bytes)
        
        # Key exchange
        shared_key = private_key.exchange(app_public_key)
        
        # Derive 256-bit key using HKDF
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"thecouncilai-e2ee-v1",
            info=b"app-bot-communication",
        )
        derived_key = hkdf.derive(shared_key)
        
        self._shared_secret = derived_key
        self.config.shared_secret_b64 = base64.b64encode(derived_key).decode()
        self.config.app_public_key_b64 = app_public_key_b64
        self.config.paired = True
        self._save_config()
        
        log.info("e2ee_paired: shared secret derived")
    
    def encrypt(self, plaintext: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt message using AES-256-GCM.
        Returns envelope with nonce and ciphertext.
        """
        if not self._shared_secret:
            raise ValueError("Not paired - no shared secret")
        
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(self._shared_secret)
        
        plaintext_bytes = json.dumps(plaintext).encode()
        ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)
        
        return {
            "v": 1,
            "nonce_b64": base64.b64encode(nonce).decode(),
            "ciphertext_b64": base64.b64encode(ciphertext).decode(),
            "ts": int(time.time() * 1000),
        }
    
    def decrypt(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt message from envelope."""
        if not self._shared_secret:
            raise ValueError("Not paired - no shared secret")
        
        nonce = base64.b64decode(envelope["nonce_b64"])
        ciphertext = base64.b64decode(envelope["ciphertext_b64"])
        
        aesgcm = AESGCM(self._shared_secret)
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        
        return json.loads(plaintext_bytes.decode())
    
    @property
    def is_paired(self) -> bool:
        return self.config.paired and bool(self._shared_secret)
    
    @property
    def public_key(self) -> str:
        return self.config.public_key_b64
    
    @property
    def device_id(self) -> str:
        if not self.config.device_id:
            import uuid
            self.config.device_id = uuid.uuid4().hex
            self._save_config()
        return self.config.device_id


class E2EEMessenger:
    """
    High-level messenger for sending/receiving E2EE messages.
    """
    
    def __init__(self, control_api_url: str, pb_token: str):
        self.control_url = control_api_url.rstrip("/")
        self.pb_token = pb_token
        self.client = E2EEClient()
        self._last_message_id: Optional[str] = None
    
    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.pb_token}"}
    
    def init_pairing(self) -> Dict[str, Any]:
        """Initialize pairing session and return pairing info."""
        public_key = self.client.generate_keypair()
        
        r = requests.post(
            f"{self.control_url}/control/pair/init",
            headers=self._headers(),
            json={
                "device_id": self.client.device_id,
                "public_key": public_key,
            },
            timeout=15,
        )
        
        if r.status_code != 200:
            raise RuntimeError(f"pair_init_failed: {r.status_code} {r.text[:200]}")
        
        return r.json()
    
    def wait_for_pairing(self, timeout: int = 900) -> bool:
        """Wait for app to approve pairing."""
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                r = requests.get(
                    f"{self.control_url}/control/pair/status",
                    headers=self._headers(),
                    timeout=10,
                )
                
                if r.status_code == 200:
                    data = r.json()
                    if data.get("paired"):
                        app_public_key = data.get("app_public_key")
                        if app_public_key:
                            self.client.derive_shared_secret(app_public_key)
                            return True
            except Exception as e:
                log.warning("pair_status_check_failed: %s", e)
            
            time.sleep(3)
        
        return False
    
    def send(self, message: Dict[str, Any]) -> bool:
        """Send encrypted message to app."""
        if not self.client.is_paired:
            raise ValueError("Not paired")
        
        envelope = self.client.encrypt(message)
        
        try:
            r = requests.post(
                f"{self.control_url}/control/e2ee/send/bot",
                headers=self._headers(),
                json={"envelope": envelope},
                timeout=10,
            )
            return r.status_code == 200
        except Exception as e:
            log.warning("e2ee_send_failed: %s", e)
            return False
    
    def poll(self) -> List[Dict[str, Any]]:
        """Poll for messages from app."""
        if not self.client.is_paired:
            return []
        
        try:
            params = {"direction": "app_to_bot"}
            if self._last_message_id:
                params["since_id"] = self._last_message_id
            
            r = requests.get(
                f"{self.control_url}/control/e2ee/poll",
                headers=self._headers(),
                params=params,
                timeout=10,
            )
            
            if r.status_code != 200:
                return []
            
            data = r.json()
            messages = []
            
            for msg in data.get("messages", []):
                self._last_message_id = msg.get("id")
                try:
                    decrypted = self.client.decrypt(msg.get("envelope", {}))
                    messages.append(decrypted)
                except Exception as e:
                    log.warning("e2ee_decrypt_failed: %s", e)
            
            return messages
        except Exception as e:
            log.warning("e2ee_poll_failed: %s", e)
            return []


# Message builders for common message types
class BotMessages:
    """Helper class to build standard bot messages."""
    
    @staticmethod
    def status_response(
        balance: float,
        positions: List[Dict],
        api_key_valid: bool,
        trade_mode: str,
        uptime_seconds: int,
        last_trade: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        return {
            "type": "status_response",
            "ts": int(time.time() * 1000),
            "balance": balance,
            "positions": positions,
            "api_key_valid": api_key_valid,
            "trade_mode": trade_mode,
            "uptime_seconds": uptime_seconds,
            "last_trade": last_trade,
        }
    
    @staticmethod
    def trade_event(
        symbol: str,
        side: str,
        qty: float,
        price: float,
        pnl: Optional[float] = None,
        trade_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "type": "trade_event",
            "ts": int(time.time() * 1000),
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "pnl": pnl,
            "trade_id": trade_id,
        }
    
    @staticmethod
    def trade_history(trades: List[Dict]) -> Dict[str, Any]:
        return {
            "type": "trade_history",
            "ts": int(time.time() * 1000),
            "trades": trades,
        }
    
    @staticmethod
    def error(code: str, message: str) -> Dict[str, Any]:
        return {
            "type": "error",
            "ts": int(time.time() * 1000),
            "code": code,
            "message": message,
        }
    
    @staticmethod
    def heartbeat() -> Dict[str, Any]:
        return {
            "type": "heartbeat",
            "ts": int(time.time() * 1000),
        }
