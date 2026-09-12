# Trade Ajanı'ndan aktarılan bulgular

Bu dosya, ayrı bir proje olan **Trade-ajanı**'nda (`C:\Users\Kaan\OneDrive\Masaüstü\Trade-ajanı`)
gerçek eğitim/test (IS/OOS) ayrımlı taramalarla doğrulanmış stratejilerin
özetidir. Kod, `trade_ajani_stratejileri.py`'ye bu projenin (kaan-trade)
kalıbına (LONG-only, `kapanis`/`yuksek`/`dusuk`/`acilis`/`hacim` sütunları)
uyarlanarak aktarıldı; `trade_ajani_tarama.py` ile bu projenin kendi
ölçüm motoruyla (rastgele-kontrol-grubu, %95 anlamlılık eşiği) test
edilebilir.

## 1) Kirilim-GeriCekilme-Toparlanma ("altcoin_stratejisi")

**Mantık:** Çok-dokunuşlu destek/direnç (en az 2 temas) + kararlı kırılım
(kapanış bazlı) + kırılan seviyeye geri çekilme + güçlü kapanışlı
toparlanma mumu ile giriş.

**Trade-ajanı'nda doğrulandığı yer:** SEIUSDT 1sa (kazanma %56, kâr
faktörü 1.71), ayrıca SHIBUSDT, FETUSDT, BICOUSDT, WLDUSDT, ZKCUSDT,
BMTUSDT, PENGUUSDT, ZENUSDT — **orta/küçük ölçekli altcoinler**, 1 saatlik.

**BTC/ETH/SOL/BNB gibi majorlerde ÇALIŞMIYOR** — Trade-ajanı'nda 54
parametre denendi, hiçbiri kâr faktörünü 1'in üzerine çıkaramadı.
kaan-trade'de bu majorlerle hızlı test edildiğinde de (bkz. aşağı)
beklendiği gibi zayıf çıktı — bu bir hata değil, tutarlı bir bulgu.

## 2) Tepe/Dip Stratejisi (rejime uyarlanan dönüş/düzeltme)

**Mantık:** ADX trendli ise (fiyat EMA200'ün doğru tarafında) kısa bir
düzeltmede (RSI sığ dalış, MACD histogram dönüşü, hacim teyidi) trend
YÖNÜNDE giriş; ADX yatay ise çok-dokunuşlu bir destek/direnç bölgesinden
derin bir RSI aşırılığıyla gelen dönüşü yakalar.

**Trade-ajanı'nda doğrulandığı yer:** 108 sembol × 3 zaman dilimi
taramasında 20 farklı 1sa sembolde bağımsız doğrulandı (ETHUSDT, DOTUSDT,
LINKUSDT, UNIUSDT, DOGEUSDT dahil). 8x kaldıraçlı tam-tarih testinde en
sağlam 6'sı: TUSDT, DOTUSDT, UNIUSDT, FETUSDT, LINKUSDT, PEPEUSDT
(kaldıraçlı getiri +%19..+%39, maxDD <%10).

## 3) Hacim-Fiyat Uyumsuzluğu (Wyckoff "efor vs sonuç")

**Mantık:** Bir mumda hacim (efor) anormal yüksekken fiyat aralığı
(sonuç) ATR'a göre küçükse, bu bir uyumsuzluk — büyük bir taraf agresif
girmiş ama fiyatı hareket ettirememiş, karşı tarafın "emdiği" anlamına
gelir. Çok-dokunuşlu bir bölgede + hacim teyitli absorbsiyon mumunun ucu
kırılınca giriş.

**Trade-ajanı'nda doğrulandığı yer:** 108 sembol IS/OOS taramasında 24
benzersiz 1sa sembolde doğrulandı. 8x kaldıraçlı en sağlam 6'sı: SANDUSDT,
BONKUSDT, ETHUSDT, BNBUSDT, ONGUSDT, DOTUSDT (kaldıraçlı getiri
+%14..+%29).

## 4) Major Trend Sürücüsü ("major_stratejisi")

**Mantık:** N-bar Donchian kırılımı + ADX (trend teyidi) + hacim oranı
(katılım teyidi) + uzun EMA ana trend filtresi ile giriş; çıkış sabit bir
hedef DEĞİL, "chandelier" (candan) iz süren stop — trend sürdükçe
pozisyon taşınır.

**Trade-ajanı'nda doğrulandığı yer:** BNBUSDT 4sa (tam tarih +%801,
Sharpe 1.12), ETHUSDT 4sa (+%142), SOLUSDT 4sa (+%411, ama maxDD -%80.75
— dikkatli olunmalı). **BTC ve ZEC'te bu mekanik henüz sağlam sonuç
VERMEDİ.**

**ÖNEMLİ:** bu strateji Trade-ajanı'nda **4 SAATLİK** zaman diliminde
doğrulandı — `trade_ajani_tarama.py`'nin varsayılanı (1sa) ile test
ederseniz zayıf çıkar, bu beklenen bir sonuç (yanlış zaman dilimi), o
kadar değil.

## kaan-trade'de yapılan hızlı tutarlılık kontrolü (2026-09-10)

`trade_ajani_tarama.py` ile BTC/ETH/BNB/SOL/DOGE/LINK, 1sa, ~400 gün,
100 rastgele deneme:

| Strateji | TEST getiri | Yüzdelik | Düşüş | İşlem | Not |
|---|---|---|---|---|---|
| Tepe/Dip | +%1.7 | **%98** | -%4.9 | 8 | Rastgele eşiğini (%95) geçti |
| Hacim-Fiyat Uyumsuzluğu | +%3.3 | **%98** | -%4.3 | 8 | Rastgele eşiğini geçti |
| Kirilim-GeriCekilme-Toparlanma | -%6.2 | %86 | -%8.3 | 22 | Geçemedi (beklenen — bu majorler için tasarlanmadı) |
| Major Trend Sürücüsü | -%12.2 | %71 | -%16.8 | 26 | Geçemedi (yanlış zaman dilimi — 4sa olmalıydı) |

**Dürüstlük notu:** Bu SADECE 6 major coin + 8-26 işlemlik küçük bir
örneklem — Trade-ajanı'nın kendi doğrulamasının yerini TUTMAZ. Tepe/Dip
ve Hacim-Fiyat Uyumsuzluğu'nun majorlerde de (asıl doğrulandıkları
altcoin evreni dışında) rastgele eşiğini geçmesi CESARET VERİCİ ama
küçük örneklemli — gerçek bir doğrulama için `trade_ajani_tarama.py`'nin
`coinler` listesini yukarıdaki bulgulardaki (SEI/SHIB/FET/BICO/WLD/ZKC/
BMT/PENGU/ZEN gibi) sembollerle değiştirip yeniden çalıştırın.
