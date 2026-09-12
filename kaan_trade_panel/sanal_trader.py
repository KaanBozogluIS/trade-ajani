r"""
SANAL TRADER  --  Coklu Pozisyon, Otomatik Rotasyonlu Sanal Alim-Satim Motoru
==============================================================================

Bu bot GERCEK PARA KULLANMAZ. Borsaya sadece "fiyat kaca?" diye sorar.
Alim-satim islemleri bilgisayarinizin icinde, hayali bir portfoyde yapilir.
Kod icinde hicbir API anahtari (sifre) yok, dolayisiyla borsaya emir
gonderme yetkisi de yok.

NE YAPAR?
    TEK bir sanal portfoyle, GENIS bir likit-coin evreninde (BTC/ETH
    kadar altcoinler de dahil -- bkz. AYARLAR) AYNI ANDA BIRDEN FAZLA
    pozisyon tutabilir. Onceki surumden (bkz. git/README gecmisi) farki:
    o surum "tek anda tek coin" secip rotasyon yapiyordu; bu surum
    "ayni anda coklu coin" tutabiliyor -- kullanicinin "tum coinlerle
    anlik islem yapsin" istegi budur.

    1. HER dongude (varsayilan saatte bir -- yeni saatlik mumla ayni
       anda, daha sik anlami yok cunku veri de o hizda degisiyor) o
       anki likit evrendeki HER coin icin, HANGI stratejinin (16 klasik
       + SFP/Order Block/Fair Value Gap/Destek-Direnc kirilmasi) o
       coinde en iyi performans gosterdigini olcer (dogrulama.simule_et
       ile -- 16 stratejiyi test ettigimiz AYNI motor). Sonuc: her coin,
       kendi "en iyi" stratejisine atanir -- bu, sadece YENI ACILACAK
       pozisyonlar icin gecerlidir (bkz. 2). Secimler VE en iyi 5 aday
       rotasyon_gunlugu.csv'ye yazilir -- her karar denetlenebilir.
    2. HER ATANMIS coin icin: pozisyon ZATEN ACIKSA, o pozisyonun
       ACILDIGI stratejinin sinyaline bakilir (rotasyon o coin icin
       baska bir strateji daha iyi cikmis olsa bile, acik bir pozisyon
       ORTASINDA strateji degistirmek tutarsiz olur); pozisyon
       ACIK DEGILSE, GUNCEL rotasyon atamasinin sinyaline bakilir.
       Sinyal "icerde" ise VE bos pozisyon yeri varsa AL, "disarda"
       ise VE o coin elimizde ise SAT. Boylece coklu coin ayni anda,
       birbirinden bagimsiz pozisyonda olabilir.
    3. Pozisyon buyuklugu: yeni bir pozisyon acilirken, o andaki
       kullanilabilir nakit, KALAN bos pozisyon yeri sayisina esit
       bolunur (basit esit-agirlik). Var olan pozisyonlar bu yuzden
       surekli yeniden dengelenmez -- sadece YENI girislerde boyut
       belirlenir.

DURUSTLUK NOTU (ONEMLI, OKUYUN): strateji_desenleri.py'deki 4 yeni desen
(SFP, Order Block, Fair Value Gap, Destek/Direnc kirilmasi), tarama_desenler
.py ile mevcut 16 stratejiyle AYNI rastgele-kontrol-grubu yontemiyle test
edildi -- HICBIRI rastgeleyi istatistiksel olarak gecemedi (bkz. README.md,
"Sanal Trader" bolumu). "En iyi performans gosteren" stratejinin
GELECEKTE de iyi gidecegi GARANTI DEGILDIR -- sadece GECMISTE en iyi
performans gosterenin secildigi anlamina gelir ("yakin gecmisi kovalama"
riski). Bu bot bir KAR GARANTISI degil, bir GOZLEM aracidir.

Nasil calistirilir:
    .\.venv\Scripts\python.exe sanal_trader.py
    (ya da calistir_sanal_trader.bat'a cift tiklayin)

Durdurmak icin: klavyeden Ctrl + C
"""

import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import ccxt
import pandas as pd

import canli_veri as cv
import veri_kaynaklari as vk
from dogrulama import simule_et
from strateji_desenleri import DESEN_STRATEJILERI
from strateji_desenleri import isinma_suresi as desen_isinma_suresi
from stratejiler import STRATEJILER
from stratejiler import isinma_suresi as klasik_isinma_suresi

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def al(sozluk, anahtar):
    """Sozlukten guvenli okuma: yoksa None doner, cokmez."""
    return sozluk.get(anahtar) if sozluk else None


