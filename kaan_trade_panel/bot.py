r"""
KAAN-TRADE  ---  Kripto "Paper Trading" (Sanal Para) Botu
==========================================================

Bu bot GERÇEK PARA KULLANMAZ. Borsaya sadece "fiyat kaça?" diye sorar.
Alım-satım işlemleri bilgisayarınızın içinde, hayali bir cüzdanda yapılır.
Kod içinde hiçbir API anahtari (sifre) yok, dolayisiyla borsaya emir
gonderme yetkisi de yok.

Nasil calistirilir:
    .\.venv\Scripts\python.exe bot.py

Durdurmak icin: klavyeden Ctrl + C
"""

import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import ccxt
import pandas as pd

# Windows konsolunda Turkce harfler bozulmasin diye:
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ============================================================
#  1) AYARLAR  --  Degistirmek isteyeceginiz her sey burada
# ============================================================

AYARLAR = {
    # Hangi borsadan fiyat okunacak
    "borsa": "binance",

    # Hangi coin izlenecek. "BTC/USDT" = Bitcoin'in dolar cinsinden fiyati
    "sembol": "BTC/USDT",

    # Her mumun kac dakikalik oldugu. "1m", "5m", "15m", "1h", "4h", "1d"
    "zaman_dilimi": "1h",

    # Strateji ayarlari (asagida "STRATEJI" bolumunde anlatiliyor)
    "hizli_ortalama": 10,
    "yavas_ortalama": 30,

    # Sanal cuzdan: kac dolarla basliyoruz
    "baslangic_bakiye": 1000.0,

    # Borsalar her islemden komisyon alir. Gerceklige yakin olsun diye
    # biz de hayali bir komisyon dusuyoruz (yuzde olarak).
    "islem_ucreti_yuzde": 0.1,

    # Alim yaparken elimizdeki nakdin ne kadarini kullanalim (0.95 = %95)
    "islem_orani": 0.95,

    # Bot iki kontrol arasinda kac saniye beklesin
    "dongu_saniye": 60,
}


# Dosya yollari (bot.py ile ayni klasorde olusurlar)
KLASOR = Path(__file__).parent
CUZDAN_DOSYASI = KLASOR / "cuzdan.json"
ISLEM_KAYDI = KLASOR / "islemler.csv"


# ============================================================
#  2) SANAL CUZDAN
# ============================================================

class Cuzdan:
    """Hayali paramizi ve coinimizi tutan kumbara."""

    def __init__(self, baslangic_bakiye, cuzdan_dosyasi=None):
        self.nakit = baslangic_bakiye          # elimizdeki dolar
        self.coin = 0.0                        # elimizdeki coin miktari
        self.baslangic = baslangic_bakiye      # karsilastirma icin
        self.islem_sayisi = 0
        # cuzdan_dosyasi VERILMEZSE bot.py'nin kendi varsayilan dosyasi
        # kullanilir -- sanal_trader.py gibi baska bir surec, kendi
        # klasorune kaydetmek icin farkli bir yol verebilir. Boylece
        # bu sinif iki yerde de (kod tekrari olmadan) kullanilabiliyor.
        self.cuzdan_dosyasi = cuzdan_dosyasi or CUZDAN_DOSYASI

    # --- Diske kaydet / diskten oku -------------------------
    # Boylece botu kapatip acinca sifirdan baslamaz.

    def kaydet(self):
        self.cuzdan_dosyasi.parent.mkdir(parents=True, exist_ok=True)
        self.cuzdan_dosyasi.write_text(json.dumps({
            "nakit": self.nakit,
            "coin": self.coin,
            "baslangic": self.baslangic,
            "islem_sayisi": self.islem_sayisi,
        }, indent=2), encoding="utf-8")

    @classmethod
    def yukle(cls, baslangic_bakiye, cuzdan_dosyasi=None):
        dosya = cuzdan_dosyasi or CUZDAN_DOSYASI
        c = cls(baslangic_bakiye, cuzdan_dosyasi=dosya)
        if dosya.exists():
            try:
                v = json.loads(dosya.read_text(encoding="utf-8"))
                c.nakit = float(v["nakit"])
                c.coin = float(v["coin"])
                c.baslangic = float(v.get("baslangic", baslangic_bakiye))
                c.islem_sayisi = int(v.get("islem_sayisi", 0))
                print(f"[i] Onceki cuzdan bulundu ve yuklendi ({dosya.name})")
            except Exception as e:
                print(f"[!] cuzdan.json okunamadi, sifirdan baslaniyor: {e}")
        return c

    # --- Islemler -------------------------------------------

    def elimizde_coin_var(self):
        return self.coin > 0

    def toplam_deger(self, fiyat):
        """Nakit + coinlerin o anki dolar karsiligi."""
        return self.nakit + self.coin * fiyat

    def kar_yuzdesi(self, fiyat):
        return (self.toplam_deger(fiyat) / self.baslangic - 1) * 100

    def al(self, fiyat, ucret_yuzde, oran):
        """Nakidin bir kismiyla coin satin alir (sanal)."""
        harcanacak = self.nakit * oran
        if harcanacak < 1:
            return None
        ucret = harcanacak * ucret_yuzde / 100
        alinan_coin = (harcanacak - ucret) / fiyat

        self.nakit -= harcanacak
        self.coin += alinan_coin
        self.islem_sayisi += 1
        return {"miktar": alinan_coin, "tutar": harcanacak, "ucret": ucret}

    def sat(self, fiyat, ucret_yuzde):
        """Elimizdeki tum coini satar (sanal)."""
        if self.coin <= 0:
            return None
        brut = self.coin * fiyat
        ucret = brut * ucret_yuzde / 100
        net = brut - ucret

        satilan = self.coin
        self.coin = 0.0
        self.nakit += net
        self.islem_sayisi += 1
        return {"miktar": satilan, "tutar": net, "ucret": ucret}


