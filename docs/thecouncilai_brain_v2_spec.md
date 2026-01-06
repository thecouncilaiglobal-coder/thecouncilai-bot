# TheCouncilAI — Brain v2 Teknik Tasarım ve Öğrenme Spesifikasyonu (Premium/Profesyonel)

> Bu doküman “Brain v2” için **modüler mimari**, **öğrenme tasarımı**, **cold-start** ve **rate-limit** stratejilerini tanımlar.  
> Dışarıya (App/Bot) **tek skor (0–100)** çıkar; içeride çok daha zengin sinyal/öğrenme katmanları korunur ve büyütülür.

---

## 0) Hedefler ve Kısıtlar

### Hedefler
- **Az risk, az işlem, yüksek kalite** (low-turnover, high-quality opportunities).
- Çok sayıda sembol (örn 1000+) içinde fırsat bulma: **cross-sectional seçicilik**.
- Ürün dili: yatırım tavsiyesi çağrışımı yok → dışa “BUY/SELL” değil, **pozitif/nötr/negatif skor**.
- **Tek kişi operasyon**: az servis, kolay deploy, kolay debug.
- **Premium değer**: asıl entelektüel katman (öğrenme + argümanlar + ağırlıklar) server tarafında kalır.

### Kısıtlar (bugün)
- Veri çoğunlukla **ücretsiz API**: limitli rate, bazen eksik tarihçe.
- “Eski veri yok”: ilk günlerde model eğitimi zayıf olacak → **cold start** şart.
- Bot/App’a fiyat/işlem emri göstermiyoruz: sadece **analiz skoru** ve renk.

---

## 1) Dış Protokol (Output) — Tek Skor

### 1.1 Skor tanımı
- `score ∈ [0, 100]` (integer)
- Semantik: **pozitiflik skoru**
  - 50: nötr merkez
  - 100’e yaklaştıkça pozitif
  - 0’a yaklaştıkça negatif

### 1.2 Renk/segment kuralı (UI/Bot)
- `score >= 70` → **Pozitif** (yeşil)
- `30 <= score < 70` → **Nötr** (gri)
- `score < 30` → **Negatif** (kırmızı)

> Not: Nötr olması “skor yok” demek değildir. Skor **her zaman** gösterilir.

### 1.3 Snapshot / Delta payload
- Snapshot (HTTP): `{ e, t, m: [[SYM, score], ...] }`
- Delta (WS): `{ e, t, d: [[SYM, score], ...] }` (sadece değişenler)

> `t` alanı **Unix epoch millisecond (ms)** olarak standarttır.

> Not: Hukuki ve ürün dili gereği dışarıya **tek kanal + tek skor** çıkar.
> Bot ve App aynı `signals:delta` akışını dinler; “BUY/SELL/FLAT” gibi ekstra output yoktur.

---

## 2) Brain v2: Katmanlı Mimari (Eski Beyni Kaybetmeden)

Brain v2, “tek beyin” yerine **çoklu uzman (experts)** yaklaşımıyla tasarlanır.

### 2.1 Katmanlar
1) **Ingestion Layer** (veri çekme + cache + rate limit)
2) **Feature Layer** (stabil özellik çıkarımı)
3) **Experts Layer** (farklı uzman skorları üretir)
4) **Gating / Fusion Layer** (uzman skorlarını ağırlıklandırır)
5) **Calibration Layer** (skoru zamanla kalibre eder, güven artırır)
6) **Decision/Turnover Control Layer** (histerezis, cooldown, onay penceresi)
7) **Publishing Layer** (snapshot + delta)

### 2.2 Eski beyin entegrasyonu (koruma)
Eski “brain”in güçlü kısımları **BaselineExpert** olarak taşınır:
- mevcut indikatör hesapları
- mevcut strateji mantığı
- mevcut öğrenme kayıtları (pozisyon kapanınca veri)

Brain v2’de bu uzman, diğer uzmanlarla birlikte skor üretir; böylece “eskisi ile uğraştık, çöpe gitmesin” garantilenir.

---

## 3) Ingestion Layer (Ücretsiz Veri + Rate Limit + Cache)