def _atomik_yaz(yol, metin):
    """
    Bir dosyayi ATOMIK olarak yazar: once gecici bir dosyaya yazip,
    sonra isim degistirerek (os.replace) hedefin yerine koyar.

    NEDEN GEREKLI: sanal_trader.py (bu surec) bu dosyalari saniyede
    birkac kez yazarken, panel (uygulama.py, AYRI bir surec) AYNI ANDA
    okuyabilir. Duz write_text() ONCE dosyayi BOSALTIP sonra icerigi
    yazar -- panel TAM o arada okursa BOS ya da YARIM (bozuk) JSON
    gorur ve cokmese bile "veri okunamadi" hatasi verir (gercekten
    yasandi -- bkz. git gecmisi). os.replace() ise TEK bir adimda
    "eski dosyanin YERINE yenisini koy" yapar -- okuyan taraf ya
    TAMAMEN ESKI ya da TAMAMEN YENI icerigi gorur, YARIM asla.
    """
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(yol.suffix + ".tmp")
    gecici.write_text(metin, encoding="utf-8")
    os.replace(gecici, yol)


# ============================================================
#  1) AYARLAR
# ============================================================

AYARLAR = {
    # Evren: canli_veri uzerinden BUTUN USDT ciftlerinden, bu dolar
    # hacminin USTUNDEKI en likit <evren_boyutu> tanesi secilir --
    # "tum coinler" ama guvenilmez/dusuk-hacimli coinler otomatik
    # elenir (panelin geri kalaninda da ayni ilke kullaniliyor).
    "en_az_hacim": 5_000_000,      # 24s hacim esigi (dolar)
    "evren_boyutu": 40,            # en likit N coin
    "maks_pozisyon": 8,            # ayni anda en fazla kac coin'de pozisyon
    # SAATLIK mumlar -- gunluk yerine, sinyaller (ve dolayisiyla islemler)
    # cok daha sik uretilsin diye. Bu bir "daha cok islem = daha iyi"
    # varsayimi DEGIL -- sadece kullanicinin "surekli calistigini gormek"
    # istegini karsilamak icin bilincli bir tercih.
    "zaman_dilimi": "1h",
    "baslangic_bakiye": 1000.0,
    "islem_ucreti_yuzde": 0.1,
    "islem_orani": 0.95,
    # ROTASYON SIKLIGI: her saat basi -- yani HER dongude. Daha sik
    # anlami YOK: veri de (saatlik mum) saatte bir degisiyor, ondan once
    # tekrar olcmek AYNI sonucu tekrar tekrar hesaplamak olurdu. "Her an/
    # surekli calissin" istegini, VERININ izin verdigi en sik -- ve
    # gercekten anlamli -- ölçekte karsiliyoruz.
    #
    # BEDELI: 3 gunde bir yerine saatte bir yeniden secim, "yakin
    # gecmisi kovalama" riskini ARTIRIR (bir coin icin secilen strateji
    # saatten saate degisebilir). Bunu dengelemek icin ac_pozisyonlar
    # ARTIK kendi ACILDIKLARI stratejiye baglı kalir (bkz. tek_coin_
    # kontrolu) -- rotasyon sadece YENI girisler icin "hangi strateji"
    # sorusunu her saat yeniden sorar, halihazirda acik bir pozisyonu
    # ortasinda strateji degistirerek tutarsizlastirmaz.
    "rotasyon_periyodu_saat": 1,
    "geriye_donuk_pencere_gun": 30,    # rotasyon karari icin bakilan gecmis pencere
    "dongu_saniye": 3600,              # kontroller arasi bekleme (saatlik mumla hizali)
}

# Zaman dilimine gore bir mumun kac saat surdugu -- "gun" cinsinden
# ayarlari (geriye_donuk_pencere_gun gibi) dogru sayida MUMA cevirmek icin.
_SAAT_PER_MUM = {"1m": 1 / 60, "5m": 5 / 60, "15m": 15 / 60, "30m": 0.5,
                 "1h": 1, "4h": 4, "1d": 24}


def _gun_to_mum(gun, zaman_dilimi):
    saat = _SAAT_PER_MUM.get(zaman_dilimi, 24)
    return int(gun * 24 / saat)


KLASOR = Path(__file__).parent
CIKTI_KLASORU = KLASOR / "cikti" / "sanal_trader"
PORTFOY_DOSYASI = CIKTI_KLASORU / "portfoy.json"
POZISYON_DOSYASI = CIKTI_KLASORU / "pozisyonlar.json"
ISLEM_DOSYASI = CIKTI_KLASORU / "islemler.csv"
ROTASYON_DOSYASI = CIKTI_KLASORU / "rotasyon_gunlugu.csv"
DURUM_DOSYASI = CIKTI_KLASORU / "durum.json"
# Sadece ROTASYON SURERKEN var olan, gecici bir "calisiyorum" isareti.
# Ilk rotasyon (40 coin x 19 strateji) birkac dakika surer ve o sure
# boyunca DURUM_DOSYASI HENUZ yazilmamis olur -- bu dosya olmadan panel
# (ve konsoldan izleyen kullanici) "hicbir sey olmuyor mu?" diye
# tereddut eder. Rotasyon bitince silinir (bkz. rotasyonu_uygula).
CALISMA_DOSYASI = CIKTI_KLASORU / "calisma_durumu.json"


