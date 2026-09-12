r"""
VERI KAYNAKLARI
===============

Uygulamanin "veri toplayan" katmani. Ekranla hic ilgilenmez, sadece
internetten sayi getirir. Boylece ayni fonksiyonlari hem uygulamada
hem botta kullanabiliyoruz.

KULLANILAN KAYNAKLAR (hepsi ucretsiz, hicbiri API anahtari istemez):

  1. Binance (ccxt ile)    -> fiyat, hacim, mum verisi, emir defteri
  2. Binance vadeli (ccxt) -> fonlama orani, acik pozisyon
  3. CoinGecko             -> piyasa degeri, siralama, arz, zirveden uzaklik
  4. alternative.me        -> Korku & Acgozluluk endeksi
  5. CoinGecko /global     -> BTC hakimiyeti, toplam piyasa degeri

TASARIM KURALI: Buradaki her fonksiyon hata durumunda COKMEZ, None
dondurur. Sebebi: bir kaynak cokerse uygulamanin tamami degil sadece
o kutu bos kalir.
"""

import ccxt
import pandas as pd
import requests

ZAMAN_ASIMI = 20

_oturum = requests.Session()
_oturum.headers.update({"User-Agent": "kaan-trade/1.0"})

# Borsa baglantilarini bir kez kurup tekrar kullaniyoruz (her seferinde
# yeniden kurmak yavas olur)
_spot = None
_vadeli = None


def spot_borsa():
    global _spot
    if _spot is None:
        _spot = ccxt.binance({"enableRateLimit": True, "timeout": ZAMAN_ASIMI * 1000})
    return _spot


def vadeli_borsa():
    global _vadeli
    if _vadeli is None:
        _vadeli = ccxt.binanceusdm({"enableRateLimit": True, "timeout": ZAMAN_ASIMI * 1000})
    return _vadeli


# ============================================================
#  1) BORSA: fiyat ve hacim
# ============================================================

def anlik_fiyat(sembol="BTC/USDT"):
    """
    Su anki fiyat ve son 24 saatin ozeti.

    Donen degerler:
      fiyat        : su anki son islem fiyati
      degisim_24s  : son 24 saatte yuzde kac degisti
      yuksek_24s   : son 24 saatin en yuksegi
      dusuk_24s    : son 24 saatin en dusugu
      hacim_24s    : son 24 saatte kac dolarlik islem oldu
    """
    try:
        t = spot_borsa().fetch_ticker(sembol)
        return {
            "fiyat": t["last"],
            "degisim_24s": t.get("percentage"),
            "yuksek_24s": t.get("high"),
            "dusuk_24s": t.get("low"),
            "hacim_24s": t.get("quoteVolume"),
        }
    except Exception:
        return None


def mum_verisi(sembol="BTC/USDT", zaman_dilimi="1d", adet=400):
    """
    Grafik ve gostergeler icin gecmis mum verisi.

    ONEMLI: Borsanin dondurdugu SON mum, o donem henuz suruyorsa (gun/
    saat/dakika bitmediyse) HENUZ KAPANMAMIS olabilir -- yani "gunluk
    hacim" gibi bir deger daha o gun bitmedigi icin gercekte daha
    yuksek cikacaktir. Bunu KAPSAM DISI tutmazsak hacim ortalamasi,
    sikisma tespiti, destek/direnc gibi butun analizler yaniltici
    olur (ozellikle gunun daha basindaki saatlerde -- o gunun hacmi
    henuz kucuk gorunur, sanki "hacim patlamasi yok" der ama gun
    daha bitmemistir). O yuzden son mum kapanmadiysa ATILIR.

    (Canli grafikteki "su an olusan mum" ayri bir mekanizmayla --
    WebSocket'ten gelen anlik fiyatla -- ayrica ekleniyor, bkz.
    grafikler.py _canli_mum_ekle. Yani kapanmamis mumu burada atmak
    "canli" hissi kaybettirmez, sadece onu doğru yerden -- WebSocket'ten
    -- almamizi saglar.)
    """
    try:
        borsa = spot_borsa()
        # +1 istiyoruz: son mum kapanmamis diye atarsak bile, geriye
        # yine istenen <adet> kadar KAPANMIS mum kalsin.
        ham = borsa.fetch_ohlcv(sembol, timeframe=zaman_dilimi, limit=adet + 1)
        if not ham:
            return None

        sure_ms = borsa.parse_timeframe(zaman_dilimi) * 1000
        if ham[-1][0] + sure_ms > borsa.milliseconds():
            ham = ham[:-1]

        df = pd.DataFrame(ham, columns=["zaman", "acilis", "yuksek", "dusuk",
                                        "kapanis", "hacim"])
        df["zaman"] = pd.to_datetime(df["zaman"], unit="ms", utc=True)
        return df.tail(adet).reset_index(drop=True)
    except Exception:
        return None


