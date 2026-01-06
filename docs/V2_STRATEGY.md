# V2.0 Strategy (Free APIs) — Nedir?

V2.0'da amaç:
- Ücretsiz veriyle stabil çalışmak
- Her sembole 0..100 skor üretmek (snapshot anlamlı olsun)
- Delta sadece anlamlı değişince gelsin (trafik azalsın)

## Skor nasıl hesaplanır?
- 20 ve 60 periyot momentum
- 20 periyot volatilite ile normalize
- z benzeri değer -2..+2 aralığına kırpılır
- skor = 50 + 25*z

Bu yüzden:
- trend yoksa skorlar 50 çevresinde toplanabilir
- güçlü trendlerde 70+ veya <30 görürsün

## Negatif neden var?
Downtrend durumunda momentum/vol oranı negatife gider; skor <30’a düşebilir.

## V2.1+ (plan)
- NewsExpert eklenince skor dağılımı zenginleşir
- Shock mode ile ani değişimlerde farklı eşik/çıktı
- SQLite learning ile hisse-bazlı etkiler
