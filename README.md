# Trade Ajanı

Strateji arastirma, backtest ve canli sinyal (Telegram bildirimi) sistemi.
Binance (spot/futures), ABD hisseleri ve BIST icin. **Gercek para ile emir
gondermez** - bu sistem sinyal uretir, karari ve gercek islemi siz verirsiniz.

## Mimari

```
core/
  providers/        Binance + Yahoo Finance veri saglayicilari (ortak sozlesme)
  datastore.py       Yerel parquet onbellek (data/raw/...)
  indicators.py       Saf pandas gostergeler (EMA, RSI, MACD, ATR, ADX, Donchian, ...)
  strategy.py          Strateji arayuzu (Signal: LONG/SHORT/FLAT)
  strategies/          Baslangic strateji kutuphanesi (4 klasik yaklasim)
  backtest.py            Bar-by-bar, komisyon/slipaj dahil backtest motoru
  metrics.py               Sharpe, Sortino, max drawdown, kazanma orani, vb.
  notify/telegram.py        Telegram bildirim gonderici

config/
  universe.yaml       Taranacak sembol/zaman dilimi evreni
  watchlist.yaml      (siz olusturacaksiniz) canli izlenecek strateji+sembol listesi

research/scan.py     Sistematik tarama: coklu sembol x zaman dilimi x parametre,
                      in-sample/out-of-sample tutarlilik siralamasi
scripts/
  fetch_data.py       Onbellegi doldurur/tazeler
  single_backtest.py  Tek kombinasyon icin detayli rapor + equity grafigi
  live_scan.py        watchlist.yaml'i kontrol eder, degisen sinyalde Telegram'a yazar
```

## Web paneli (arayüz)

Masaüstünde **"Trade Ajanı Panel"** kısayoluna çift tıklayın — tarayıcıda
otomatik açılır (`http://localhost:8501`). Panel açıkken bilgisayarınızdaki
her tarayıcıdan bu adrese girebilirsiniz.

Elle başlatmak isterseniz:
```bash
scripts\panel_ac.bat
```

Panel 5 sayfadan oluşur:
- **Ana Sayfa** — Binance'teki tüm USDT paritelerinde canlı fiyat/hacim tablosu
- **Veri Gezgini** — önbellekteki herhangi bir sembolü mum grafiğiyle inceleme
- **Strateji Taraması** — `research/scan.py` sonuçlarını filtrelenebilir tabloda görme,
  panelden tarama tetikleme
- **Backtest** — sembol/strateji/parametre seçip anında equity eğrisi + metrikler
- **İzleme & Sinyaller** — izleme listesi durumu, Telegram yapılandırma kontrolü

## Kurulum

```bash
# venv zaten C:\Users\Kaan\.venvs\trade-ajani altinda kuruldu
C:\Users\Kaan\.venvs\trade-ajani\Scripts\pip install -r requirements.txt
copy .env.example .env
```

`.env` icini doldurun (Telegram kurulumu asagida).

## Kullanim akisi

### 0) Kripto evrenini genişlet (opsiyonel, majör 5 coin dışında altcoin eklemek için)
```bash
python scripts/build_universe.py --top 150
```
Binance'teki tüm USDT paritelerini 24s hacme göre sıralar, stabilcoin/altın
tokenlerini eler, `config/universe.yaml`'i günceller. Varsayılan olarak zaten
~108 coin (majörler + likit altcoinler) tanımlı.

### 1) Veri cek
```bash
python scripts/fetch_data.py
```

### 2) Sistematik tara (strateji ara)
```bash
python research/scan.py
```
`reports/scan_sonuclari.csv` uretir; `tutarlilik_skoru` en yuksek satirlar,
hem in-sample hem out-of-sample'da (ezberlemeden) calisan kombinasyonlardir.
**Sadece IS'te iyi olan sonuclara guvenmeyin** - OOS'ta da tutarli olmali.

