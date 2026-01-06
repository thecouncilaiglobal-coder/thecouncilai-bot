from __future__ import annotations

import getpass
import os
import sys
import time
import uuid

from bot.config import LocalConfig, load_config, save_config
from bot.control.pocketbase import PocketBaseClient
from bot.control.e2ee_client import E2EEMessenger
from bot.util.qr import print_qr


def run_setup() -> int:
    pb_url = os.getenv("POCKETBASE_URL", "http://pocketbase:8090")
    control_url = os.getenv("CONTROL_API_URL", "http://control-api:8001")
    cfg = load_config()

    print("\n" + "=" * 50)
    print("  TheCouncilAI Bot Setup")
    print("=" * 50 + "\n")

    # Step 1: Credentials (only email and password)
    print("📧 Hesap Bilgileri")
    print("-" * 30)
    email = input(f"Email [{cfg.email or ''}]: ").strip() or cfg.email
    if not email:
        print("❌ Email gerekli")
        return 2
    password = getpass.getpass("Şifre: ").strip()
    if not password:
        print("❌ Şifre gerekli")
        return 2

    cfg.email = email
    cfg.password = password
    if not cfg.device_id:
        cfg.device_id = uuid.uuid4().hex

    # NOTE: Broker and API keys are configured via mobile app (E2EE)
    # No need to ask for them here

    save_config(cfg)

    # Step 3: Authentication
    print("\n🔐 Giriş Yapılıyor...")
    pb = PocketBaseClient(pb_url)
    try:
        pb.auth_with_password(cfg.email, cfg.password)
        print("✅ Giriş başarılı")
    except Exception as e:
        print(f"❌ Giriş başarısız: {e}")
        return 3

    # Step 4: E2EE Pairing
    print("\n🔗 E2EE Eşleştirme Başlatılıyor...")
    print("-" * 30)
    
    try:
        messenger = E2EEMessenger(control_url, pb.token)
        pairing_info = messenger.init_pairing()
        
        pairing_code = pairing_info.get("pairing_code", "")
        device_id = pairing_info.get("device_id", cfg.device_id)
        expires_at = pairing_info.get("expires_at", "")
        
        # Build QR data
        qr_data = {
            "type": "thecouncilai_bot_pair",
            "device_id": device_id,
            "code": pairing_code,
            "public_key": messenger.client.public_key,
        }
        import json
        qr_string = json.dumps(qr_data)
        
        print("\n" + "=" * 50)
        print("  📱 UYGULAMADAKİ BOT EŞLEŞTIRME SAYFASINI AÇIN")
        print("=" * 50)
        print(f"\n🔑 Eşleştirme Kodu: {pairing_code}")
        print(f"🖥️  Cihaz ID: {device_id[:16]}...")
        if expires_at:
            print(f"⏰ Geçerlilik: 15 dakika")
        
        print("\n📷 QR Kodu Tarayın:")
        print("-" * 30)
        
        try:
            print_qr(qr_string)
        except Exception:
            print("(QR görüntülenemedi - kodu manuel girin)")
        
        print("\n" + "-" * 30)
        print("QR okutamıyorsanız, uygulamada kodu manuel girin.")
        print("\n⏳ Uygulama onayı bekleniyor...")
        
        # Wait for pairing
        if messenger.wait_for_pairing(timeout=900):
            print("\n✅ Eşleştirme Başarılı!")
            print("🔒 E2EE bağlantısı kuruldu")
            
            # Update PocketBase
            try:
                pb.update_me({
                    "bot_device_id": device_id,
                    "bot_paired": True,
                    "bot_last_seen": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
                })
            except Exception:
                pass
        else:
            print("\n❌ Eşleştirme zaman aşımına uğradı")
            print("Tekrar denemek için setup'ı yeniden çalıştırın.")
            return 4
            
    except Exception as e:
        print(f"\n⚠️  E2EE eşleştirme hatası: {e}")
        print("Bot yine de çalışabilir, ancak E2EE iletişim olmayacak.")
        
        # Fallback: old-style pairing
        import secrets
        pair_code = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10].upper()
        
        try:
            pb.update_me({
                "bot_device_id": cfg.device_id,
                "bot_pair_code": pair_code,
                "bot_paired": False,
                "bot_last_seen": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            })
        except Exception:
            pass
        
        deep_link = f"thecouncilai://pair?device={cfg.device_id}&code={pair_code}"
        
        print(f"\n📱 Fallback Eşleştirme Kodu: {pair_code}")
        try:
            print_qr(deep_link)
        except Exception:
            pass

    print("\n" + "=" * 50)
    print("  Setup Tamamlandı!")
    print("=" * 50)
    print("\n🚀 Bot'u başlatmak için:")
    print("   docker compose up -d bot")
    print("   veya: python -m bot.main")
    print()
    
    return 0