# ============================================================
#  3) BORSADAN VERI ALMA
# ============================================================

def borsa_baglan(borsa_adi):
    """
    Borsaya baglanir. DIKKAT: hicbir sifre/anahtar verilmiyor,
    yani bu baglanti sadece herkese acik fiyat verisini okuyabilir.
    """
    sinif = getattr(ccxt, borsa_adi)
    return sinif({"enableRateLimit": True, "timeout": 20000})


def mum_verisi_al(borsa, sembol, zaman_dilimi, adet=200):
    """
    Borsadan gecmis fiyat verisini ("mum" / candlestick) ceker
    ve pandas tablosuna cevirir.

    Her mum sunlari soyler: acilis, en yuksek, en dusuk, kapanis, hacim.
    """
    ham = borsa.fetch_ohlcv(sembol, timeframe=zaman_dilimi, limit=adet)
    df = pd.DataFrame(ham, columns=["zaman", "acilis", "yuksek", "dusuk", "kapanis", "hacim"])
    df["zaman"] = pd.to_datetime(df["zaman"], unit="ms", utc=True)

    # Son mum henuz KAPANMAMIS olabilir (fiyati hala degisiyor).
    # Yaniltici sinyal uretmesin diye onu atiyoruz.
    return df.iloc[:-1].reset_index(drop=True)


# ============================================================
#  4) STRATEJI  --  "Ne zaman al, ne zaman sat?"
# ============================================================
#
# Burada cok bilinen basit bir ornek kullaniyoruz:
# "Hareketli Ortalama Kesismesi" (Moving Average Crossover).
#
#   * HIZLI ortalama = son 10 mumun ortalama fiyati (cabuk tepki verir)
#   * YAVAS ortalama = son 30 mumun ortalama fiyati (agir hareket eder)
#
#   Hizli olan yavasi YUKARI keserse  -> yukselis basliyor olabilir -> AL
#   Hizli olan yavasi ASAGI keserse   -> dusus basliyor olabilir    -> SAT
#
# ONEMLI: Bu bir OGRENME ornegidir, yatirim tavsiyesi DEGILDIR.
# Basit ortalama stratejileri yatay piyasalarda cok sik hatali sinyal
# uretir. Amac burada botun nasil calistigini gormek.

def ortalamalari_hesapla(df, hizli, yavas):
    df = df.copy()
    df["hizli_ma"] = df["kapanis"].rolling(window=hizli).mean()
    df["yavas_ma"] = df["kapanis"].rolling(window=yavas).mean()
    return df


def sinyal_uret(df):
    """
    Son iki muma bakar ve "AL", "SAT" veya "BEKLE" dondurur.
    """
    if len(df) < 2:
        return "BEKLE", "Yeterli veri yok"

    onceki = df.iloc[-2]
    simdi = df.iloc[-1]

    # Ortalamalar henuz hesaplanamadiysa (yeterli mum yoksa) bekle
    degerler = [onceki["hizli_ma"], onceki["yavas_ma"], simdi["hizli_ma"], simdi["yavas_ma"]]
    if any(pd.isna(d) for d in degerler):
        return "BEKLE", "Ortalamalar icin yeterli mum yok"

    onceki_ustte = onceki["hizli_ma"] > onceki["yavas_ma"]
    simdi_ustte = simdi["hizli_ma"] > simdi["yavas_ma"]

    if not onceki_ustte and simdi_ustte:
        return "AL", "Hizli ortalama yavasi yukari kesti"
    if onceki_ustte and not simdi_ustte:
        return "SAT", "Hizli ortalama yavasi asagi kesti"

    yon = "hizli ustte (yukselis egilimi)" if simdi_ustte else "yavas ustte (dusus egilimi)"
    return "BEKLE", f"Kesisme yok - {yon}"


# ============================================================
#  5) ISLEM KAYDI (CSV)
# ============================================================

