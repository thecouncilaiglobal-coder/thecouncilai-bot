from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

from bot.brokers.alpaca import AlpacaBroker
from bot.brokers.ibkr import IBKRBroker
from bot.config import load_config
from bot.control.control_api import ControlApiClient
from bot.control.pocketbase import PocketBaseClient
from bot.control.user_config import UserConfigWatcher
from bot.control.e2ee_client import E2EEMessenger, BotMessages
from bot.setup import run_setup
from bot.signals.feed import SignalFeed
from bot.storage.trades_db import init_db, get_recent_trades
from bot.strategy.engine import BotEngine
from bot.util.logging import setup_logging

log = logging.getLogger("bot.main")

# Global state
_emergency_stop = False
_start_time = time.time()


class SubscriptionError(Exception):
    """Raised when user doesn't have valid subscription for bot access."""
    pass


def check_subscription_access(control_url: str, pb_token: str) -> dict:
    """
    Check if user has valid subscription for bot access.
    
    Raises SubscriptionError if:
    - User has basic plan (bot not allowed)
    - User has expired subscription/trial
    
    Returns token response on success.
    """
    ctrl = ControlApiClient(control_url)
    try:
        tok = ctrl.issue_token(pb_token, client_type="bot")
        return tok
    except RuntimeError as e:
        error_msg = str(e).lower()
        
        if "bot_not_allowed_for_basic" in error_msg:
            raise SubscriptionError(
                "Bot erişimi için Pro plan gerekli. "
                "Lütfen uygulamadan planınızı yükseltin."
            )
        elif "subscription_expired" in error_msg:
            raise SubscriptionError(
                "Abonelik süreniz dolmuş. "
                "Lütfen uygulamadan aboneliğinizi yenileyin."
            )
        elif "access_disabled" in error_msg:
            raise SubscriptionError(
                "Hesabınıza erişim devre dışı bırakılmış. "
                "Lütfen destek ile iletişime geçin."
            )
        else:
            # Re-raise other errors
            raise


async def e2ee_listener(
    messenger: E2EEMessenger,
    broker,
    usercfg: UserConfigWatcher,
    engine: BotEngine,
) -> None:
    """
    E2EE message listener task.
    Handles commands from app and sends status updates.
    """
    global _emergency_stop
    
    last_status_send = 0
    status_interval = 30  # Send status every 30 seconds
    
    while True:
        try:
            # Poll for messages from app
            messages = messenger.poll()
            
            for msg in messages:
                msg_type = msg.get("type", "")
                
                if msg_type == "status_request":
                    # Send status response
                    await _send_status(messenger, broker, usercfg)
                    
                elif msg_type == "config_update":
                    # Handle config update
                    trade_mode = msg.get("trade_mode")
                    risk_profile = msg.get("risk_profile")
                    
                    if trade_mode:
                        log.info("e2ee_config_update: trade_mode=%s", trade_mode)
                        # Trade mode is handled by broker URL, would need restart
                        
                    if risk_profile:
                        log.info("e2ee_config_update: risk_profile=%s", risk_profile)
                        # This would update via PocketBase normally
                        
                elif msg_type == "command":
                    action = msg.get("action", "")
                    
                    if action == "emergency_stop":
                        log.warning("e2ee_command: EMERGENCY STOP received")
                        _emergency_stop = True
                        engine.pause()
                        messenger.send(BotMessages.error("emergency_stop", "Bot durduruldu"))
                        
                    elif action == "pause":
                        log.info("e2ee_command: pause")
                        engine.pause()
                        
                    elif action == "resume":
                        log.info("e2ee_command: resume")
                        _emergency_stop = False
                        engine.resume()
                        
                    elif action == "sync_config":
                        log.info("e2ee_command: sync_config")
                        usercfg.refresh()
                        
                elif msg_type == "api_keys_update":
                    # API keys update would require restart
                    log.info("e2ee_api_keys_update: received (requires restart)")
                    messenger.send(BotMessages.error(
                        "restart_required",
                        "API key güncellemesi için bot'u yeniden başlatın"
                    ))
            
            # Send periodic status
            now = time.time()
            if now - last_status_send > status_interval:
                await _send_status(messenger, broker, usercfg)
                last_status_send = now
                
        except Exception as e:
            log.warning("e2ee_listener_error: %s", e)
        
        await asyncio.sleep(3)


async def _send_status(messenger: E2EEMessenger, broker, usercfg: UserConfigWatcher):
    """Send status update to app via E2EE."""
    global _emergency_stop, _start_time
    
    try:
        # Get balance and positions from broker
        balance = 0.0
        positions = []
        api_key_valid = False
        
        try:
            account = broker.get_account()
            balance = float(account.get("equity", 0) or account.get("cash", 0))
            api_key_valid = True
        except Exception as e:
            log.debug("broker_account_failed: %s", e)
        
        try:
            pos_list = broker.get_positions()
            positions = [
                {
                    "symbol": p.get("symbol"),
                    "qty": float(p.get("qty", 0)),
                    "avg_entry": float(p.get("avg_entry_price", 0)),
                    "current_price": float(p.get("current_price", 0)),
                    "unrealized_pl": float(p.get("unrealized_pl", 0)),
                }
                for p in pos_list
            ]
        except Exception as e:
            log.debug("broker_positions_failed: %s", e)
        
        # Get last trade
        last_trade = None
        try:
            trades = get_recent_trades(limit=1)
            if trades:
                t = trades[0]
                last_trade = {
                    "symbol": t.get("symbol"),
                    "side": t.get("side"),
                    "qty": t.get("qty"),
                    "price": t.get("price"),
                    "pnl": t.get("pnl"),
                    "ts": t.get("timestamp"),
                }
        except Exception:
            pass
        
        # Build and send status
        status = BotMessages.status_response(
            balance=balance,
            positions=positions,
            api_key_valid=api_key_valid,
            trade_mode=usercfg.latest.trade_mode,
            uptime_seconds=int(time.time() - _start_time),
            last_trade=last_trade,
        )
        
        if _emergency_stop:
            status["paused"] = True
            status["pause_reason"] = "emergency_stop"
        
        messenger.send(status)
        
    except Exception as e:
        log.warning("send_status_failed: %s", e)


