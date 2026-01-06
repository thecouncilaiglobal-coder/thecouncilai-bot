# Configuration Guide - TheCouncilAI Bot

Bot'un tüm konfigürasyon seçenekleri ve ayarları.

## Environment Değişkenleri

### Backend Services

#### POCKETBASE_URL
- **Varsayılan**: `http://pocketbase:8090`
- **Açıklama**: PocketBase authentication service URL
- **Örnek**: `https://your-pocketbase.com`

Kullanıcı kimlik doğrulama ve profil yönetimi için kullanılır.

#### CONTROL_API_URL
- **Varsayılan**: `http://control-api:8001`
- **Açıklama**: Control API service URL
- **Örnek**: `https://your-control-api.com`

Token yönetimi, abonelik kontrolü ve E2EE için kullanılır.

#### BRAIN_API_URL
- **Varsayılan**: `http://brain-api:8080`
- **Açıklama**: Brain AI service URL
- **Örnek**: `https://your-brain-api.com`

AI trading sinyallerini almak için kullanılır.

#### CENTRIFUGO_WS_URL
- **Varsayılan**: `ws://centrifugo:8000/connection/websocket`
- **Açıklama**: Centrifugo WebSocket URL
- **Örnek**: `wss://your-centrifugo.com/connection/websocket`

Real-time sinyal güncellemeleri için WebSocket bağlantısı.

### Broker Configuration

#### ALPACA_DATA_BASE_URL
- **Varsayılan**: `https://data.alpaca.markets`
- **Açıklama**: Alpaca market data URL
- **Değiştirmeyin**: Alpaca'nın resmi data endpoint'i

### Bot State

#### BOT_STATE_DIR
- **Varsayılan**: `/shared/bot`
- **Açıklama**: Bot configuration ve state directory
- **Not**: Docker volume ile persist edilir

Bu dizinde saklanır:
- `config.json`: Bot credentials ve settings
- `trades.db`: Trade history database

## Local Configuration (config.json)

Setup komutu çalıştırıldığında oluşturulur: `docker-compose run --rm bot python -m bot.main setup`

### Yapı

```json
{
  "version": 1,
  "email": "user@example.com",
  "password": "encrypted_password",
  "device_id": "unique_device_id",
  "broker": "alpaca",
  "alpaca": {
    "api_key": "PK...",
    "api_secret": "...",
    "trading_base_url": "https://paper-api.alpaca.markets"
  },
  "ibkr": {
    "host": "127.0.0.1",
    "port": 7497,
    "client_id": 7
  },
  "risk_profile": "balanced"
}
```

### Alanlar

#### email / password
- **Tip**: String
- **Açıklama**: PocketBase hesap bilgileri
- **Nasıl değiştirilir**: `python -m bot.main setup` komutunu yeniden çalıştırın

#### device_id
- **Tip**: String (UUID)
- **Açıklama**: E2EE için unique device identifier
- **Otomatik oluşturulur**: Setup sırasında

#### broker
- **Değerler**: `"alpaca"` veya `"ibkr"`
- **Açıklama**: Kullanılacak broker
- **Nasıl değiştirilir**: Setup komutunu yeniden çalıştırın

#### alpaca.trading_base_url
- **Paper Trading**: `https://paper-api.alpaca.markets`
- **Live Trading**: `https://api.alpaca.markets`
- **⚠️ UYARI**: Live trading gerçek para kullanır!

#### ibkr.port
- **Paper Trading**: `7497`
- **Live Trading**: `7496`
- **Not**: IB Gateway/TWS'de ayarlanan port ile eşleşmeli

#### risk_profile
- **Değerler**: `"conservative"`, `"balanced"`, `"aggressive"`
- **Varsayılan**: `"balanced"`
- **Nasıl değiştirilir**: Mobil uygulamadan veya manual edit

## Risk Profiles

### Conservative (Muhafazakar)