### 3.1 Veri kaynakları (adapter pattern)
- `MarketDataProvider`: candle/ohlcv (örn 1m/5m/1h/1d)
- `NewsProvider`: haber başlık/özet/kaynak/timestamp, sembol eşleşmesi
- (Opsiyonel) `DepthProvider`: orderbook/derinlik (varsa)

Her sağlayıcı için:
- `fetch_latest(symbols, since_ts)`
- `fetch_snapshot(symbols, window)`

### 3.2 Rate-limit stratejisi (kritik)
- **Central RateLimiter**: token bucket + backoff
- **Symbol batching**: istekleri sembol gruplarına böl
- **Adaptive polling**:
  - Piyasa kapalı: daha seyrek (örn 5 dk / 15 dk)
  - Piyasa açık: 5–10 sn “score cycle” ama veri çekimi her cycle olmak zorunda değil (cache ile)
- **Cache-first**:
  - Candle: sadece yeni bar geldiğinde güncelle
  - Haber: dedup + incremental pull

### 3.3 Cold-start için veri seçimi
- İlk etap: mümkünse **son N gün** (örn 30 gün) günlük/1h veri ile temel trend/vol hesapla
- Haber tarafı: son 7–14 gün haberleri dedup ederek topla
- “Tarihçe yoksa”: yalnız “anlık/son veriler” ile heuristik başla; öğrenme yavaşça devreye girer.

---

## 4) Feature Layer (Oynaklığı Azaltan Tasarım)

Trend/hacim/derinlik oynak → bunları **stabilize** edip doğru yere koyacağız.

### 4.1 Trend Features (filtre/onay)
Amaç: whipsaw azaltmak, işlem sayısını düşürmek.
- EMA(20/50), SMA(20/50) farkları
- ADX: trend var mı?
- ATR / realized vol: rejim ölçümü
- EWMA smoothing (kısa timeframe gürültüsünü azaltır)

Çıktılar:
- `trend_dir ∈ [-1, +1]`
- `trend_strength ∈ [0, 1]`
- `trend_present ∈ {0,1}`

### 4.2 Volume/Liquidity Features (timing/kalite, yön değil)
Amaç: “girilebilirlik” ve aşırı spike gürültüsünü kontrol.
- Relative Volume (RVOL) + winsorization (uç değer kırp)
- Spread proxy (varsa)
- “liquidity_ok” flag

Çıktılar:
- `liquidity_ok ∈ {0,1}`
- `timing_score ∈ [0,1]`

### 4.3 News Features (baskın, daha stabil)
Haber “event-driven” → daha seyrek ama anlamlı.
- Sembol eşleştirme (ticker match + alias)
- Dedup/cluster (aynı olay farklı kaynaklardan gelirse tek olay)
- Source ağırlığı (whitelist/weight map)
- Recency decay (half-life: 6–24h)
- Novelty (aynı tema tekrarında etki düşer)

News metni için iki seviye:
- **Basit token**: kelime/bi-gram hashing (hafif, hızlı)
- **Opsiyonel embedding**: daha sonra ücretli veri + daha güçlü model için

Çıktılar:
- `news_signal ∈ [-1, +1]` (iç temsil)
- `news_conf ∈ [0,1]`
- `news_intensity ∈ [0,1]` (haber yoğunluğu)

---

## 5) Experts Layer (Çoklu Uzman Skorları)

### 5.1 BaselineExpert (Eski beyin)
- Eski strateji/indikatörler aynen
- Çıkış: `p_base ∈ [-1, +1]`, `c_base ∈ [0,1]`

### 5.2 TrendExpert
- Trend yönü ve gücü
- Çıkış: `p_trend`, `c_trend`

### 5.3 NewsExpert — **İki seviyeli öğrenme** (Hisse bazlı + Genel etki)
Senin fikrini aynen mimariye gömüyoruz:

#### A) Stock-Specific News Learning (Hisse bazlı)
Amaç: “Bu hissede şu kelimeler/temalar geçince tipik etki”.
- Model: online logistic/linear regression (L2) **per-symbol**
- Feature: token hashing (çok hafif)
- Öğrenme label’ı: haber sonrası belirli ufuklarda (H1/H4/D1) normalize edilmiş return
- Shrinkage: az veri varsa global modele yaklaş (empirical Bayes)

