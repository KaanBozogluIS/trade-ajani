r"""
HABERLER
========

Global haber sitelerinden RSS ile kripto ve piyasa haberlerini toplar.

RSS nedir? Haber sitelerinin "burada en son ne yayınladım" listesini
otomatik okunabilir bicimde yayinladigi standart bir format. API anahtari
gerektirmez, herkese aciktir -- tarayicinizda "abone ol" dugmesi gordugunuz
haber sitelerinin cogu bunu sunar.

TASARIM KURALI: veri_kaynaklari.py'deki gibi, her fonksiyon hata
durumunda COKMEZ, bos liste dondurur. Bir haber kaynagi coksede
diger kaynaklardan gelen haberler gosterilmeye devam eder.
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests

ZAMAN_ASIMI = 10

_oturum = requests.Session()
_oturum.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) kaan-trade/1.0"})


# ============================================================
#  KAYNAKLAR
# ============================================================
# Hepsi ucretsiz, API anahtari istemez. Kripto-odakli kaynaklar ana
# haber akisini, genel piyasa kaynaklari makro baglami saglar (Fed
# karari, enflasyon verisi gibi kripto fiyatlarini da etkileyen seyler).

KAYNAKLAR = {
    "CoinDesk":       {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "tur": "kripto"},
    "CoinTelegraph":  {"url": "https://cointelegraph.com/rss", "tur": "kripto"},
    "Decrypt":        {"url": "https://decrypt.co/feed", "tur": "kripto"},
    "CryptoSlate":    {"url": "https://cryptoslate.com/feed/", "tur": "kripto"},
    "Bitcoin.com":    {"url": "https://news.bitcoin.com/feed/", "tur": "kripto"},
    "The Block":      {"url": "https://www.theblock.co/rss.xml", "tur": "kripto"},
    "Investing.com":  {"url": "https://www.investing.com/rss/news_301.rss", "tur": "kripto"},
    "MarketWatch":    {"url": "https://feeds.content.dowjones.io/public/rss/mw_topstories", "tur": "genel"},
    "CNBC Markets":   {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258", "tur": "genel"},
}

# Basliktan coin adi yakalamak icin basit anahtar kelime eslesmesi.
# NLP degil -- sadece "bu haberde hangi coin geciyor" etiketi icin.
COIN_ANAHTAR = {
    "BTC": ["bitcoin", "btc"],
    "ETH": ["ethereum", "eth ", "ether "],
    "SOL": ["solana", " sol "],
    "XRP": ["ripple", "xrp"],
    "BNB": ["binance coin", " bnb"],
    "DOGE": ["dogecoin", "doge"],
    "ADA": ["cardano", " ada "],
    "AVAX": ["avalanche", "avax"],
    "LINK": ["chainlink"],
    "DOT": ["polkadot"],
}


def _coin_etiketleri(baslik):
    """Baslikta gecen coin isimlerini bulur (en fazla 3)."""
    b = f" {baslik.lower()} "
    bulunan = []
    for kod, anahtarlar in COIN_ANAHTAR.items():
        if any(a in b for a in anahtarlar):
            bulunan.append(kod)
    return bulunan[:3]


def _zaman_ayikla(girdi):
    """
    feedparser'in verdigi tarihi UTC datetime'a cevirir.
    Format kaynaktan kaynaga degisir, o yuzden birkac yol deneriz.
    """
    for alan in ("published_parsed", "updated_parsed"):
        deger = girdi.get(alan)
        if deger:
            try:
                return datetime(*deger[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    for alan in ("published", "updated"):
        deger = girdi.get(alan)
        if deger:
            try:
                return parsedate_to_datetime(deger).astimezone(timezone.utc)
            except Exception:
                pass
    return None


_HTML_ETIKET = re.compile(r"<[^>]+>")


def _temizle(metin, uzunluk=220):
    """HTML etiketlerini atar, metni kirpar."""
    if not metin:
        return ""
    duz = _HTML_ETIKET.sub("", metin).strip()
    duz = re.sub(r"\s+", " ", duz)
    return duz[:uzunluk].rstrip() + ("…" if len(duz) > uzunluk else "")


def kaynak_oku(isim, url, zaman_asimi=ZAMAN_ASIMI):
    """Tek bir RSS kaynagindan haberleri okur. Hata olursa bos liste doner."""
    try:
        y = _oturum.get(url, timeout=zaman_asimi)
        if y.status_code != 200:
            return []
        ayrisan = feedparser.parse(y.content)
        haberler = []
        for girdi in ayrisan.entries[:20]:
            baslik = (girdi.get("title") or "").strip()
            if not baslik:
                continue
            haberler.append({
                "kaynak": isim,
                "baslik": baslik,
                "ozet": _temizle(girdi.get("summary") or girdi.get("description")),
                "link": girdi.get("link"),
                "zaman": _zaman_ayikla(girdi),
                "coinler": _coin_etiketleri(baslik),
            })
        return haberler
    except Exception:
        return []


def tumunu_getir(kaynaklar=None, zaman_asimi=ZAMAN_ASIMI):
    """
    Butun kaynaklardan haberleri toplar, tarihe gore en yeniden en
    eskiye siralar. Tarihi olmayan haberler sona atilir (yok sayilmaz,
    listede kalir ama en altta gorunur).

    Kaynaklar PARALEL okunur (ThreadPoolExecutor). NEDEN: sirayla
    okusaydik, her kaynak en fazla <zaman_asimi> saniye bekleyebildigi
    icin (9 kaynak x 10 sn = 90 saniyeye kadar) 5 dakikalik onbellek
    dolup bu fonksiyon tekrar cagrildiginda butun sayfa uzun sure
    donebilirdi. Paralel okuma toplam sureyi TEK bir kaynagin suresine
    (en yavas olan ~10 sn) indirir. kaynak_oku zaten hicbir istisna
    firlatmadigi icin (hepsini yakalayip [] donuyor) burada ekstra
    try/except gerekmiyor.
    """
    kaynaklar = kaynaklar or KAYNAKLAR
    hepsi = []
    basarili, basarisiz = [], []

    with ThreadPoolExecutor(max_workers=len(kaynaklar)) as havuz:
        gorevler = {havuz.submit(kaynak_oku, isim, bilgi["url"], zaman_asimi): isim
                    for isim, bilgi in kaynaklar.items()}
        for gorev in as_completed(gorevler):
            isim = gorevler[gorev]
            h = gorev.result()
            if h:
                basarili.append(isim)
                hepsi.extend(h)
            else:
                basarisiz.append(isim)

    simdi = datetime.now(timezone.utc)
    hepsi.sort(key=lambda x: x["zaman"] or simdi.replace(year=2000), reverse=True)
    return hepsi, basarili, basarisiz


def yas_yaz(zaman):
    """'3 saat önce' gibi okunur bir sure yazar."""
    if zaman is None:
        return ""
    saniye = (datetime.now(timezone.utc) - zaman).total_seconds()
    if saniye < 0:
        saniye = 0
    if saniye < 60:
        return "az önce"
    if saniye < 3600:
        return f"{int(saniye // 60)} dakika önce"
    if saniye < 86400:
        return f"{int(saniye // 3600)} saat önce"
    return f"{int(saniye // 86400)} gün önce"