async def _run_bot() -> int:
    global _start_time
    _start_time = time.time()
    
    pb_url = os.getenv("POCKETBASE_URL", "http://pocketbase:8090")
    control_url = os.getenv("CONTROL_API_URL", "http://control-api:8001")
    brain_url = os.getenv("BRAIN_API_URL", "http://brain-api:8080")
    ws_url = os.getenv("CENTRIFUGO_WS_URL", "ws://centrifugo:8000/connection/websocket")

    cfg = load_config()
    if not cfg.email or not cfg.password:
        log.error("missing_credentials: run 'python -m bot.main setup' first")
        return 2

    # Authenticate with PocketBase
    log.info("authenticating with PocketBase...")
    pb = PocketBaseClient(pb_url)
    try:
        pb.auth_with_password(cfg.email, cfg.password)
    except Exception as e:
        log.error("auth_failed: %s", e)
        print("\n❌ Giriş başarısız. E-posta veya şifrenizi kontrol edin.\n")
        return 2

    usercfg = UserConfigWatcher(pb, fallback_risk_profile=cfg.risk_profile)

    # Check subscription and get Centrifugo token
    log.info("checking subscription status...")
    token = None
    try:
        tok = check_subscription_access(control_url, pb.token)
        token = tok.get("token")
        plan = tok.get("plan", "unknown")
        log.info("subscription_ok: plan=%s", plan)
        print(f"\n✅ Abonelik aktif: {plan.upper()} planı\n")
    except SubscriptionError as e:
        log.error("subscription_error: %s", e)
        print(f"\n❌ {e}\n")
        return 3
    except Exception as e:
        log.warning("centrifugo_token_failed err=%s", e)
        print(f"\n⚠️ Bağlantı hatası: {e}\n")
        # Continue without token - will retry later

    # Initialize E2EE messenger
    messenger = None
    try:
        messenger = E2EEMessenger(control_url, pb.token)
        if messenger.client.is_paired:
            log.info("e2ee_paired: encrypted communication active")
            print("🔒 E2EE bağlantısı aktif\n")
        else:
            log.warning("e2ee_not_paired: run setup to pair with app")
    except Exception as e:
        log.warning("e2ee_init_failed: %s", e)

    feed = SignalFeed(
        ws_url=ws_url,
        brain_api_url=brain_url,
        pb_token=pb.token,
        centrifugo_token=token,
    )

    # Broker init
    data_base_url = os.getenv("ALPACA_DATA_BASE_URL", "https://data.alpaca.markets")
    if cfg.broker == "alpaca":
        broker = AlpacaBroker(
            api_key=cfg.alpaca.api_key,
            api_secret=cfg.alpaca.api_secret,
            trading_base_url=cfg.alpaca.trading_base_url,
            data_base_url=data_base_url,
        )
    else:
        broker = IBKRBroker(host=cfg.ibkr.host, port=cfg.ibkr.port, client_id=cfg.ibkr.client_id)

    init_db()

    engine = BotEngine(
        broker=broker,
        feed=feed,
        profile_name=cfg.risk_profile,
        get_panic=lambda: usercfg.latest.panic or _emergency_stop,
        get_profile=lambda: usercfg.latest.risk_profile,
    )

    async def pair_gate() -> None:
        # Only enforce pairing if PB supports the flag.
        while not usercfg.latest.bot_paired:
            log.warning("bot_not_paired: waiting for app pairing")
            await asyncio.sleep(10)

    # Build task list
    tasks = [
        asyncio.create_task(usercfg.run()),
        asyncio.create_task(feed.run()),
        asyncio.create_task(pair_gate()),
        asyncio.create_task(engine.run()),
    ]
    
    # Add E2EE listener if paired
    if messenger and messenger.client.is_paired:
        tasks.append(asyncio.create_task(
            e2ee_listener(messenger, broker, usercfg, engine)
        ))

    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    for d in done:
        exc = d.exception()
        if exc:
            raise exc
    return 0


def main() -> None:
    setup_logging()

    if len(sys.argv) > 1 and sys.argv[1].lower() == "setup":
        sys.exit(run_setup())

    print("\n" + "=" * 50)
    print("  TheCouncilAI Trading Bot")
    print("=" * 50)

    try:
        exit_code = asyncio.run(_run_bot())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n👋 Bot durduruldu.\n")
    except Exception as e:
        log.exception("unexpected_error")
        print(f"\n❌ Beklenmeyen hata: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