def emir_defteri_ozeti(sembol="BTC/USDT", derinlik=50):
    """
    Emir defteri: o anda alicilarin ve saticilarin bekleyen emirleri.

    makas       : en iyi alis ve en iyi satis arasindaki fark (yuzde).
                  Kucuk olmasi "piyasa likit, alip satmak kolay" demektir.
    alis_baskisi: bekleyen alis emirleri toplaminin, tum emirlere orani.
                  %50 uzeri alicilarin daha kalabalik oldugunu gosterir.

    UYARI: Emir defteri anlik bir fotograftir ve cok hizli degisir.
    Buradan gelecek tahmini yapilmaz.
    """
    try:
        d = spot_borsa().fetch_order_book(sembol, limit=derinlik)
        if not d["bids"] or not d["asks"]:
            return None
        en_iyi_alis = d["bids"][0][0]
        en_iyi_satis = d["asks"][0][0]
        alis_hacim = sum(m for _, m in d["bids"])
        satis_hacim = sum(m for _, m in d["asks"])
        toplam = alis_hacim + satis_hacim
        return {
            "makas_yuzde": (en_iyi_satis - en_iyi_alis) / en_iyi_alis * 100,
            "makas_mutlak": en_iyi_satis - en_iyi_alis,
            "alis_baskisi": alis_hacim / toplam * 100 if toplam else None,
            "alis_hacim": alis_hacim,
            "satis_hacim": satis_hacim,
        }
    except Exception:
        return None


# ============================================================
#  2) VADELI ISLEMLER: fonlama orani ve acik pozisyon
# ============================================================

def fonlama_orani(sembol="BTC/USDT:USDT"):
    """
    Fonlama orani: vadeli piyasada uzun ve kisa pozisyon tutanlar
    arasinda 8 saatte bir el degistiren odeme.

      POZITIF -> yukselis bekleyenler kalabalik, onlar odeme yapiyor
      NEGATIF -> dusus bekleyenler kalabalik, onlar odeme yapiyor

    Kalabalik yonu gosterir, dogru yonu gostermez. Cok yuksek pozitif
    degerler genelde "piyasa fazla iyimser" diye okunur ama bu bir
    tahmin araci degil, bir kalabalik olcusudur.
    """
    try:
        r = vadeli_borsa().fetch_funding_rate(sembol)
        oran = r.get("fundingRate")
        if oran is None:
            oran = float(r["info"]["lastFundingRate"])
        return {
            "oran_yuzde": oran * 100,
            "yillik_yuzde": oran * 3 * 365 * 100,   # gunde 3 kez odenir
            "sonraki_odeme": r.get("fundingDatetime") or r.get("nextFundingDatetime"),
        }
    except Exception:
        return None


def acik_pozisyon(sembol="BTC/USDT:USDT", fiyat=None):
    """
    Acik pozisyon (open interest): vadeli piyasada su an acik olan
    toplam sozlesme miktari. Piyasaya ne kadar para girdiginin olcusu.

    Artiyorsa yeni para giriyor, azaliyorsa pozisyonlar kapaniyor.
    """
    try:
        r = vadeli_borsa().fetch_open_interest(sembol)
        miktar = r.get("openInterestAmount") or r.get("baseVolume")
        deger = r.get("openInterestValue")
        if deger is None and miktar is not None and fiyat:
            deger = miktar * fiyat
        return {"miktar": miktar, "deger_usd": deger}
    except Exception:
        return None