# ============================================================
#  2) COKLU POZISYON PORTFOYU
# ============================================================

class Portfoy:
    """
    bot.py'deki tek-coinlik Cuzdan'in coklu-pozisyon hali: nakit +
    {sembol: {"miktar", "strateji", "giris_fiyat", "giris_zamani"}}.

    NEDEN AYRI BIR SINIF (Cuzdan'i genisletmek yerine): Cuzdan'in
    "self.coin = tek bir sayi" varsayimi butun sinifin omurgasinda --
    coklu pozisyon icin veri modeli baştan farkli olmak zorunda. bot.py
    kendi tek-coin akisinda degismeden calismaya devam ediyor.
    """

    def __init__(self, baslangic_bakiye):
        self.nakit = baslangic_bakiye
        self.pozisyonlar = {}          # sembol -> {"miktar","strateji","giris_fiyat","giris_zamani"}
        self.baslangic = baslangic_bakiye
        self.islem_sayisi = 0

    def kaydet(self):
        _atomik_yaz(PORTFOY_DOSYASI, json.dumps({
            "nakit": self.nakit, "baslangic": self.baslangic,
            "islem_sayisi": self.islem_sayisi,
        }, indent=2))
        _atomik_yaz(POZISYON_DOSYASI,
                    json.dumps(self.pozisyonlar, indent=2, ensure_ascii=False))

    @classmethod
    def yukle(cls, baslangic_bakiye):
        p = cls(baslangic_bakiye)
        if PORTFOY_DOSYASI.exists():
            try:
                v = json.loads(PORTFOY_DOSYASI.read_text(encoding="utf-8"))
                p.nakit = float(v["nakit"])
                p.baslangic = float(v.get("baslangic", baslangic_bakiye))
                p.islem_sayisi = int(v.get("islem_sayisi", 0))
                print(f"[i] Onceki portfoy bulundu ve yuklendi ({PORTFOY_DOSYASI.name})")
            except Exception as e:
                print(f"[!] portfoy.json okunamadi, sifirdan baslaniyor: {e}")
        if POZISYON_DOSYASI.exists():
            try:
                p.pozisyonlar = json.loads(POZISYON_DOSYASI.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[!] pozisyonlar.json okunamadi, bos baslaniyor: {e}")
        return p

    def bos_pozisyon_yeri(self, maks_pozisyon):
        return max(0, maks_pozisyon - len(self.pozisyonlar))

    def ac(self, sembol, strateji, fiyat, tutar, ucret_yuzde):
        """<tutar> USDT'lik nakitle sembolu satin alir (sanal)."""
        if tutar < 1 or tutar > self.nakit:
            return None
        ucret = tutar * ucret_yuzde / 100
        miktar = (tutar - ucret) / fiyat
        self.nakit -= tutar
        self.pozisyonlar[sembol] = {
            "miktar": miktar, "strateji": strateji, "giris_fiyat": fiyat,
            "giris_zamani": datetime.now(timezone.utc).isoformat(),
            "maliyet": tutar,  # nakitten cikan TAM tutar (ucret dahil) -- kapat()'ta kar/zarar buna gore hesaplanir
        }
        self.islem_sayisi += 1
        return {"miktar": miktar, "tutar": tutar, "ucret": ucret}

    def kapat(self, sembol, fiyat, ucret_yuzde):
        """
        Elimizdeki <sembol> pozisyonunun TAMAMINI satar (sanal) ve bu
        ISLEMIN kar/zararini hesaplar -- "hangi strateji ne zaman
        kazandirdi/kaybettirdi" sorusuna cevap vermek icin (bkz.
        islem_kaydet, panelde "Strateji performansı" tablosu).
        """
        pozisyon = self.pozisyonlar.get(sembol)
        if not pozisyon:
            return None
        miktar = pozisyon["miktar"]
        brut = miktar * fiyat
        ucret = brut * ucret_yuzde / 100
        net = brut - ucret
        self.nakit += net
        del self.pozisyonlar[sembol]
        self.islem_sayisi += 1

        maliyet = pozisyon.get("maliyet") or (miktar * pozisyon.get("giris_fiyat", fiyat))
        kar_zarar = net - maliyet
        kar_zarar_yuzde = (kar_zarar / maliyet * 100) if maliyet else 0.0
        return {"miktar": miktar, "tutar": net, "ucret": ucret,
               "kar_zarar": kar_zarar, "kar_zarar_yuzde": kar_zarar_yuzde}

    def toplam_deger(self, fiyatlar):
        """fiyatlar: {sembol: fiyat} -- elimizdeki her pozisyon icin gerekir."""
        deger = self.nakit
        for sembol, pozisyon in self.pozisyonlar.items():
            fiyat = fiyatlar.get(sembol)
            if fiyat:
                deger += pozisyon["miktar"] * fiyat
        return deger

    def kar_yuzdesi(self, fiyatlar):
        return (self.toplam_deger(fiyatlar) / self.baslangic - 1) * 100


# ============================================================
#  3) EVREN: en likit N coin (canli_veri uzerinden)
# ============================================================

# Stabilcoin/USDT ciftleri (USDC/USDT gibi) fiyatca neredeyse hic
# oynamaz -- "strateji" acisindan anlamsizdir, sadece bir pozisyon
# yerini bosuna isgal eder. Evrenden bilerek cikariliyor.
_STABILCOIN_KODLARI = {"USDC", "USD1", "RLUSD", "FDUSD", "TUSD", "DAI",
                       "BUSD", "PYUSD", "USDP", "EUR", "EURI", "USDE"}


def evreni_sec(depo, a):
    """
    canli_veri'nin (ayni anda ~650-700 USDT ciftini izleyen) tablosundan,
    hacim esigini gecen en likit <evren_boyutu> coini dondurur --
    stabilcoin ciftleri haric (bkz. yukaridaki not).
    """
    semboller = depo.semboller(a["en_az_hacim"])
    semboller = [s for s in semboller if s.split("/")[0] not in _STABILCOIN_KODLARI]
    evren = semboller[:a["evren_boyutu"]]
    if not evren:
        # BOS EVREN SESSIZCE GECILMEMELI -- rotasyon o zaman hicbir sey
        # yapmaz, hicbir hata da vermez (STRATEJILER_TUMU zaten bos
        # listede donmez) ve kullanici "neden hicbir islem olmuyor?"
        # sorusuna asla cevap bulamaz. GitHub Actions gibi baska bir
        # ag/bolgeden calisirken bazi borsalar (ozellikle Binance)
        # BULUT SAGLAYICI IP araliklarini engelleyebilir -- bu durumda
        # depo.durum["hata"] genelde ipucu tasir.
        print(f"[!] UYARI: likit evren BOS (0 coin) -- depo.durum: {depo.durum}")
    return evren


# ============================================================
#  4) ADAY STRATEJI LISTESI  (bir coin icin)
# ============================================================

def _tum_stratejiler():
    """
    (isim, fonksiyon, parametreler, isinma) -- "al ve tut" ve "rastgele"
    HARIC (onlar tarama.py'de oldugu gibi KIYAS/KONTROL amaclidir,
    "secilebilir bir strateji" degildir).
    """
    liste = []
    for isim, fn, params in STRATEJILER:
        if isim in ("al ve tut", "rastgele"):
            continue
        liste.append((isim, fn, params, klasik_isinma_suresi(isim, params)))
    for isim, fn, params in DESEN_STRATEJILERI:
        liste.append((isim, fn, params, desen_isinma_suresi(isim, params)))
    return liste


_STRATEJILER_TUMU = _tum_stratejiler()
_STRATEJI_SOZLUGU = {isim: (fn, params, isinma) for isim, fn, params, isinma in _STRATEJILER_TUMU}


# ============================================================
#  5) ROTASYON: HER COIN ICIN EN IYI STRATEJIYI SEC
# ============================================================

def _calisma_durumu_kaydet(ilerleme, toplam):
    _atomik_yaz(CALISMA_DOSYASI, json.dumps({
        "asama": "rotasyon", "ilerleme": ilerleme, "toplam": toplam,
        "guncelleme": datetime.now(timezone.utc).isoformat(),
    }))


def rotasyonu_degerlendir(evren, a):
    """
    Evrendeki HER coin icin, butun stratejileri son <geriye_donuk_
    pencere_gun> gunde olcer ve en iyi getiriyi verenini o coine atar.

    Donen: {sembol: {"strateji", "getiri", "dusus", "piyasada"}}, ve
    ayrica her coin icin en iyi 5 adayin ozeti (gunluge yazmak icin).

    ONEMLI: bu, evren buyukse (40 coin x 19 strateji = 760 istek)
    BIRKAC DAKIKA surebilir. O sure boyunca hem konsola ("X/40 coin
    tarandi") hem CALISMA_DOSYASI'na ilerleme yazilir -- aksi halde
    ilk calistirmada kullanici "hicbir sey olmuyor, takildi mi?" diye
    dusunur (bu, gercekten yasanan bir kafa karisikligiydi).
    """
    pencere_mum = _gun_to_mum(a["geriye_donuk_pencere_gun"], a["zaman_dilimi"])
    atamalar = {}
    gunluk_satirlari = []
    toplam = len(evren)

    for i, coin in enumerate(evren):
        if i % 5 == 0 or i == toplam - 1:
            print(f"   ... {i}/{toplam} coin tarandi ({coin})")
        _calisma_durumu_kaydet(i, toplam)
        sonuclar = []
        for isim, fn, params, isinma in _STRATEJILER_TUMU:
            gerekli_mum = isinma + pencere_mum + 15
            df = vk.mum_verisi(coin, a["zaman_dilimi"], gerekli_mum)
            if df is None or len(df) < isinma + 30:
                continue
            try:
                poz = fn(df, **params)
            except Exception:
                continue
            sonuc = simule_et(df, poz, a, baslangic=isinma)
            if sonuc is None:
                continue
            sonuclar.append({"isim": isim, "getiri": sonuc["getiri"],
                             "dusus": sonuc["dusus"], "piyasada": sonuc["piyasada"]})

        if not sonuclar:
            continue
        sonuclar.sort(key=lambda r: r["getiri"], reverse=True)
        en_iyi = sonuclar[0]
        atamalar[coin] = {"strateji": en_iyi["isim"], "getiri": en_iyi["getiri"],
                          "dusus": en_iyi["dusus"], "piyasada": en_iyi["piyasada"]}
        gunluk_satirlari.append({
            "coin": coin, "en_iyi_5": " | ".join(
                f"{r['isim']}:{r['getiri']:+.1f}%" for r in sonuclar[:5]),
        })

    return atamalar, gunluk_satirlari


def rotasyon_kaydet(atamalar, gunluk_satirlari):
    CIKTI_KLASORU.mkdir(parents=True, exist_ok=True)
    yeni_dosya = not ROTASYON_DOSYASI.exists()
    with ROTASYON_DOSYASI.open("a", newline="", encoding="utf-8-sig") as f:
        yazici = csv.DictWriter(f, fieldnames=[
            "tarih", "coin", "secilen_strateji", "test_getirisi_yuzde", "en_iyi_5",
        ])
        if yeni_dosya:
            yazici.writeheader()
        saat = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        detay = {r["coin"]: r["en_iyi_5"] for r in gunluk_satirlari}
        for coin, bilgi in atamalar.items():
            yazici.writerow({
                "tarih": saat, "coin": coin, "secilen_strateji": bilgi["strateji"],
                "test_getirisi_yuzde": round(bilgi["getiri"], 2),
                "en_iyi_5": detay.get(coin, ""),
            })


def rotasyon_zamani_mi(durum, a):
    if durum is None or not durum.get("son_rotasyon"):
        return True
    son = datetime.fromisoformat(durum["son_rotasyon"])
    return (datetime.now(timezone.utc) - son).total_seconds() >= a["rotasyon_periyodu_saat"] * 3600


def durumu_yukle():
    if DURUM_DOSYASI.exists():
        try:
            return json.loads(DURUM_DOSYASI.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def durumu_kaydet(durum):
    _atomik_yaz(DURUM_DOSYASI, json.dumps(durum, indent=2, ensure_ascii=False))


def rotasyonu_uygula(portfoy, durum, depo, a):
    """
    Evreni yeniden secer, her coin icin en iyi stratejiyi olcer.

    Halihazirda ELIMIZDE OLAN ama yeni evrende artik yer almayan coinler
    (hacmi dustu vb.) "pozisyon_stratejileri"nden ATILMAZ -- eski
    stratejisiyle izlenmeye devam eder, boylece duzgun bir sekilde
    CIKIS yapilabilir (yeni giris icin aday olmaz, ama var olan pozisyon
    "yetim" kalmaz).
    """
    evren = evreni_sec(depo, a)
    print(f"[i] Rotasyon: {len(evren)} coinlik likit evren, "
          f"{len(_STRATEJILER_TUMU)} strateji ile test ediliyor...")

    if evren:
        # HIZLI TEYIT: gecmis mum verisi cekmek (rotasyonun butun
        # temeli) gercekten calisiyor mu? 760 istegin HEPSI sessizce
        # basarisiz olabilir (bkz. veri_kaynaklari.mum_verisi -- HER
        # hatada None doner, hicbir sey yazdirmaz) ve sonuc BOS bir
        # rotasyon olur, HICBIR ACIKLAMA olmadan. Ana dongudeki 760
        # denemeden ONCE, TEK bir denemeyle ("kanarya") sorunu erken
        # ve ACIKCA yakaliyoruz -- ozellikle GitHub Actions gibi baska
        # bir sunucudan calisirken bazi borsalar (Binance dahil) bulut
        # saglayici IP araliklarini engelleyebilir.
        deneme = vk.mum_verisi(evren[0], a["zaman_dilimi"], 50)
        if deneme is None:
            print(f"[!] TEYIT BASARISIZ: {evren[0]} icin mum verisi alinamadi. "
                  "Muhtemel sebep: bu sunucunun IP adresi borsa tarafindan "
                  "engellenmis olabilir (GitHub Actions gibi bulut "
                  "saglayicilarda bilinen bir sorun) ya da gecici bir ag "
                  "sorunu var. Rotasyonun geri kalani da basarisiz olabilir.")
        else:
            print(f"[i] Teyit basarili: {evren[0]} icin {len(deneme)} mum alindi.")

    atamalar, gunluk_satirlari = rotasyonu_degerlendir(evren, a)
    rotasyon_kaydet(atamalar, gunluk_satirlari)

    eski_atamalar = (durum or {}).get("pozisyon_stratejileri", {})
    yeni_atamalar = {coin: bilgi["strateji"] for coin, bilgi in atamalar.items()}
    # Elde tutulan ama yeni evrende olmayan coinler icin ESKI atamayi koru.
    for sembol in portfoy.pozisyonlar:
        if sembol not in yeni_atamalar and sembol in eski_atamalar:
            yeni_atamalar[sembol] = eski_atamalar[sembol]

    yeni_durum = {
        "pozisyon_stratejileri": yeni_atamalar,
        "son_rotasyon": datetime.now(timezone.utc).isoformat(),
    }
    durumu_kaydet(yeni_durum)
    CALISMA_DOSYASI.unlink(missing_ok=True)  # "rotasyon calisiyor" isareti artik gecerli degil
    print(f"[i] ROTASYON TAMAMLANDI: {len(yeni_atamalar)} coin icin strateji atandi.")
    return yeni_durum


# ============================================================
#  6) NORMAL DONGU: her atanmis coin icin AL/SAT kontrolu
# ============================================================

def islem_kaydet(saat, islem, strateji, sembol, fiyat, sonuc, portfoy, fiyatlar, sebep):
    """
    "kar_zarar"/"kar_zarar_yuzde" sutunlari SADECE SAT satirlarinda
    doludur (Portfoy.kapat()'in dondurdugu sonuc'ta bulunur) -- AL
    satirlarinda bos kalir, cunku bir alim ANINDA henuz kar/zarar
    yoktur. Boylece panelde "hangi strateji, hangi coin'de, ne zaman,
    kar mi zarar mi etti" dogrudan bu tablodan okunabilir.
    """
    CIKTI_KLASORU.mkdir(parents=True, exist_ok=True)
    yeni_dosya = not ISLEM_DOSYASI.exists()
    with ISLEM_DOSYASI.open("a", newline="", encoding="utf-8-sig") as f:
        yazici = csv.DictWriter(f, fieldnames=[
            "tarih", "islem", "strateji", "sembol", "fiyat", "miktar",
            "tutar", "ucret", "kar_zarar", "kar_zarar_yuzde", "nakit",
            "portfoy_degeri", "sebep",
        ])
        if yeni_dosya:
            yazici.writeheader()
        yazici.writerow({
            "tarih": saat, "islem": islem, "strateji": strateji, "sembol": sembol,
            "fiyat": round(fiyat, 6), "miktar": round(sonuc["miktar"], 8),
            "tutar": round(sonuc["tutar"], 2), "ucret": round(sonuc["ucret"], 4),
            "kar_zarar": round(sonuc["kar_zarar"], 2) if "kar_zarar" in sonuc else "",
            "kar_zarar_yuzde": round(sonuc["kar_zarar_yuzde"], 2) if "kar_zarar_yuzde" in sonuc else "",
            "nakit": round(portfoy.nakit, 2),
            "portfoy_degeri": round(portfoy.toplam_deger(fiyatlar), 2), "sebep": sebep,
        })


def _portfoy_fiyatlari(portfoy, depo, guncel_sembol=None, guncel_fiyat=None):
    """
    Elde tutulan HER pozisyon icin canli (depo) fiyatini toplar --
    islem_kaydet'e verilecek "portfoy_degeri" HATALI olmasin diye (sadece
    o an islem yapilan coini degil, AYNI ANDA tutulan butun coinleri
    saymasi gerekiyor). <guncel_sembol> icin (varsa) tam olarak islemde
    kullanilan fiyat (mum kapanisi) yazilir -- o, o anki islemin
    GERCEK fiyatidir, canli fiyattan ufak farkli olabilir.
    """
    fiyatlar = {}
    for sembol in portfoy.pozisyonlar:
        f = al(depo.coin(sembol), "fiyat")
        if f:
            fiyatlar[sembol] = f
    if guncel_sembol and guncel_fiyat:
        fiyatlar[guncel_sembol] = guncel_fiyat
    return fiyatlar


def tek_coin_kontrolu(portfoy, sembol, atanan_strateji, depo, a):
    """
    Bir coin icin: guncel sinyale bak, gerekiyorsa AL/SAT yap.

    <atanan_strateji>, rotasyonun O AN o coin icin "en iyi" dedigi
    stratejidir -- ama pozisyon ZATEN ACIKSA, o pozisyonun ACILDIGI
    strateji kullanilir (rotasyon saatte bir kostugu icin, acik bir
    pozisyonu ortasinda baska bir stratejiye gore satmak tutarsiz
    olurdu -- bkz. dosya basindaki not).
    """
    tutuluyor_mu = sembol in portfoy.pozisyonlar
    strateji_isim = portfoy.pozisyonlar[sembol]["strateji"] if tutuluyor_mu else atanan_strateji

    aday = _STRATEJI_SOZLUGU.get(strateji_isim)
    if aday is None:
        return None
    fn, params, isinma = aday

    df = vk.mum_verisi(sembol, a["zaman_dilimi"], isinma + 60)
    if df is None or len(df) < isinma + 30:
        return None

    try:
        poz = fn(df, **params)
    except Exception:
        return None
    son_sinyal = poz.iloc[-1]
    if pd.isna(son_sinyal):
        return None

    fiyat = float(df["kapanis"].iloc[-1])
    saat = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    if son_sinyal == 1.0 and not tutuluyor_mu:
        bos_yer = portfoy.bos_pozisyon_yeri(a["maks_pozisyon"])
        if bos_yer <= 0:
            return None
        tutar = (portfoy.nakit * a["islem_orani"]) / bos_yer
        sonuc = portfoy.ac(sembol, strateji_isim, fiyat, tutar, a["islem_ucreti_yuzde"])
        if sonuc:
            fiyatlar = _portfoy_fiyatlari(portfoy, depo, sembol, fiyat)
            islem_kaydet(saat, "AL", strateji_isim, sembol, fiyat, sonuc, portfoy,
                        fiyatlar, "sinyal")
            print(f"   >> SANAL ALIM: {sembol}  {sonuc['miktar']:.6f} "
                  f"({sonuc['tutar']:,.2f} USDT)  [{strateji_isim}]")
            return "AL"
    elif son_sinyal == 0.0 and tutuluyor_mu:
        # ONCE fiyatlari topla (pozisyon hala listede), SONRA kapat --
        # aksi halde satilan pozisyon toplam degerden eksik sayilirdi.
        fiyatlar = _portfoy_fiyatlari(portfoy, depo, sembol, fiyat)
        sonuc = portfoy.kapat(sembol, fiyat, a["islem_ucreti_yuzde"])
        if sonuc:
            islem_kaydet(saat, "SAT", strateji_isim, sembol, fiyat, sonuc, portfoy,
                        fiyatlar, "sinyal")
            print(f"   >> SANAL SATIS: {sembol}  {sonuc['miktar']:.6f} "
                  f"({sonuc['tutar']:,.2f} USDT)  [{strateji_isim}]")
            return "SAT"
    return None


# ============================================================
#  7) ANA DONGU
# ============================================================

def _baslik_yaz(a):
    print("=" * 70)
    print("  SANAL TRADER  --  COKLU POZISYON, OTOMATIK ROTASYON")
    print("  Gercek para KULLANILMIYOR. Sadece fiyat okunuyor.")
    print("=" * 70)
    print(f"  Likit evren   : en az ${a['en_az_hacim']:,.0f} hacim, en fazla {a['evren_boyutu']} coin")
    print(f"  Maks pozisyon : ayni anda {a['maks_pozisyon']} coin")
    print(f"  Strateji sayisi: {len(_STRATEJILER_TUMU)} (klasik + desen)")
    print(f"  Rotasyon      : her {a['rotasyon_periyodu_saat']} saatte bir (her dongude), "
          f"son {a['geriye_donuk_pencere_gun']} gune bakarak")
    print(f"  Kontrol araligi: {a['dongu_saniye']} saniye")
    print("=" * 70)


def bir_dongu(portfoy, durum, depo, a):
    """
    TEK bir kontrol turu: gerekirse rotasyon, sonra butun atanmis
    coinler icin AL/SAT kontrolu. Hem surekli modun (main) dongusu
    hem tek-seferlik modun (main_tek_seferlik -- GitHub Actions gibi
    bir zamanlayicidan her tetiklendiginde bir kez calisir) icinde
    AYNEN kullanilir -- iki modun DAVRANISI ayni kalsin diye tek yerde.

    ROTASYON, saati gelmemis olsa BILE, eger su an HICBIR coine
    strateji atanmamissa YINE DE denenir. NEDEN: "son_rotasyon" zaman
    damgasi, o rotasyonun SONUCU BOS cikmis olsa bile yazilir --
    yoksa (bir onceki calisma bos donduyse) sistem "vakti gelmedi"
    diyerek BOS durumu bir sonraki saate kadar hicbir sey yapmadan
    tasir, kendi kendini asla duzeltemez. Bos bir atama zaten
    "izlenecek hicbir sey yok" demek oldugu icin, zamanindan once
    tekrar denemenin bir sakincasi yok.
    """
    atama_yok = not (durum or {}).get("pozisyon_stratejileri")
    if rotasyon_zamani_mi(durum, a) or atama_yok:
        durum = rotasyonu_uygula(portfoy, durum, depo, a)

    atamalar = (durum or {}).get("pozisyon_stratejileri", {})
    if not atamalar:
        print("[!] Henuz coin/strateji ataması yok.")
        return durum

    islem_oldu = False
    for sembol, strateji_isim in list(atamalar.items()):
        sonuc = tek_coin_kontrolu(portfoy, sembol, strateji_isim, depo, a)
        if sonuc:
            islem_oldu = True

    if islem_oldu:
        portfoy.kaydet()

    fiyatlar = _portfoy_fiyatlari(portfoy, depo)
    saat = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{saat}] {len(portfoy.pozisyonlar)}/{a['maks_pozisyon']} pozisyon acik  "
          f"toplam={portfoy.toplam_deger(fiyatlar):,.2f} USDT "
          f"({portfoy.kar_yuzdesi(fiyatlar):+.2f}%)")
    return durum


