# 🤖 TheCouncilAI Bot

**Yapay zeka destekli otomatik trading bot'u** - Tek komutla kurulum, otomatik güncellemeler.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![Auto-Update](https://img.shields.io/badge/Auto--Update-Enabled-green.svg)](https://containrrr/watchtower)

## 🌟 Özellikler

- **🎯 Yapay Zeka Sinyalleri**: TheCouncilAI brain sisteminden gerçek zamanlı trading sinyalleri
- **🔒 End-to-End Şifreleme**: Mobil uygulama ile güvenli E2EE iletişim
- **📊 Çoklu Broker Desteği**: Alpaca ve Interactive Brokers (IBKR) entegrasyonu
- **⚡ Otomatik Güncellemeler**: Watchtower ile günlük otomatik versiyon kontrolleri
- **🛡️ Risk Yönetimi**: Conservative, Balanced, Aggressive risk profilleri
- **📱 Mobil Kontrol**: Uygulamadan bot durumunu izleme ve kontrol etme
- **🐳 Docker-Based**: Tek komutla kurulum ve yönetim

## 🚀 Hızlı Başlangıç

### Tek Komut Kurulum

**Linux / Mac:**
```bash
curl -sSL https://raw.githubusercontent.com/thecouncilaiglobal-coder/thecouncilai-bot/main/install.sh | bash
```

**Windows (PowerShell - Yönetici olarak çalıştırın):**
```powershell
irm https://raw.githubusercontent.com/thecouncilaiglobal-coder/thecouncilai-bot/main/install.ps1 | iex
```

### Kurulum Sonrası

1. **Konfigürasyonu düzenle** (opsiyonel):
   ```bash
   cd ~/thecouncilai-bot
   nano .env
   ```

2. **Bot kurulumunu çalıştır**:
   ```bash
   docker-compose run --rm bot python -m bot.main setup
   ```
   
   Bu adımda:
   - TheCouncilAI hesabınızın email ve şifresini girin
   - Broker'ınızı seçin (Alpaca veya IBKR)
   - API key'lerinizi girin
   - Mobil uygulama ile eşleştirmek için QR kodu tarayın

3. **Bot'u başlat**:
   ```bash
   docker-compose up -d
   ```

4. **Logları görüntüle**:
   ```bash
   docker-compose logs -f bot
   ```

## 📋 Gereksinimler

- Docker 20.10+
- Docker Compose 2.0+
- TheCouncilAI hesabı (mobil uygulamadan oluşturulur)
- Broker hesabı (Alpaca veya IBKR)

## 🔧 Konfigürasyon

### Backend Servisleri

Bot, TheCouncilAI backend servislerine bağlanır:

- **PocketBase**: Kullanıcı kimlik doğrulama
- **Control API**: Token yönetimi ve abonelik kontrolü
- **Brain API**: AI trading sinyalleri
- **Centrifugo**: Gerçek zamanlı WebSocket iletişimi

Varsayılan olarak bot, lokal servislere bağlanır. Remote servisler kullanıyorsanız `.env` dosyasını düzenleyin.

### Broker Konfigürasyonu

#### Alpaca
```bash
# Paper trading (test)
Trading URL: https://paper-api.alpaca.markets

# Live trading (gerçek para)
Trading URL: https://api.alpaca.markets
```

API key'lerinizi [Alpaca Dashboard](https://alpaca.markets/)'dan alın.

#### Interactive Brokers (IBKR)
- IB Gateway veya TWS'yi ayrıca çalıştırmanız gerekir
- Varsayılan port: 7497 (paper), 7496 (live)

### Risk Profilleri

- **Conservative**: Düşük risk, küçük pozisyonlar
- **Balanced**: Orta risk, dengeli yaklaşım (varsayılan)
- **Aggressive**: Yüksek risk, büyük pozisyonlar

Risk profilini mobil uygulamadan değiştirebilirsiniz.

## 🔄 Otomatik Güncellemeler

Bot, **Watchtower** kullanarak otomatik güncellenir:

- Her 24 saatte bir yeni versiyon kontrolü
- Yeni versiyon varsa otomatik Docker image güncellemesi
- Eski image'ların otomatik temizlenmesi
- Sıfır downtime ile güncelleme

### Manuel Güncelleme

Otomatik güncellemeyi beklemek istemiyorsanız:

```bash
./update.sh
```

veya

```bash
docker-compose pull
docker-compose up -d
```

## 📱 Mobil Uygulama Eşleştirme

1. Bot kurulumunu çalıştırın: `docker-compose run --rm bot python -m bot.main setup`
2. QR kod görüntülenecek
3. TheCouncilAI mobil uygulamasını açın
4. Settings → Bot → Pair Device
5. QR kodu tarayın
6. E2EE bağlantısı kuruldu! 🔒

Artık uygulamadan:
- Bot durumunu görüntüleyebilir
- Bakiye ve pozisyonları izleyebilir
- Emergency stop yapabilir
- Risk profilini değiştirebilirsiniz

## 🛠️ Komutlar

### Temel Komutlar

```bash
# Bot'u başlat
docker-compose up -d

# Bot'u durdur
docker-compose down

# Logları görüntüle
docker-compose logs -f bot

# Bot durumunu kontrol et
docker-compose ps

# Bot'u yeniden başlat
docker-compose restart bot
```

### Setup Komutu

```bash
# İlk kurulum veya reconfiguration
docker-compose run --rm bot python -m bot.main setup
```

### Güncelleme Komutu

```bash
# Manuel güncelleme
./update.sh

# veya
docker-compose pull && docker-compose up -d
```

## 📚 Dokümantasyon

Detaylı dokümantasyon için [`docs/`](./docs) klasörüne bakın:

- [Installation Guide](./docs/INSTALLATION.md) - Detaylı kurulum talimatları
- [Configuration Guide](./docs/CONFIGURATION.md) - Konfigürasyon seçenekleri
- [Auto-Update Guide](./docs/AUTO_UPDATE.md) - Otomatik güncelleme sistemi
- [Architecture](./docs/thecouncilai_system_architecture.md) - Sistem mimarisi

## 🔐 Güvenlik

- **E2EE**: Mobil uygulama ile tüm iletişim uçtan uca şifrelidir
- **API Keys**: Credential'lar Docker volume'de şifrelenmiş olarak saklanır
- **Network Isolation**: Bot izole bir Docker network'ünde çalışır
- **Read-Only Repository**: Kaynak kod sadece okunabilir, düzenlemeler kısıtlıdır

> **⚠️ UYARI**: `.env` dosyanızı asla paylaşmayın veya Git'e commit'lemeyin!

## 🐛 Sorun Giderme

### Bot başlamıyor

```bash
# Logları kontrol edin
docker-compose logs bot

# Container durumunu kontrol edin
docker-compose ps

# Bot'u yeniden başlatın
docker-compose restart bot
```

### Bağlantı hataları

- Backend servislerinin çalıştığından emin olun
- `.env` dosyasındaki URL'leri kontrol edin
- Network bağlantınızı kontrol edin

### API key hataları

```bash
# Setup'ı yeniden çalıştırın
docker-compose run --rm bot python -m bot.main setup
```

### E2EE eşleştirme sorunları

- Bot'u yeniden başlatın
- Setup komutunu tekrar çalıştırın
- QR kodu mobil uygulamadan tekrar tarayın

## 📊 Durum İzleme

Bot durumunu izlemek için:

1. **Loglar**: `docker-compose logs -f bot`
2. **Mobil Uygulama**: Real-time status updates
3. **Docker Stats**: `docker stats thecouncilai-bot`

## 🤝 Katkıda Bulunma

Bu repository **read-only**'dir. Önerileriniz için:

1. Issue açın
2. Repository owner ile iletişime geçin
3. Resmi kanallar üzerinden feedback verin

## 📄 Lisans

Bu proje [MIT License](LICENSE) ile lisanslanmıştır.

## 🆘 Destek

- **Dokümantasyon**: [docs/](./docs)
- **Issues**: [GitHub Issues](https://github.com/thecouncilaiglobal-coder/thecouncilai-bot/issues)
- **Email**: support@thecouncil.ai

## ⚠️ Sorumluluk Reddi

Bu bot yatırım tavsiyesi vermez. Tüm trading kararları kullanıcının sorumluluğundadır. Geçmiş performans gelecekteki sonuçları garanti etmez. Trading'de para kaybetme riski vardır.

---

**TheCouncilAI** - Yapay zeka destekli trading platformu 🚀