```yaml
Position Sizing: Küçük (portfolio'nun %5-10%)
Max Open Positions: 2-3
Stop Loss: Sıkı (1-2%)
Take Profit: Düşük hedefler (2-3%)
Signal Threshold: Yüksek (sadece güçlü sinyaller)
```

**Kimler için:**
- Düşük risk toleransı olanlar
- Küçük sermayeli hesaplar
- Yeni başlayanlar

### Balanced (Dengeli)

```yaml
Position Sizing: Orta (portfolio'nun %10-20%)
Max Open Positions: 3-5
Stop Loss: Orta (2-3%)
Take Profit: Orta hedefler (3-5%)
Signal Threshold: Orta
```

**Kimler için:**
- Orta risk toleransı olanlar
- Çoğu kullanıcı için önerilir
- Dengeli risk/kazanç

### Aggressive (Agresif)

```yaml
Position Sizing: Büyük (portfolio'nun %20-30%)
Max Open Positions: 5-8
Stop Loss: Geniş (3-5%)
Take Profit: Yüksek hedefler (5-10%)
Signal Threshold: Düşük (daha fazla sinyal)
```

**Kimler için:**
- Yüksek risk toleransı olanlar
- Büyük sermayeli hesaplar
- Deneyimli traderlar

**⚠️ UYARI**: Agresif profil büyük kayıplara yol açabilir!

## Broker-Specific Configuration

### Alpaca

#### Paper Trading vs Live Trading

**Paper Trading (Test)**:
```json
{
  "trading_base_url": "https://paper-api.alpaca.markets"
}
```
- Gerçek para kullanılmaz
- $100,000 virtual money
- Test için ideal
- Gerçek market data

**Live Trading (Gerçek)**:
```json
{
  "trading_base_url": "https://api.alpaca.markets"
}
```
- ⚠️ GERÇEK PARA KULLANILIR!
- Minimum hesap: $0 (fractional shares)
- PDT rules uygulanır (Pattern Day Trader)

#### API Key Permissions

Alpaca Dashboard'da API key oluştururken:

- ✅ **Account**: Read + Write
- ✅ **Trading**: Enabled
- ⚠️ **Transfer**: Disabled (güvenlik için)

### Interactive Brokers (IBKR)

#### IB Gateway / TWS Configuration

1. **TWS API Settings**:
   - Enable ActiveX and Socket Clients: ✅
   - Socket Port: `7497` (paper) / `7496` (live)
   - Trusted IP Addresses: `127.0.0.1` (veya Docker IP)
   - Read-Only API: ❌ (bot trade yapmalı)

2. **Login**:
   - Paper account için: `edemo` username kullanın
   - Live account için: gerçek credentials

3. **Auto-Restart**:
   - Settings → Lock and Exit → Auto restart: ✅
   - Restart time: Market'in kapalı olduğu bir saat seçin

#### client_id

```json
{
  "client_id": 7
}
```

- Her bot instance için unique olmalı
- 0-999 arası değer
- Aynı TWS'ye birden fazla bot bağlanıyorsa farklı ID'ler kullanın

## Advanced Configuration

### Watchtower Auto-Update

#### Update Interval

`.env` dosyasında:

```env
# Her 24 saatte bir kontrol (varsayılan)
WATCHTOWER_POLL_INTERVAL=86400

# Her 12 saatte bir
WATCHTOWER_POLL_INTERVAL=43200

# Her 6 saatte bir
WATCHTOWER_POLL_INTERVAL=21600
```

#### Disable Auto-Update

Otomatik güncellemeyi kapatmak için:

```bash
# docker-compose.yml'den watchtower servisini komutla:
docker-compose up -d bot
# (watchtower olmadan sadece bot)
```

veya `docker-compose.yml`'de:

```yaml
services:
  bot:
    labels:
      - "com.centurylinklabs.watchtower.enable=false"
```

### Docker Volume Location

Docker volume'u manuel path'e değiştirmek için `docker-compose.yml`:

```yaml
volumes:
  bot-data:
    driver: local
    driver_opts:
      type: none
      device: /path/to/your/data
      o: bind
```

### Network Configuration

External network kullanmak için (örn: TheCouncilAI full stack ile):

```yaml
networks:
  bot-network:
    external: true
    name: thecouncilai-network
```

## Security Best Practices

### 1. Encrypt config.json

File permissions:

```bash
# Sadece owner okuyabilir
chmod 600 /shared/bot/config.json
```

Bot otomatik olarak yapar, ama kontrol edin.

### 2. Environment Variables

`.env` dosyası sensitive data içerir:

```bash
# Permissions
chmod 600 .env

# Git'e eklenmesin
echo ".env" >> .gitignore
```

### 3. API Key Rotation

Düzenli olarak API key'leri yenileyin:

1. Broker dashboard'da yeni key oluşturun
2. Setup komutunu çalıştırın
3. Yeni key'i girin
4. Eski key'i devre dışı bırakın

### 4. E2EE Device Management

Cihaz kaybında:

1. Mobil uygulamadan "Unpair All Devices"
2. Setup komutunu yeniden çalıştırın
3. Yeni QR kod ile pair edin

## Configuration Changes

### Runtime'da Değiştirilebilir (Bot yeniden başlatmadan)

Mobil uygulamadan:

- ✅ Risk profile
- ✅ Panic mode (emergency stop)
- ✅ Bot pairing

### Restart Gerektiren Değişiklikler

- ❌ Broker type (alpaca ↔ ibkr)
- ❌ API keys
- ❌ Email/password
- ❌ Trading mode (paper ↔ live)
- ❌ Backend URLs

Değiştirmek için:

```bash
# 1. Setup'ı yeniden çalıştır
docker-compose run --rm bot python -m bot.main setup

# 2. Bot'u yeniden başlat
docker-compose restart bot
```

## Troubleshooting Configuration

### Config.json bulunamıyor

```bash
# Kontrol et
docker-compose exec bot ls -la /shared/bot/

# Yoksa setup çalıştır
docker-compose run --rm bot python -m bot.main setup
```

### Invalid JSON

```bash
# Config'i görüntüle
docker-compose exec bot cat /shared/bot/config.json

# Syntax error varsa manuel düzelt veya setup'ı yeniden çalıştır
```

### Permission denied

```bash
# Volume permissions kontrol et
docker-compose exec bot ls -la /shared/bot/config.json

# Fix
docker-compose exec bot chmod 600 /shared/bot/config.json
```

## Örnek Konfigürasyonlar

### Örnek 1: Local Stack + Alpaca Paper

```env
# .env
POCKETBASE_URL=http://pocketbase:8090
CONTROL_API_URL=http://control-api:8001
BRAIN_API_URL=http://brain-api:8080
CENTRIFUGO_WS_URL=ws://centrifugo:8000/connection/websocket
```

```json
// config.json
{
  "broker": "alpaca",
  "alpaca": {
    "trading_base_url": "https://paper-api.alpaca.markets"
  },
  "risk_profile": "balanced"
}
```

### Örnek 2: Remote Stack + IBKR Live

```env
# .env
POCKETBASE_URL=https://pb.thecouncil.ai
CONTROL_API_URL=https://control.thecouncil.ai
BRAIN_API_URL=https://brain.thecouncil.ai
CENTRIFUGO_WS_URL=wss://ws.thecouncil.ai/connection/websocket
```

```json
// config.json
{
  "broker": "ibkr",
  "ibkr": {
    "host": "127.0.0.1",
    "port": 7496,  // Live port!
    "client_id": 7
  },
  "risk_profile": "conservative"
}
```

⚠️ **Live trading dikkatli kullanılmalı!**

## Yardım

Konfigürasyon sorunları için:

- [Installation Guide](./INSTALLATION.md)
- [README](../README.md)
- [GitHub Issues](https://github.com/thecouncilaiglobal-coder/thecouncilai-bot/issues)
