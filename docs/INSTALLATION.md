# Installation Guide - TheCouncilAI Bot

Bu rehber, TheCouncilAI Bot'u kurmak için detaylı adımları içerir.

## Sistem Gereksinimleri

### Minimum Gereksinimler

- **İşletim Sistemi**: Linux, macOS, veya Windows 10/11
- **RAM**: En az 2GB (4GB önerilir)
- **Disk**: En az 5GB boş alan
- **İnternet**: Stabil internet bağlantısı

### Yazılım Gereksinimleri

- **Docker**: 20.10 veya üzeri
- **Docker Compose**: 2.0 veya üzeri
- **Git**: Herhangi bir versiyon

## Docker Kurulumu

### Linux

Ubuntu/Debian:
```bash
# Docker kurulumu
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Kullanıcıyı docker grubuna ekle
sudo usermod -aG docker $USER

# Oturumu yenile (logout/login)
```

### macOS

1. [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/) indirin
2. DMG dosyasını çalıştırın
3. Docker.app'i Applications klasörüne sürükleyin
4. Docker Desktop'u başlatın

### Windows

1. [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/) indirin
2. Installer'ı çalıştırın
3. WSL2 backend'i etkinleştirin (önerilir)
4. Docker Desktop'u başlatın

## Bot Kurulumu

### Hızlı Kurulum (Önerilen)

#### Linux / Mac

```bash
curl -sSL https://raw.githubusercontent.com/thecouncilaiglobal-coder/thecouncilai-bot/main/install.sh | bash
```

#### Windows (PowerShell - Yönetici)

```powershell
irm https://raw.githubusercontent.com/thecouncilaiglobal-coder/thecouncilai-bot/main/install.ps1 | iex
```

### Manuel Kurulum

1. **Repository'yi klonlayın**:
   ```bash
   git clone https://github.com/thecouncilaiglobal-coder/thecouncilai-bot.git
   cd thecouncilai-bot
   ```

2. **Environment dosyasını oluşturun**:
   ```bash
   cp .env.example .env
   ```

3. **Docker image'ı çekin**:
   ```bash
   docker-compose pull
   ```

## Konfigürasyon

### 1. Environment Değişkenlerini Ayarlayın

`.env` dosyasını düzenleyin:

```bash
nano .env  # Linux/Mac
notepad .env  # Windows
```

#### Backend Servisleri (Local Stack)

Eğer TheCouncilAI stack'ini local'de çalıştırıyorsanız, varsayılan değerleri kullanabilirsiniz:

```env
POCKETBASE_URL=http://pocketbase:8090
CONTROL_API_URL=http://control-api:8001
BRAIN_API_URL=http://brain-api:8080
CENTRIFUGO_WS_URL=ws://centrifugo:8000/connection/websocket
```

#### Backend Servisleri (Remote)

Eğer remote servislere bağlanıyorsanız, URL'leri güncelleyin:

```env
POCKETBASE_URL=https://your-pocketbase.com
CONTROL_API_URL=https://your-control-api.com
BRAIN_API_URL=https://your-brain-api.com
CENTRIFUGO_WS_URL=wss://your-centrifugo.com/connection/websocket
```

### 2. Bot Setup'ı Çalıştırın

```bash
docker-compose run --rm bot python -m bot.main setup
```

Bu komut sırasıyla:

#### a) Email ve Şifre

TheCouncilAI hesabınızın bilgilerini girin:

```
Email: your-email@example.com
Password: ********
```

> **Not**: Bu bilgiler mobil uygulamadan oluşturduğunuz hesap bilgileridir.

#### b) Broker Seçimi

Hangi broker'ı kullanmak istediğinizi seçin:

```
Select broker:
  1. Alpaca
  2. Interactive Brokers (IBKR)

Choice: 1
```

#### c) Alpaca Configuration

Alpaca seçtiyseniz:

```
Alpaca API Key: PK...
Alpaca API Secret: ...
Trading Mode:
  1. Paper Trading (Test)
  2. Live Trading (Real Money)
Choice: 1
```

**API Key Nasıl Alınır:**