def acik_pozisyon_gecmisi(sembol="BTC/USDT:USDT", gun=10):
    """
    Son <gun> gunun acik pozisyon (open interest) gecmisi -- tek bir
    anlik deger degil, TREND gormek icin. En eskiden en yeniye sirali
    bir sayi listesi dondurur (miktar cinsinden).

    Coin'in vadeli piyasasi yoksa (cogu altcoin'de bu boyle) None doner.
    """
    try:
        r = vadeli_borsa().fetch_open_interest_history(sembol, timeframe="1d", limit=gun)
        degerler = [x["openInterestAmount"] for x in r if x.get("openInterestAmount") is not None]
        return degerler if degerler else None
    except Exception:
        return None


# ============================================================
#  3) COINGECKO: piyasa degeri ve zirveden uzaklik
# ============================================================

def coingecko_piyasa(kimlikler=("bitcoin", "ethereum")):
    """
    CoinGecko'dan piyasa ozeti. Borsada olmayan bilgileri verir:
    piyasa degeri, siralama, dolasimdaki arz, tum zamanlarin zirvesi.

    Ucretsiz kullanim siniri: ayda 10.000 cagri, dakikada 30.
    Bu uygulama 60 saniyede bir cagirdigi icin sinirin cok altinda kalir.
    """
    try:
        y = _oturum.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={"vs_currency": "usd", "ids": ",".join(kimlikler),
                    "price_change_percentage": "1h,24h,7d,30d"},
            timeout=ZAMAN_ASIMI).json()
        sonuc = {}
        for c in y:
            sonuc[c["symbol"].upper()] = {
                "isim": c["name"],
                "fiyat": c["current_price"],
                "piyasa_degeri": c["market_cap"],
                "siralama": c["market_cap_rank"],
                "hacim_24s": c["total_volume"],
                "arz": c.get("circulating_supply"),
                "zirve": c.get("ath"),
                "zirveden_uzaklik": c.get("ath_change_percentage"),
                "degisim_1s": c.get("price_change_percentage_1h_in_currency"),
                "degisim_24s": c.get("price_change_percentage_24h_in_currency"),
                "degisim_7g": c.get("price_change_percentage_7d_in_currency"),
                "degisim_30g": c.get("price_change_percentage_30d_in_currency"),
            }
        return sonuc or None
    except Exception:
        return None


def piyasa_geneli():
    """Toplam kripto piyasa degeri ve BTC/ETH hakimiyeti."""
    try:
        d = _oturum.get("https://api.coingecko.com/api/v3/global",
                        timeout=ZAMAN_ASIMI).json()["data"]
        return {
            "toplam_deger": d["total_market_cap"]["usd"],
            "toplam_hacim": d["total_volume"]["usd"],
            "btc_hakimiyet": d["market_cap_percentage"].get("btc"),
            "eth_hakimiyet": d["market_cap_percentage"].get("eth"),
            "coin_sayisi": d.get("active_cryptocurrencies"),
        }
    except Exception:
        return None


# ============================================================
#  4) KORKU & ACGOZLULUK ENDEKSI
# ============================================================

def korku_acgozluluk(gun=30):
    """
    0-100 arasi bir sayi. Piyasadaki genel duyguyu olcmeye calisir.
      0-25   Asiri korku
      25-45  Korku
      45-55  Notr
      55-75  Acgozluluk
      75-100 Asiri acgozluluk

    Oynaklik, hacim, sosyal medya ve arama egilimlerinden hesaplanir.
    Gecmise bakan bir olcudur; gelecegi tahmin etmez.
    """
    try:
        y = _oturum.get("https://api.alternative.me/fng/",
                        params={"limit": gun}, timeout=ZAMAN_ASIMI).json()
        kayitlar = y["data"]
        gecmis = pd.DataFrame([{
            "zaman": pd.to_datetime(int(k["timestamp"]), unit="s", utc=True),
            "deger": int(k["value"]),
        } for k in kayitlar]).sort_values("zaman").reset_index(drop=True)
        return {
            "deger": int(kayitlar[0]["value"]),
            "sinif": kayitlar[0]["value_classification"],
            "gecmis": gecmis,
        }
    except Exception:
        return None


TURKCE_SINIF = {
    "Extreme Fear": "Aşırı korku",
    "Fear": "Korku",
    "Neutral": "Nötr",
    "Greed": "Açgözlülük",
    "Extreme Greed": "Aşırı açgözlülük",
}