Çıkış:
- `p_news_stock(sym)`, `c_news_stock(sym)`

#### B) Global / Cross-Asset News Learning (Genel etki)
Amaç: “Tüm hisseleri etkileyen haberler genelde nasıl etki eder?”
- Model: tek global online model
- Ayrıca sector/industry koşullu alt modeller (opsiyonel)
- Çıkış:
  - `p_news_global`, `c_news_global`

**Birleştirme (news tarafı):**
- `p_news = w_s(sym)*p_news_stock + (1-w_s(sym))*p_news_global`
- `w_s(sym)` hisse veri miktarına göre artar (cold start’ta küçük).

### 5.4 RegimeExpert (Volatilite + Haber Yoğunluğu)
Amaç: eşik/histerezis/cooldown gibi kontrol parametrelerini rejime göre ayarlamak.
- `regime_risk ∈ [0,1]` (yüksek vol/şok = yüksek risk)
- `risk_multiplier` üretir (eşikleri yukarı çeker)

---

## 6) Gating / Fusion Layer (Skorları Toplama)

Amaç: her uzmanın katkısını “güven” ile ağırlıklandırmak.

### 6.1 İç temsil: pozitiflik p
Tüm uzmanlar `p_i ∈ [-1,+1]` ve `c_i ∈ [0,1]` üretir.

Örnek birleşim:
- `p_raw = Σ (w_i * c_i * p_i) / (Σ w_i * c_i + ε)`
- `conf_raw = clamp(Σ w_i * c_i, 0, 1)` (opsiyonel)

**Önerilen ağırlıklar (başlangıç):**
- News: 0.6–0.75 (baskın)
- Trend: 0.15–0.25 (onay)
- Baseline: 0.10–0.20 (eski beynin gücü korunur)
- Regime: doğrudan p’ye değil, kontrol parametrelerine etki

### 6.2 0–100 skora dönüşüm
- `score_unclamped = round(50 + 50 * p_raw)`
- `score = clamp(score_unclamped, 0, 100)`

---

## 7) Calibration Layer (Profesyonel Kaliteyi Arttıran Kısım)

### 7.1 Bucket-based Bayesian Calibration (düşük operasyon, güçlü etki)
- Skor aralıkları: 0–10, 10–20, … 90–100
- Her bucket için Beta dağılımı: `(α, β)`
- Her kapatılan pozisyonda:
  - win → α += 1
  - loss → β += 1
- `p_win(bucket) = α / (α+β)`

**Kullanım:**
- `score` üretildikten sonra bucket’a göre “kalibrasyon düzeltmesi” uygulanır (hafif).
- Ayrıca “confidence” ve eşik dinamikleri için kullanılır.

### 7.2 Rejim bazlı kalibrasyon (opsiyonel)
- düşük vol / yüksek vol
- haber var / haber yok
Bucket tabloları rejime göre ayrı tutulabilir.

### 7.3 Shrinkage (hisse bazlı vs global)
- Hisse bazlı bucket tabloları az veriyle aşırı oynamasın:
  - `p_calibrated(sym) = λ(sym)*p_sym + (1-λ(sym))*p_global`
  - λ(sym) = trade_count / (trade_count + k)

---

## 8) Turnover Control Layer (Az İşlem Garantisi)

### 8.1 Histerezis (eşik tamponu)
- Pozitife girmek: `score >= 70`
- Pozitiften çıkmak: `score < 60`
- Negatife girmek: `score <= 30`
- Negatiften çıkmak: `score > 40`

### 8.2 Onay penceresi (N ölçüm üst üste)
- Örn: 3 ardışık cycle `>= 70` olmadan “pozitif state”e geçme

### 8.3 Cooldown / minimum holding
- Aynı sembolde tekrar işlem için min süre
- Kapandıktan sonra yeniden giriş için bekleme

---

## 9) Learning Veri Modeli (Öğrenme Kayıtları)

