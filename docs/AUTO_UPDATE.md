# Auto-Update Guide - TheCouncilAI Bot

Bot'un otomatik güncelleme sistemi nasıl çalışır ve nasıl yönetilir.

## Watchtower Nedir?

[Watchtower](https://containrrr.dev/watchtower/), Docker container'larını otomatik olarak güncelleyen bir servistir. TheCouncilAI bot, Watchtower kullanarak:

- Belirli aralıklarla yeni Docker image versiyonlarını kontrol eder
- Yeni versiyon bulunduğunda otomatik olarak günceller
- Sıfır downtime ile bot'u yeniden başlatır
- Eski image'ları temizler

## Nasıl Çalışır?

### 1. Versiyon Kontrolü

Watchtower her 24 saatte bir (varsayılan) şunları yapar:

```
1. Docker Hub'a bağlanır
2. thecouncilaiglobal/thecouncilai-bot:latest image'ını kontrol eder
3. Local image ile remote image'ı karşılaştırır
4. SHA256 hash'leri farklıysa güncelleme gerekir
```

### 2. Güncelleme Süreci

Yeni versiyon bulunduğunda:

```
1. Yeni Docker image indirilir (pull)
2. Mevcut container durdurulur (graceful shutdown)
3. Yeni image ile container yeniden başlatılır
4. Eski image silinir (cleanup=true)
```

### 3. Downtime

- **Tipik downtime**: 30-60 saniye
- Bot durdurulur, güncellenir, tekrar başlatılır
- Açık pozisyonlar etkilenmez (broker'da saklanır)
- Trade history korunur (persistent volume)

### 4. Rollback

Güncelleme başarısız olursa:

- Watchtower otomatik rollback yapmaz
- Manuel olarak eski versiyona dönmek için: [Rollback](#rollback) bölümüne bakın

## Konfigürasyon

### Update Interval

`.env` dosyasında:

```env
# Varsayılan: Her 24 saatte bir (86400 saniye)
WATCHTOWER_POLL_INTERVAL=86400

# Her 12 saatte bir
WATCHTOWER_POLL_INTERVAL=43200

# Her 6 saatte bir
WATCHTOWER_POLL_INTERVAL=21600

# Her 1 saatte bir (aggressive)
WATCHTOWER_POLL_INTERVAL=3600
```

**Öneri**: 24 saat yeterlidir. Daha sık kontrol gereksiz network trafiği oluşturur.

### Cleanup Policy

```env
# Eski image'ları sil (varsayılan: true)
WATCHTOWER_CLEANUP=true

# Eski image'ları sakla
WATCHTOWER_CLEANUP=false
```

**Öneri**: `true` kullanın. Eski image'lar disk alanı kaplar.

### Label-Based Update

`docker-compose.yml`'de bot servisi için:

```yaml
services:
  bot:
    labels:
      - "com.centurylinklabs.watchtower.enable=true"
```

Bu label sayesinde Watchtower sadece bot container'ını günceller, diğer container'lara dokunmaz.

## Manuel Güncelleme

Otomatik güncellemeyi beklemek istemiyorsanız:

### Script ile

```bash
./update.sh
```

veya Windows:

```powershell
.\update.ps1
```

### Docker Compose ile

```bash
# 1. Yeni image'ı indir
docker-compose pull

# 2. Container'ı yeniden başlat
docker-compose up -d

# 3. Logları kontrol et
docker-compose logs -f bot
```

### Watchtower'ı Manuel Tetikle

```bash
# Watchtower'ı hemen çalıştır (interval beklemeden)
docker exec thecouncilai-watchtower /watchtower --run-once
```

## Otomatik Güncellemeyi Devre Dışı Bırakma

### Option 1: Watchtower'ı Durdur

```bash
docker-compose stop watchtower
```

Bot çalışmaya devam eder, ama otomatik güncelleme olmaz.

### Option 2: Watchtower'ı Kaldır

`docker-compose.yml`'den watchtower servisini silin veya komutlayın, ardından:

```bash
docker-compose up -d
```

### Option 3: Label'ı Disable Et

`docker-compose.yml`'de:

```yaml
services:
  bot:
    labels:
      - "com.centurylinklabs.watchtower.enable=false"
```

Sonra:

```bash
docker-compose up -d
```

## Versiyon Yönetimi

### Mevcut Versiyonu Kontrol Etme

```bash
# Docker image tag'ini görüntüle
docker images | grep thecouncilai-bot

# Çıktı:
# thecouncilaiglobal/thecouncilai-bot   latest   abc123def456   2 days ago   200MB
```

### Belirli Bir Versiyon Kullanma

`docker-compose.yml`'de:

```yaml
services:
  bot:
    image: thecouncilaiglobal/thecouncilai-bot:v1.2.3  # Specific version
    # image: thecouncilaiglobal/thecouncilai-bot:latest  # Always latest
```

**Not**: Specific version kullanırsanız, otomatik güncelleme çalışmaz (latest değil).

### Rollback

Yeni versiyonda problem varsa eski versiyona dönmek için:

#### 1. Eski Version Tag'ini Belirle

```bash
# Docker Hub'da mevcut versiyonları görüntüle
# https://hub.docker.com/r/thecouncilaiglobal/thecouncilai-bot/tags
```

veya

```bash
# Local'de mevcut image'ları görüntüle
docker images | grep thecouncilai-bot
```

#### 2. docker-compose.yml'i Güncelle

```yaml
services:
  bot:
    image: thecouncilaiglobal/thecouncilai-bot:v1.2.2  # Old version
```

#### 3. Container'ı Yeniden Başlat

```bash
docker-compose up -d
```

#### 4. Cleanup (opsiyonel)

```bash
# Kullanılmayan image'ları temizle
docker image prune -a
```

## Güncelleme Bildirimleri

### Watchtower Loglarını İzleme

```bash
docker-compose logs -f watchtower
```

**Örnek log çıktısı:**

```
watchtower  | time="2026-01-06T22:00:00Z" level=info msg="Checking for new images"
watchtower  | time="2026-01-06T22:00:05Z" level=info msg="Found new image for thecouncilai-bot"
watchtower  | time="2026-01-06T22:00:10Z" level=info msg="Stopping container thecouncilai-bot"
watchtower  | time="2026-01-06T22:00:15Z" level=info msg="Starting container thecouncilai-bot"
watchtower  | time="2026-01-06T22:00:20Z" level=info msg="Update complete"
```

### Mobil Uygulama Bildirimleri

Güncelleme sırasında:

- Bot status: **Disconnected** (kısa süre)
- Güncelleme tamamlandığında: **Connected**

## Best Practices

### 1. Güncelleme Zamanlaması

Watchtower'ın market saatleri dışında kontrol yapması için:

```env
# Gece 2:00'de kontrol (market kapalı)
# Cron expression ile (advanced):
WATCHTOWER_SCHEDULE=0 0 2 * * *
```

**Not**: Bu özellik Watchtower'ın ileri versiyonlarında mevcuttur. `POLL_INTERVAL` daha basittir.

### 2. Güncelleme Öncesi Backup

Önemli güncellemeler öncesi:

```bash
# Config backup
docker cp thecouncilai-bot:/shared/bot/config.json ./config.backup.json

# Trade history backup
docker cp thecouncilai-bot:/shared/bot/trades.db ./trades.backup.db
```

### 3. Test Environment

Yeni versiyonları production'da çalıştırmadan önce test etmek için:

```bash
# Test container başlat (farklı port/volume)
docker run --rm \
  -e POCKETBASE_URL=... \
  --name thecouncilai-bot-test \
  thecouncilaiglobal/thecouncilai-bot:latest \
  python -m bot.main
```

### 4. Update Notifications

Slack/Discord webhook ile bildirim almak için (advanced):

```yaml
services:
  watchtower:
    environment:
      - WATCHTOWER_NOTIFICATIONS=slack
      - WATCHTOWER_NOTIFICATION_SLACK_HOOK_URL=https://hooks.slack.com/...
```

## Sorun Giderme

### Problem: Watchtower çalışmıyor

```bash
# Watchtower status kontrol et
docker-compose ps watchtower

# Logları kontrol et
docker-compose logs watchtower

# Yeniden başlat
docker-compose restart watchtower
```

### Problem: Güncelleme sonrası bot başlamıyor

```bash
# Bot loglarını kontrol et
docker-compose logs bot

# Eski versiyona geri dön (rollback)
# Yukarıdaki Rollback bölümüne bakın
```

### Problem: Docker Hub rate limit

Watchtower çok sık kontrol ettiğinde Docker Hub rate limit uygulayabilir:

```
Error response from daemon: toomanyrequests: You have reached your pull rate limit.
```

**Çözüm:**

1. Update interval'ı artırın (örn: 24 saat)
2. Docker Hub'a login olun (authenticated rate limit daha yüksek):

```yaml
services:
  watchtower:
    environment:
      - REPO_USER=your_dockerhub_username
      - REPO_PASS=your_dockerhub_password
```

### Problem: Eski image'lar dolmuyor

```bash
# Manuel cleanup
docker image prune -a

# Watchtower cleanup kontrol et
# .env'de WATCHTOWER_CLEANUP=true olduğundan emin olun
```

### Problem: Güncelleme sırasında trade kaybı

Güncelleme sırasında açık order'lar:

- **Limit orders**: Broker'da kalır, güncelleme etkilemez
- **Market orders**: Gönderilmişse execute olur
- **Pending signals**: Güncelleme sonrası tekrar işlenir

Bot yeniden başladığında:
- Broker'dan açık pozisyonları sync eder
- Trade history database'den devam eder
- Hiçbir veri kaybı olmaz

## Güncelleme Geçmişi

### Versiyon Listesi

GitHub Releases sayfasından mevcut versiyonları görebilirsiniz:

https://github.com/thecouncilaiglobal-coder/thecouncilai-bot/releases

### Changelog

Her versiyonda yapılan değişiklikleri görmek için:

- GitHub Releases notlarını okuyun
- Breaking changes için upgrade guide'a bakın

## Advanced: Custom Update Script

Kendi güncelleme logic'inizi yazmak için:

```bash
#!/bin/bash
# custom-update.sh

# Pre-update backup
docker cp thecouncilai-bot:/shared/bot ./backup/

# Update
docker-compose pull
docker-compose up -d

# Post-update health check
sleep 10
if docker-compose ps bot | grep -q "Up"; then
  echo "✅ Update successful"
else
  echo "❌ Update failed, rolling back"
  docker-compose down
  docker-compose up -d
fi
```

## Yardım

Güncelleme sorunları için:

- [Installation Guide](./INSTALLATION.md)
- [Configuration Guide](./CONFIGURATION.md)
- [README](../README.md)
- [GitHub Issues](https://github.com/thecouncilaiglobal-coder/thecouncilai-bot/issues)

## Özet

- ✅ Watchtower otomatik güncellemeleri yönetir
- ✅ Varsayılan: Her 24 saatte bir kontrol
- ✅ Sıfır konfigürasyon gerekli (out-of-the-box çalışır)
- ✅ Manuel güncelleme her zaman mümkün
- ✅ Rollback basit (eski version tag kullan)
- ⚠️ Market saatleri dışında güncelleme önerilir
- ⚠️ Önemli güncellemeler öncesi backup alın