def _canli_veriye_baglan():
    print("[i] Canli piyasa verisine baglaniliyor (ilk dolum birkac saniye surer)...")
    depo = cv.piyasa()
    for _ in range(30):
        if depo.durum.get("ilk_dolum"):
            break
        time.sleep(1)
    if not depo.durum.get("ilk_dolum"):
        # BASARISIZ oldugunu ACIKCA yazdiriyoruz -- aksi halde
        # sembol_sayisi=0 ile sessizce devam edip evreni_sec BOS
        # doner, hicbir islem yapilmaz ve loglarda NEDEN bulunamaz.
        # Bazi borsalar (ozellikle Binance) bulut saglayici IP
        # araliklarini (AWS/GCP/Azure -- GitHub Actions da Azure
        # kullanir) engelleyebilir; hata mesaji genelde bunu gosterir.
        print(f"[!] ILK DOLUM BASARISIZ OLDU -- depo.durum: {depo.durum}")
    print(f"[i] Baglandi -- {depo.durum.get('sembol_sayisi', 0)} coin izleniyor.")
    return depo


def main():
    """
    SUREKLI mod: bilgisayarınız acikken calistirmak icin
    (calistir_sanal_trader.bat). Ctrl+C'ye kadar sonsuz donuyor.
    """
    a = AYARLAR
    CIKTI_KLASORU.mkdir(parents=True, exist_ok=True)
    _baslik_yaz(a)

    depo = _canli_veriye_baglan()
    portfoy = Portfoy.yukle(a["baslangic_bakiye"])
    durum = durumu_yukle()

    try:
        while True:
            try:
                durum = bir_dongu(portfoy, durum, depo, a)
            except ccxt.NetworkError as e:
                print(f"[!] Internet/borsa baglanti sorunu: {str(e)[:100]}")
            except ccxt.ExchangeError as e:
                print(f"[!] Borsa hata verdi: {str(e)[:150]}")

            print(f"   ... {a['dongu_saniye']} saniye bekleniyor (durdurmak icin Ctrl+C)")
            time.sleep(a["dongu_saniye"])

    except KeyboardInterrupt:
        print("\n\n[i] Sanal trader durduruldu. Portfoy kaydedildi.")
        portfoy.kaydet()