### 9.1 Event kayıtları (haber tabanlı öğrenme için)
Her haber olayı için:
- `event_id`, `symbol(s)`, `timestamp`
- `tokens` (hashing vector)
- `source_weight`, `novelty`, `cluster_id`
- “after” label’lar:
  - H1 return, H4 return, D1 return (normalize edilmiş)

### 9.2 Trade kayıtları (mevcut mekanizma korunur)
Her trade/pozisyon için:
- entry timestamp
- entry feature snapshot (trend, news, baseline p/c, rejim)
- exit timestamp
- realized outcome (win/loss/return)
- used score & thresholds (audit)

### 9.3 Depolama (tek kişi için pratik)
- Local SQLite veya dosya tabanlı (ör. sqlite + periodic backup)
- PocketBase’e ağır öğrenme datası yazmak zorunda değilsin (opsiyonel).

---

## 10) Cold Start Planı (Veri yoksa bile çalışsın)

### 10.1 Başlangıç “heuristic mode”
- News yoksa: skor 50 civarı + trend filtre (çok sınırlı hareket)
- News varsa: source ağırlıklı, decay’li basit sentiment + trend onayı

### 10.2 “Öğrenme devreye giriş” eşiği
- Hisse bazlı model aktifleşmesi için min event/trade sayısı (örn 20–50)
- Aksi halde global modele shrink

### 10.3 API limit koruması
- Tek bir cycle’da tüm sembollere news/candle çekme yerine:
  - watchlist batching
  - market open saatleri yoğun, kapalıyken seyrek
  - değişmeyen sembollerde update’i düşür

---

## 11) Publishing Layer (Snapshot + Delta)

### 11.1 Snapshot üretimi
- Cycle sonunda tam listeyi JSON üret (gzip ile çok küçülür)
- `/snapshot` endpoint’i servis eder

### 11.2 Delta üretimi
- Son score state ile yeni score state diff
- Değişen semboller `signals:delta` ile hub’a basılır

### 11.3 Epoch (e)
- Her cycle `e += 1`
- App/Bot `e` atladıysa snapshot’a döner

---

## 12) Konfigürasyon (Önerilen Parametreler)

- `SCORE_POSITIVE=70`, `SCORE_NEGATIVE=30`
- `HYST_POS_EXIT=60`, `HYST_NEG_EXIT=40`
- `CONF_HALF_LIFE_HOURS=12`
- `NEWS_HALF_LIFE_HOURS=12`
- `MIN_EVENTS_STOCK_MODEL=30`
- `MIN_TRADES_STOCK_CALIB=30`
- `CYCLE_SECONDS_OPEN=10`, `CYCLE_SECONDS_CLOSED=300`
- `TOPK_POSITIVE=30`, `BOTTOMK_NEGATIVE=30` (opsiyonel seçim)

---

## 13) Modül/Package Yapısı (Öneri)

```
brain/
  ingestion/
    market_provider.py
    news_provider.py
    rate_limiter.py
    cache_store.py
  features/
    trend_features.py
    volume_features.py
    news_features.py
  experts/
    baseline_expert.py        # eski beyin mantığı
    trend_expert.py
    news_expert_global.py
    news_expert_stock.py
    regime_expert.py
  learning/
    event_store.py
    online_models.py          # SGD/logreg, hashing vectorizer
    calibrator_bucket_beta.py
    shrinkage.py
  fusion/
    gating.py
    score_mapping.py
    turnover_control.py
  api/
    brain_api.py              # /snapshot /health
  publish/
    centrifugo_publisher.py   # delta publish
  main.py
```

---

## 14) Yol Haritası (Veri Kalitesi Artınca)

- Adapter layer değişir (MarketDataProvider/NewsProvider)
- Feature/Expert/Learning katmanları korunur
- Daha iyi haber sınıflandırma (embedding + küçük model), daha iyi depth verisi (execution)

---

**Sonraki adım:** Bu spes’e göre mevcut beyin kodunu “BaselineExpert”e sarıp,
NewsExpertStock/Global + Calibrator + TurnoverControl katmanlarını ekleyerek Brain v2’yi kademeli devreye alacağız.