1. [Alpaca'ya kaydolun](https://alpaca.markets/)
2. Dashboard → API Keys
3. "Generate New Key" tıklayın
4. Key ve Secret'i kopyalayın

#### d) IBKR Configuration

IBKR seçtiyseniz:

```
IB Gateway Host: 127.0.0.1
IB Gateway Port: 7497  (paper) veya 7496 (live)
Client ID: 7
```

**IBKR Setup:**

1. IB Gateway veya TWS'yi indirin ve yükleyin
2. API Access'i etkinleştirin (Configuration → API → Settings)
3. Socket Port'u not edin (7497 paper, 7496 live)

#### e) QR Code Pairing

Setup tamamlandığında bir QR kod gösterilir:

```
█████████████████████████████
█████████████████████████████
████ ▄▄▄▄▄ █▀█ █▄▀▄ ▄▄▄▄▄ ████
████ █   █ █▀▀▀█ █ █   █ ████
...
```

**Mobil Uygulama ile Eşleştirme:**

1. TheCouncilAI mobil uygulamasını açın
2. Settings → Bot → Pair Device
3. QR kodu tarayın
4. E2EE bağlantısı kuruldu! 🔒

## Bot'u Başlatma

### İlk Çalıştırma

```bash
docker-compose up -d
```

Bu komut:
- Bot container'ını başlatır
- Watchtower container'ını başlatır (otomatik güncellemeler için)
- Container'ları background'da çalıştırır

### Logları İzleme

```bash
docker-compose logs -f bot
```

**Başarılı başlangıç logları:**

```
✅ Abonelik aktif: PRO planı
🔒 E2EE bağlantısı aktif
========================================
  TheCouncilAI Trading Bot
========================================
```

## Doğrulama

### Bot Durumunu Kontrol Edin

```bash
docker-compose ps
```

Çıktı şöyle olmalı:

```
NAME                     STATUS         PORTS
thecouncilai-bot         Up 2 minutes   
thecouncilai-watchtower  Up 2 minutes
```

### Mobil Uygulamadan Kontrol

1. TheCouncilAI uygulamasını açın
2. Bot sekmesine gidin
3. Status: **Connected** olmalı
4. Balance ve positions görünmeli

### Test Trade (Paper Trading)

1. Bot'un paper trading modunda olduğundan emin olun
2. Mobil uygulamadan sinyalleri izleyin
3. Bot otomatik olarak sinyallere göre trade açacak
4. Positions sekmesinden açık pozisyonları görebilirsiniz

## Sorun Giderme

### Problem: Docker bulunamadı

```bash
# Docker kurulu mu kontrol edin
docker --version

# Yoksa yukarıdaki Docker kurulum adımlarını takip edin
```

### Problem: Permission denied (Linux)

```bash
# Kullanıcıyı docker grubuna ekleyin
sudo usermod -aG docker $USER

# Logout/login veya:
newgrp docker
```

### Problem: Bot başlamıyor

```bash
# Logları kontrol edin
docker-compose logs bot

# Yaygın hatalar:
# - POCKETBASE_URL unreachable → URL'i kontrol edin
# - Auth failed → Email/password'u kontrol edin
# - Broker connection failed → API key/credentials kontrol edin
```

### Problem: QR kod görünmüyor

```bash
# Terminal'in QR kodu desteklediğinden emin olun
# Alternatif: Setup'ı farklı terminal'de çalıştırın
# Veya: Pairing'i mobil uygulamadan manuel olarak yapın
```

### Problem: E2EE bağlantısı yok

```bash
# Setup'ı yeniden çalıştırın
docker-compose run --rm bot python -m bot.main setup

# QR kodu yeniden tarayın
# Bot'u yeniden başlatın
docker-compose restart bot
```

## Güvenlik Kontrol Listesi

- [ ] `.env` dosyası `.gitignore`'da
- [ ] Güçlü PocketBase şifresi kullanıldı
- [ ] API key'ler güvenli saklanıyor
- [ ] Paper trading ile test edildi
- [ ] Firewall kuralları uygun
- [ ] Docker socket permissions kontrol edildi

## Sonraki Adımlar

Kurulum tamamlandı! Şimdi:

1. [Configuration Guide](./CONFIGURATION.md) - Risk profili ve ayarları optimize edin
2. [Auto-Update Guide](./AUTO_UPDATE.md) - Otomatik güncelleme sistemini anlayın
3. Bot'u izlemeye başlayın ve logları gözden geçirin

## Yardım

Sorunlarınız için:

- [GitHub Issues](https://github.com/thecouncilaiglobal-coder/thecouncilai-bot/issues)
- [README](../README.md)
- Email: support@thecouncil.ai