def main_tek_seferlik():
    """
    TEK SEFERLIK mod: bir dis zamanlayici (GitHub Actions gibi) bunu
    periyodik olarak (ornegin saatte bir) tetikler; bu fonksiyon TEK
    bir bir_dongu() calistirir ve CIKAR -- sonsuz donmez. Boylece
    bilgisayarınız kapali olsa bile, zamanlayici bu scripti calistirdigi
    surece sistem 7/24 islemeye devam eder.
    """
    a = AYARLAR
    CIKTI_KLASORU.mkdir(parents=True, exist_ok=True)
    _baslik_yaz(a)
    print("  MOD: tek seferlik (dis zamanlayicidan tetiklendi)")
    print("=" * 70)

    depo = _canli_veriye_baglan()
    portfoy = Portfoy.yukle(a["baslangic_bakiye"])
    durum = durumu_yukle()

    try:
        bir_dongu(portfoy, durum, depo, a)
    except ccxt.NetworkError as e:
        print(f"[!] Internet/borsa baglanti sorunu: {str(e)[:100]}")
    except ccxt.ExchangeError as e:
        print(f"[!] Borsa hata verdi: {str(e)[:150]}")

    print("[i] Tek seferlik calisma tamamlandi.")


if __name__ == "__main__":
    if "--once" in sys.argv or "--tek-seferlik" in sys.argv:
        main_tek_seferlik()
    else:
        main()