### 3) Begendiginiz kombinasyonu detayli incele
```bash
python scripts/single_backtest.py --symbol BTCUSDT --tf 4h --strategy donchian_breakout \
    --params "{\"entry_len\":20,\"exit_len\":10,\"adx_min\":20}"
```
`reports/` altina equity + drawdown grafigi kaydedilir.

### 4) Begendiklerinizi izleme listesine ekleyin
`config/watchlist.yaml.example` dosyasini `config/watchlist.yaml` olarak kopyalayip
scan sonuclarindan sectiklerinizi girin.

### 5) Telegram bot kurulumu (bir kez)
1. Telegram'da **@BotFather**'a yazip `/newbot` ile bot olusturun, token'i alin.
2. Botunuza herhangi bir mesaj gonderin (baslatmak icin).
3. Tarayicida acin: `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. Donen JSON'da `"chat":{"id": ...}` degerini bulun.
5. `.env` dosyasina `TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` olarak yazin.

Test:
```bash
python scripts/live_scan.py --dry-run
```

### 6) Canli tarama (gercek Telegram bildirimi)
```bash
python scripts/live_scan.py
```
Bunu duzenli calistirmak icin **Windows Gorev Zamanlayicisi** kullanin:
Action = `C:\Users\Kaan\.venvs\trade-ajani\Scripts\python.exe`,
Arguments = `scripts\live_scan.py`, Start in = proje klasoru,
Trigger = her 15-60 dakikada bir (secilen zaman dilimine gore).

### 7) TradingView ile gorsel dogrulama
TradingView'in resmi bir veri/otomasyon API'si olmadigi icin otomasyon burada
(Python) kalir. Begendiginiz stratejiyi Pine Script'e cevirip TradingView
grafiginde gozle dogrulamak ve gorsel alarm kurmak icin ayri bir adim olarak
ele alacagiz (asama 5, asagida).

## Yol haritasi (asamalar)

1. **[Tamamlandi] Altyapi** - veri, backtest motoru, gostergeler, strateji arayuzu
2. **[Tamamlandi] Ilk strateji taramasi** - 4 klasik strateji, IS/OOS tutarlilik siralamasi
3. **Strateji gelistirme** - taramadan cikan adaylari birlikte inceleyip parametre/filtre
   ekleyerek dogruluk oranini artirma (walk-forward optimizasyon, rejim filtreleri)
4. **Sanal cuzdan / demo hesap testi** - Binance Testnet (spot+futures) ile gercek zamanli
   kagit islem; local backtestin canli veriyle tutarliligini dogrulama
5. **Telegram canli sinyal** - [Tamamlandi, altyapi hazir] watchlist genisletme + zamanlama
6. **TradingView entegrasyonu** - onaylanan stratejiyi Pine Script'e cevirip gorsel dogrulama

## Onemli notlar

- Backtest **komisyon + slipaj** varsayar (varsayilan: %0.1 komisyon + %0.05 slipaj,
  taraf basina) - bunlari config/universe.yaml'da ayarlayabilirsiniz.
- Sinyal, mumun **kapanisinda** karar verilip **bir sonraki mumun acilisinda**
  uygulanir (ileriye-bakma kacagini onlemek icin).
- **Fiyat doğruluğu:** Binance verisi doğrudan borsanın kendi genel API'sinden
  gelir - gerçek zamanlı (ağ gecikmesi dışında gecikme yok). Yahoo Finance
  (ABD hisseleri, BIST) garantili anlık değildir; birkaç saniye-dakika
  gecikmeli olabilir, özellikle BIST'te. Gerçek zamanlı BIST/hisse verisi
  gerekiyorsa ücretli bir veri sağlayıcısı entegre etmemiz gerekir.
- Yahoo Finance intraday veri sinirlidir (1m: son 7 gun, <1d: son 60 gun).
  Yogun intraday arastirma icin Binance verisi kullanin.
- Bu sistem yatirim tavsiyesi vermez, sinyal uretir. Gercek/demo emir gonderme
  adimi (asama 4) baslamadan once birlikte risk kurallarini (pozisyon buyuklugu,
  maksimum kaldirac, gunluk zarar limiti) netlestirecegiz.