def islem_kaydet(satir):
    """Her sanal islemi islemler.csv dosyasina ekler (Excel'de acilabilir)."""
    yeni_dosya = not ISLEM_KAYDI.exists()
    with ISLEM_KAYDI.open("a", newline="", encoding="utf-8-sig") as f:
        yazici = csv.DictWriter(f, fieldnames=[
            "tarih", "islem", "sembol", "fiyat", "miktar",
            "tutar", "ucret", "nakit", "coin", "portfoy_degeri", "sebep",
        ])
        if yeni_dosya:
            yazici.writeheader()
        yazici.writerow(satir)


# ============================================================
#  6) ANA DONGU
# ============================================================

def tek_tur(borsa, cuzdan, a):
    """Bir kez fiyata bakar, gerekiyorsa sanal islem yapar."""
    df = mum_verisi_al(borsa, a["sembol"], a["zaman_dilimi"])
    df = ortalamalari_hesapla(df, a["hizli_ortalama"], a["yavas_ortalama"])

    sinyal, sebep = sinyal_uret(df)
    fiyat = float(df.iloc[-1]["kapanis"])
    saat = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n[{saat}]  {a['sembol']}  fiyat: {fiyat:,.2f}")
    print(f"   Sinyal : {sinyal}  ({sebep})")

    sonuc = None
    if sinyal == "AL" and not cuzdan.elimizde_coin_var():
        sonuc = cuzdan.al(fiyat, a["islem_ucreti_yuzde"], a["islem_orani"])
        if sonuc:
            print(f"   >> SANAL ALIM : {sonuc['miktar']:.8f} coin, {sonuc['tutar']:,.2f} USDT")
    elif sinyal == "SAT" and cuzdan.elimizde_coin_var():
        sonuc = cuzdan.sat(fiyat, a["islem_ucreti_yuzde"])
        if sonuc:
            print(f"   >> SANAL SATIS: {sonuc['miktar']:.8f} coin, {sonuc['tutar']:,.2f} USDT")
    else:
        durum = "coin elimizde" if cuzdan.elimizde_coin_var() else "nakitte bekliyoruz"
        print(f"   Islem yok ({durum})")

    if sonuc:
        cuzdan.kaydet()
        islem_kaydet({
            "tarih": saat,
            "islem": sinyal,
            "sembol": a["sembol"],
            "fiyat": round(fiyat, 2),
            "miktar": round(sonuc["miktar"], 8),
            "tutar": round(sonuc["tutar"], 2),
            "ucret": round(sonuc["ucret"], 4),
            "nakit": round(cuzdan.nakit, 2),
            "coin": round(cuzdan.coin, 8),
            "portfoy_degeri": round(cuzdan.toplam_deger(fiyat), 2),
            "sebep": sebep,
        })

    print(f"   Cuzdan : {cuzdan.nakit:,.2f} USDT + {cuzdan.coin:.8f} coin")
    print(f"   Toplam : {cuzdan.toplam_deger(fiyat):,.2f} USDT "
          f"({cuzdan.kar_yuzdesi(fiyat):+.2f}%)  |  {cuzdan.islem_sayisi} islem")


def main():
    a = AYARLAR

    print("=" * 62)
    print("  KAAN-TRADE  --  SANAL (PAPER) TRADING BOTU")
    print("  Gercek para KULLANILMIYOR. Sadece fiyat okunuyor.")
    print("=" * 62)
    print(f"  Borsa        : {a['borsa']}")
    print(f"  Coin         : {a['sembol']}")
    print(f"  Zaman dilimi : {a['zaman_dilimi']}")
    print(f"  Strateji     : {a['hizli_ortalama']} / {a['yavas_ortalama']} hareketli ortalama kesismesi")
    print(f"  Kontrol araligi: {a['dongu_saniye']} saniye")
    print("=" * 62)

    borsa = borsa_baglan(a["borsa"])
    cuzdan = Cuzdan.yukle(a["baslangic_bakiye"])

    hata_ust_uste = 0
    try:
        while True:
            try:
                tek_tur(borsa, cuzdan, a)
                hata_ust_uste = 0
            except ccxt.NetworkError as e:
                hata_ust_uste += 1
                print(f"[!] Internet/borsa baglanti sorunu ({hata_ust_uste}. kez): {str(e)[:100]}")
                print("    Birazdan tekrar denenecek.")
            except ccxt.ExchangeError as e:
                print(f"[!] Borsa hata verdi: {str(e)[:150]}")
                print("    Muhtemelen 'sembol' ayari bu borsada yok. bot.py icindeki AYARLAR'i kontrol edin.")
                break

            print(f"   ... {a['dongu_saniye']} saniye bekleniyor (durdurmak icin Ctrl+C)")
            time.sleep(a["dongu_saniye"])

    except KeyboardInterrupt:
        print("\n\n[i] Bot durduruldu. Cuzdan kaydedildi.")
        cuzdan.kaydet()


if __name__ == "__main__":
    main()
