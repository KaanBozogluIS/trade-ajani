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
import trade_ajani_stratejileri as taj
from dogrulama import simule_et
from strateji_desenleri import DESEN_STRATEJILERI
from strateji_desenleri import isinma_suresi as desen_isinma_suresi
from stratejiler import STRATEJILER, atr
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


# Bu dongude olan islemler -- dongu SONUNDA tek bir Telegram mesajinda
# toplu gonderilir (her islem icin ayri mesaj = gereksiz bildirim yagmuru).
_olaylar = []


def _telegram_gonder(metin):
    """
    TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID ortam degiskenleri varsa (GitHub
    Secrets ya da sunucudaki .env) mesaj gonderir; yoksa sessizce atlar
    (yerel denemelerde bildirim gitmesin). Duz metin -- Markdown ozel
    karakterleri (sembol/strateji adlarindaki _ gibi) mesaji bozamasin.
    """
    token, sohbet = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not sohbet:
        return False
    try:
        import requests
        y = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": sohbet, "text": metin,
                                "disable_web_page_preview": True}, timeout=15)
        if y.status_code != 200:
            print(f"[telegram] gonderilemedi ({y.status_code}): {y.text[:200]}")
        return y.status_code == 200
    except Exception as e:
        print(f"[telegram] hata: {e}")
        return False


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

    # KALDIRAC (2026-09-12'de eklendi): YENI acilan pozisyonlar artik SPOT
    # degil, VADELI (kaldiracli) -- "sanal", gercek para/API anahtari yine
    # YOK, sadece kar/zarar matematigi buyutuluyor. Kaldirac, HER pozisyon
    # icin ayni degil -- ATR'a (oynakliga) gore DINAMIK hesaplanir (bkz.
    # _kaldirac_hesapla): oynakligi dusuk coinlerde min_kaldirac'a, oynakligi
    # yuksek coinlerde maks_kaldirac'a YAKLASMAZ, TAM TERSI -- risk_per_
    # islem_yuzde sabit tutulmaya calisilir (dar/ongorulen stop -> yuksek
    # kaldirac, genis/ongorulen stop -> dusuk kaldirac), HER ZAMAN
    # [min_kaldirac, maks_kaldirac] araligina sikistirilir.
    #
    # ONEMLI SINIRLAMA (durustluk notu): stratejilerin hicbiri (kaan-trade'in
    # kendi 16+4'u de, aktarilan Trade-ajani stratejileri de) gercek bir
    # stop-loss seviyesi DONDURMUYOR (sinyal serisi sadece -1/0/1) -- bu
    # yuzden "stop mesafesi" gercek stratejinin kendi stop'u DEGIL, 2xATR'lik
    # GENEL bir varsayimdir (coğu strateji icin kaba ama makul bir vekil).
    "min_kaldirac": 5.0,
    "maks_kaldirac": 10.0,
    "risk_per_islem_yuzde": 12.0,   # kaldirac = risk_per_islem_yuzde / (stop_atr_kati*ATR/fiyat*100), sonra klemplenir
    "stop_atr_kati": 2.0,           # varsayilan stop mesafesi ~= bu kati * ATR(14)

    # MAKSIMUM TUTMA SURESI (2026-10-04): bir pozisyon bu kadar gunden uzun
    # aciksa, stratejisinin sinyalinden BAGIMSIZ olarak kapatilir. NEDEN:
    # bazi trend stratejileri (or. "SMA trend 200", "Dusuk oynaklik") cikis
    # sinyalini haftalarca vermiyor -- 8 slotun bir kismi aylarca kilitli
    # kaliyor ve nakit ~0'a indiginde bot YENI hicbir firsati
    # degerlendiremiyor (Eylul 2026'da tam olarak bu oldu). Kapanan coin,
    # bir sonraki kontrolde rotasyonun GUNCEL stratejisiyle yeniden
    # degerlendirilir -- sinyal hala lehteyse TAZE kaldiracla yeniden acilir.
    "maks_tutma_gun": 14,
}

# Zaman dilimine gore bir mumun kac saat surdugu -- "gun" cinsinden
# ayarlari (geriye_donuk_pencere_gun gibi) dogru sayida MUMA cevirmek icin.
_SAAT_PER_MUM = {"1m": 1 / 60, "5m": 5 / 60, "15m": 15 / 60, "30m": 0.5,
                 "1h": 1, "4h": 4, "1d": 24}


def _gun_to_mum(gun, zaman_dilimi):
    saat = _SAAT_PER_MUM.get(zaman_dilimi, 24)
    return int(gun * 24 / saat)


def _kaldirac_hesapla(df, a):
    """
    YENI acilan bir pozisyon icin kaldiraci ATR'a (oynakliga) gore
    DINAMIK hesaplar, HER ZAMAN [min_kaldirac, maks_kaldirac] icine
    sikistirir (bkz. AYARLAR'daki "KALDIRAC" notu -- bu proje stop
    seviyesini stratejiden degil, 2xATR varsayimindan turetir).
    """
    seri = atr(df, 14)
    if seri is None or len(seri) == 0:
        return a["min_kaldirac"]
    a_deger = float(seri.iloc[-1])
    fiyat = float(df["kapanis"].iloc[-1])
    if pd.isna(a_deger) or a_deger <= 0 or fiyat <= 0:
        return a["min_kaldirac"]
    stop_mesafe_yuzde = (a["stop_atr_kati"] * a_deger / fiyat) * 100
    if stop_mesafe_yuzde <= 0:
        return a["maks_kaldirac"]
    kaldirac = a["risk_per_islem_yuzde"] / stop_mesafe_yuzde
    return max(a["min_kaldirac"], min(a["maks_kaldirac"], kaldirac))


def _likidasyon_fiyati(pozisyon):
    """
    Kaldiracli bir pozisyonun MARJININ TAMAMEN tukendigi fiyat seviyesi
    (basitlestirilmis -- gercek borsalardaki bakim marjini tamponu yok,
    bkz. AYARLAR'daki "likidasyon_bakim_payi"). Kaldiracsiz (spot, yani
    kaldirac<=1.0 ya da alan hic yok) pozisyonlar icin None doner --
    spot pozisyonlar HICBIR ZAMAN likide olmaz.
    """
    kaldirac = pozisyon.get("kaldirac", 1.0)
    if not kaldirac or kaldirac <= 1.0:
        return None
    giris = pozisyon.get("giris_fiyat")
    if not giris:
        return None
    if pozisyon.get("yon") == "SHORT":
        return giris * (1 + 1.0 / kaldirac)
    return giris * (1 - 1.0 / kaldirac)


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
# Her calismanin SAGLIK raporu: mum verisi alinabildi mi, kac coin icin
# veri alinamadi. Panel bunu gosterir; GitHub Actions is akisi da buna
# bakip veri yoksa calismayi BASARISIZ (kirmizi) isaretler -- boylece
# "her sey yesil ama bot aslinda kor" durumu bir daha fark edilmeden
# gunlerce surmez.
SAGLIK_DOSYASI = CIKTI_KLASORU / "saglik.json"
_saglik = {"mum_verisi_ok": True, "hata": None, "verisiz_coin": []}


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

    def ac(self, sembol, strateji, fiyat, tutar, ucret_yuzde, yon="LONG", kaldirac=1.0):
        """
        <tutar> USDT'lik nakitle sembolde pozisyon acar (sanal).

        <yon>: "LONG" (fiyat yukselirse kazanc) ya da "SHORT" (fiyat
        duserse kazanc -- Trade-ajani'nin orijinal LONG+SHORT strateji
        mantigi buraya tasinirken eklendi).

        <kaldirac>: 1.0 (varsayilan) = SPOT, davranis BIREBIR eskisi gibi
        (miktar = tutar/fiyat, tam notional). >1.0 ise <tutar> artik
        MARJIN'dir -- gercekte kontrol edilen notional = tutar*kaldirac
        (miktar buyur), ama nakitten yine SADECE <tutar> (marjin)
        dusulur. Bkz. _kaldirac_hesapla (ATR'a gore dinamik, [5,10]
        araligina sikistirilir) ve kapat()'taki likidasyon mantigi.
        """
        if tutar < 1 or tutar > self.nakit:
            return None
        kaldirac = kaldirac or 1.0
        ucret = tutar * kaldirac * ucret_yuzde / 100
        miktar = (tutar * kaldirac - ucret) / fiyat
        self.nakit -= tutar
        self.pozisyonlar[sembol] = {
            "miktar": miktar, "strateji": strateji, "giris_fiyat": fiyat,
            "giris_zamani": datetime.now(timezone.utc).isoformat(),
            "maliyet": tutar,  # nakitten cikan MARJIN (kaldirac=1'de "tam tutar" ile ayni) -- kapat()'ta kar/zarar buna gore hesaplanir
            "yon": yon,
            "kaldirac": kaldirac,
        }
        self.islem_sayisi += 1
        return {"miktar": miktar, "tutar": tutar, "ucret": ucret}

    def kapat(self, sembol, fiyat, ucret_yuzde):
        """
        Elimizdeki <sembol> pozisyonunun TAMAMINI kapatir (sanal) ve bu
        ISLEMIN kar/zararini hesaplar -- "hangi strateji ne zaman
        kazandirdi/kaybettirdi" sorusuna cevap vermek icin (bkz.
        islem_kaydet, panelde "Strateji performansı" tablosu).

        YON'A GORE HESAP: eski (SHORT'tan once yazilmis) pozisyonlarda
        "yon" alani YOK -- .get(..., "LONG") ile geriye uyumlu (mevcut
        acik pozisyonlar LONG olarak yorumlanmaya devam eder, davranis
        DEGISMEZ). SHORT icin kar/zarar formulu Trade-ajani'nin
        core/backtest.py'sindeki "pos_dir * (exit/entry - 1)" ile AYNI
        matematik (pos_dir=-1) -- fiyat DUSTUKCE kazanc.

        KALDIRAC (kaldirac>1.0): kar/zarar MARJIN (<maliyet>) uzerinden
        kaldirac KATI buyutulur -- LIKIDASYON: kar/zarar marjinin
        TAMAMINI goturursen (ya da asarsa) <net> SIFIRDA sabitlenir,
        nakit NEGATIFE dusmez (gercek vadeli islemlerdeki "marjin kaybi"
        ile ayni ilke). kaldirac<=1.0 (spot -- eski pozisyonlarda alan
        hic YOK) icin asagidaki iki dal (LONG/SHORT) BIREBIR eskisi gibi,
        DEGISMEDI.
        """
        pozisyon = self.pozisyonlar.get(sembol)
        if not pozisyon:
            return None
        miktar = pozisyon["miktar"]
        yon = pozisyon.get("yon", "LONG")
        kaldirac = pozisyon.get("kaldirac", 1.0) or 1.0
        giris_fiyat = pozisyon.get("giris_fiyat", fiyat)
        maliyet = pozisyon.get("maliyet") or (miktar * giris_fiyat)

        brut_islem = miktar * fiyat  # kapanista el degistiren notional -- ucret bunun uzerinden alinir (yon farketmez)
        ucret = brut_islem * ucret_yuzde / 100

        if kaldirac > 1.0:
            # Giris komisyonu (ac()'ta notional uzerinden alindi) burada da
            # dusulur -- 2026-10-04'e kadar UNUTULUYORDU: 10x'te islem basina
            # marjinin ~%1'i kadar fazla kar gorunuyordu.
            giris_ucreti = maliyet * kaldirac * ucret_yuzde / 100
            if yon == "SHORT":
                kar_zarar = maliyet * kaldirac * (giris_fiyat - fiyat) / giris_fiyat if giris_fiyat else 0.0
            else:
                kar_zarar = maliyet * kaldirac * (fiyat / giris_fiyat - 1) if giris_fiyat else 0.0
            kar_zarar -= ucret + giris_ucreti
            net = maliyet + kar_zarar
            if net < 0:
                # LIKIDASYON: marjinin tamami gitti, daha fazla kaybedilemez.
                kar_zarar = -maliyet
                net = 0.0
        elif yon == "SHORT":
            kar_zarar = maliyet * (giris_fiyat - fiyat) / giris_fiyat - ucret if giris_fiyat else -ucret
            net = maliyet + kar_zarar
        else:
            net = brut_islem - ucret
            kar_zarar = net - maliyet

        self.nakit += net
        del self.pozisyonlar[sembol]
        self.islem_sayisi += 1

        kar_zarar_yuzde = (kar_zarar / maliyet * 100) if maliyet else 0.0
        return {"miktar": miktar, "tutar": net, "ucret": ucret,
               "kar_zarar": kar_zarar, "kar_zarar_yuzde": kar_zarar_yuzde}

    def toplam_deger(self, fiyatlar):
        """
        fiyatlar: {sembol: fiyat} -- elimizdeki her pozisyon icin gerekir.

        SHORT pozisyonlar icin, o an kapatilsa ne kadar nakit donecegi
        (maliyet +/- gerceklesmemis kar/zarar) hesaba katilir -- LONG
        icin davranis (miktar * fiyat) DEGISMEDI. Kaldiracli pozisyonlar
        icin kar/zarar marjin uzerinden kaldirac kati buyutulur ve deger
        SIFIRIN ALTINA (marjin kaybindan fazla) dusurulmez -- kapat()'taki
        likidasyon mantigiyla tutarli.
        """
        deger = self.nakit
        for sembol, pozisyon in self.pozisyonlar.items():
            fiyat = fiyatlar.get(sembol)
            if not fiyat:
                continue
            yon = pozisyon.get("yon", "LONG")
            kaldirac = pozisyon.get("kaldirac", 1.0) or 1.0
            giris_fiyat = pozisyon.get("giris_fiyat", fiyat)
            maliyet = pozisyon.get("maliyet") or (pozisyon["miktar"] * giris_fiyat)

            if kaldirac > 1.0:
                if yon == "SHORT":
                    kar_zarar = maliyet * kaldirac * (giris_fiyat - fiyat) / giris_fiyat if giris_fiyat else 0.0
                else:
                    kar_zarar = maliyet * kaldirac * (fiyat / giris_fiyat - 1) if giris_fiyat else 0.0
                kar_zarar -= maliyet * kaldirac * AYARLAR["islem_ucreti_yuzde"] / 100  # odenmis giris komisyonu
                deger += max(0.0, maliyet + kar_zarar)
            elif yon == "SHORT":
                kar_zarar = maliyet * (giris_fiyat - fiyat) / giris_fiyat if giris_fiyat else 0.0
                deger += maliyet + kar_zarar
            else:
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

    trade_ajani_stratejileri.STRATEJILER (Trade-ajani'ndan aktarilan, 2026-
    09-12'de SHORT destegi geri getirilen 4 strateji) de listeye DAHIL --
    aksi halde motor SHORT pozisyon acabilir hale gelse bile, rotasyonun
    secebildigi HICBIR strateji -1.0 uretmedigi icin SHORT hicbir zaman
    fiilen tetiklenmezdi (mevcut 16 klasik + 4 desen strateji, tasarim
    geregi LONG-only kalmaya devam ediyor -- bkz. dosya basindaki notlar).
    """
    liste = []
    for isim, fn, params in STRATEJILER:
        if isim in ("al ve tut", "rastgele"):
            continue
        liste.append((isim, fn, params, klasik_isinma_suresi(isim, params)))
    for isim, fn, params in DESEN_STRATEJILERI:
        liste.append((isim, fn, params, desen_isinma_suresi(isim, params)))
    for isim, fn, params in taj.STRATEJILER:
        liste.append((isim, fn, params, taj.isinma_suresi(isim, params)))
    return liste


_STRATEJILER_TUMU = _tum_stratejiler()
_STRATEJI_SOZLUGU = {isim: (fn, params, isinma) for isim, fn, params, isinma in _STRATEJILER_TUMU}
_MAKS_ISINMA = max(isinma for *_, isinma in _STRATEJILER_TUMU)


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
        # Coin basina TEK istek: eskiden her strateji icin ayri cekiliyordu
        # (40 coin x 23 strateji = 920 istek); her strateji kendi
        # ihtiyaci kadarini bu tek veriden kesip alir -- sonuc ayni.
        tum_df = vk.mum_verisi(coin, a["zaman_dilimi"], _MAKS_ISINMA + pencere_mum + 15)
        if tum_df is None:
            _saglik["verisiz_coin"].append(coin)
            continue
        # Puanlama CANLI ISLEMLE AYNI kaldiracla (ve likidasyon riskiyle)
        # yapilir -- spot puanlama, 10x'te likide olacak stratejileri odullendirirdi.
        kaldirac = _kaldirac_hesapla(tum_df, a)
        for isim, fn, params, isinma in _STRATEJILER_TUMU:
            df = tum_df.tail(isinma + pencere_mum + 15).reset_index(drop=True)
            if len(df) < isinma + 30:
                continue
            try:
                poz = fn(df, **params)
            except Exception:
                continue
            sonuc = simule_et(df, poz, a, baslangic=isinma, kaldirac=kaldirac)
            if sonuc is None:
                continue
            sonuclar.append({"isim": isim, "getiri": sonuc["getiri"],
                             "dusus": sonuc["dusus"], "piyasada": sonuc["piyasada"],
                             "likidasyon": sonuc.get("likidasyon", 0)})

        if not sonuclar:
            continue
        sonuclar.sort(key=lambda r: r["getiri"], reverse=True)
        en_iyi = sonuclar[0]
        atamalar[coin] = {"strateji": en_iyi["isim"], "getiri": en_iyi["getiri"],
                          "dusus": en_iyi["dusus"], "piyasada": en_iyi["piyasada"]}
        gunluk_satirlari.append({
            "coin": coin, "en_iyi_5": f"[{kaldirac:.1f}x] " + " | ".join(
                f"{r['isim']}:{r['getiri']:+.1f}%" + (f"(L{r['likidasyon']})" if r["likidasyon"] else "")
                for r in sonuclar[:5]),
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


def _saglik_kaydet():
    _atomik_yaz(SAGLIK_DOSYASI, json.dumps({
        **_saglik, "zaman": datetime.now(timezone.utc).isoformat(),
    }, indent=2, ensure_ascii=False))


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
            # ROTASYON ATLANIR: veri yokken devam etmek, 40 coinin HEPSINI
            # "atanamadi" sayip mevcut atamalari silerdi ve son_rotasyon'u
            # guncelleyerek bir sonraki denemeyi de geciktirirdi
            # (2026-09-26 - 10-04 arasi tam olarak bu oldu: bot 8 gun
            # boyunca sessizce kordu). durum AYNEN korunur, bir sonraki
            # calismada tekrar denenir.
            print(f"[!] TEYIT BASARISIZ: {evren[0]} icin mum verisi alinamadi "
                  f"-- sebep: {vk.son_mum_hatasi}. Rotasyon ATLANIYOR, mevcut "
                  "atamalar korunuyor.")
            _saglik["mum_verisi_ok"] = False
            _saglik["hata"] = vk.son_mum_hatasi
            return durum
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

_ISLEM_KOLONLARI = [
    "tarih", "islem", "strateji", "sembol", "fiyat", "miktar",
    "tutar", "ucret", "kar_zarar", "kar_zarar_yuzde", "nakit",
    "portfoy_degeri", "sebep", "kaldirac",
]


def _islem_dosyasi_semaya_uydur():
    """
    islemler.csv'ye "kaldirac" sutunu SONRADAN (2026-09-12) eklendi.
    Dosya zaten varsa VE eski (bu sutunsuz) bir basligi varsa, TUM
    dosyayi okuyup basligi + her eski satira "kaldirac"=1.0 (o donemde
    HER ISLEM spot'tu, bu dogru bir varsayimdan cok bir GERCEK) ekleyerek
    yeniden yazar. Boylece DictWriter'in yeni sutunla YENI satir eklemesi,
    eski (sutunsuz) baslikla COLUMN SAYISI UYUSMAZLIGINA yol acmaz --
    "yarim/bozuk dosya" riskine karsi _atomik_yaz ile TEK adimda yazilir.
    """
    if not ISLEM_DOSYASI.exists():
        return
    with ISLEM_DOSYASI.open("r", newline="", encoding="utf-8-sig") as f:
        okuyucu = csv.reader(f)
        satirlar = list(okuyucu)
    if not satirlar or "kaldirac" in satirlar[0]:
        return
    satirlar[0] = satirlar[0] + ["kaldirac"]
    for satir in satirlar[1:]:
        satir.append("1.0")
    import io
    tampon = io.StringIO()
    csv.writer(tampon).writerows(satirlar)
    _atomik_yaz(ISLEM_DOSYASI, tampon.getvalue())
    print(f"[i] {ISLEM_DOSYASI.name} semasi guncellendi: 'kaldirac' sutunu eklendi "
          f"(eski {len(satirlar) - 1} satira 1.0/spot atandi).")


def islem_kaydet(saat, islem, strateji, sembol, fiyat, sonuc, portfoy, fiyatlar, sebep, kaldirac=1.0):
    """
    "kar_zarar"/"kar_zarar_yuzde" sutunlari SADECE SAT satirlarinda
    doludur (Portfoy.kapat()'in dondurdugu sonuc'ta bulunur) -- AL
    satirlarinda bos kalir, cunku bir alim ANINDA henuz kar/zarar
    yoktur. Boylece panelde "hangi strateji, hangi coin'de, ne zaman,
    kar mi zarar mi etti" dogrudan bu tablodan okunabilir.

    <kaldirac>: pozisyonun kaldiraci (1.0 = spot) -- panelin geçmiş
    portföy eğrisini (_sanal_trader_egri_verisi) doğru yeniden
    kurabilmesi için AL/KISA_AC satırlarına yazılır.
    """
    _islem_dosyasi_semaya_uydur()
    CIKTI_KLASORU.mkdir(parents=True, exist_ok=True)
    yeni_dosya = not ISLEM_DOSYASI.exists()
    with ISLEM_DOSYASI.open("a", newline="", encoding="utf-8-sig") as f:
        yazici = csv.DictWriter(f, fieldnames=_ISLEM_KOLONLARI)
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
            "kaldirac": round(kaldirac, 3) if kaldirac else 1.0,
        })

    simge = {"AL": "🟢 LONG AC", "KISA_AC": "🔴 SHORT AC", "SAT": "⚪ LONG KAPAT",
             "KISA_KAPAT": "⚪ SHORT KAPAT", "LIKIDASYON": "💥 LIKIDASYON"}.get(islem, islem)
    satir = f"{simge} {sembol} @ {fiyat:.6g}"
    if islem in ("AL", "KISA_AC"):
        satir += f" · {kaldirac:.1f}x" if kaldirac and kaldirac > 1 else " · spot"
        satir += f" · marjin {sonuc['tutar']:,.0f}$"
    elif "kar_zarar" in sonuc:
        satir += f" · K/Z {sonuc['kar_zarar']:+,.2f}$ ({sonuc['kar_zarar_yuzde']:+.1f}%)"
    if sebep == "sure_doldu":
        satir += f" · {AYARLAR['maks_tutma_gun']} gun doldu"
    _olaylar.append(f"{satir} · [{strateji}]")


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

    gerekli = isinma + 60
    giris_zamani = None
    if tutuluyor_mu and portfoy.pozisyonlar[sembol].get("giris_zamani"):
        # Likidasyon kontrolu GIRISTEN BERI tum mumlari kapsamali (asagiya
        # bkz.) -- uzun suredir acik bir pozisyon icin daha fazla mum gerekir.
        giris_zamani = pd.Timestamp(portfoy.pozisyonlar[sembol]["giris_zamani"])
        gecen_saat = (pd.Timestamp.now(tz="UTC") - giris_zamani).total_seconds() / 3600
        gerekli = max(gerekli, min(int(gecen_saat / _SAAT_PER_MUM.get(a["zaman_dilimi"], 1)) + 3, 2000))

    df = vk.mum_verisi(sembol, a["zaman_dilimi"], gerekli)
    if df is None or len(df) < isinma + 30:
        _saglik["verisiz_coin"].append(sembol)
        return None

    saat = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # LIKIDASYON KONTROLU (kaldiracli pozisyonlar icin): GIRISTEN BERI
    # tum mumlarin ic fiyat araligina (yuksek/dusuk) bakilir -- sadece son
    # muma degil. NEDEN: GitHub'in zamanlayicisi "saatte bir" isi olcumlere
    # gore 8 saate kadar geciktirebiliyor; sadece son muma bakmak, aradaki
    # saatlerde likidasyon seviyesine degip geri donen bir hareketi
    # KACIRIRDI (gercek bir borsada pozisyon o an kapanmis olurdu). Spot
    # (kaldiracsiz) pozisyonlarda _likidasyon_fiyati None doner, blok
    # hicbir sey yapmaz.
    if tutuluyor_mu:
        acik_poz = portfoy.pozisyonlar[sembol]
        likit_fiyat = _likidasyon_fiyati(acik_poz)
        if likit_fiyat is not None:
            mum_suresi = pd.Timedelta(hours=_SAAT_PER_MUM.get(a["zaman_dilimi"], 1))
            donem = df[df["zaman"] + mum_suresi > giris_zamani] if giris_zamani is not None else df.tail(1)
            if donem.empty:
                donem = df.tail(1)
            son_yuksek = float(donem["yuksek"].max())
            son_dusuk = float(donem["dusuk"].min())
            likide_oldu = (acik_poz.get("yon", "LONG") == "LONG" and son_dusuk <= likit_fiyat) or \
                          (acik_poz.get("yon") == "SHORT" and son_yuksek >= likit_fiyat)
            if likide_oldu:
                acik_kaldirac = acik_poz.get("kaldirac", 1.0)
                fiyatlar = _portfoy_fiyatlari(portfoy, depo, sembol, likit_fiyat)
                sonuc = portfoy.kapat(sembol, likit_fiyat, a["islem_ucreti_yuzde"])
                if sonuc:
                    islem_kaydet(saat, "LIKIDASYON", strateji_isim, sembol, likit_fiyat, sonuc,
                                portfoy, fiyatlar, "likidasyon", kaldirac=acik_kaldirac)
                    print(f"   >> LIKIDASYON: {sembol} @ {likit_fiyat:.6g}  "
                          f"(marjin kaybedildi, {acik_kaldirac:.1f}x)  [{strateji_isim}]")
                    return "LIKIDASYON"

    fiyat = float(df["kapanis"].iloc[-1])

    # MAKSIMUM TUTMA SURESI -- bkz. AYARLAR["maks_tutma_gun"].
    if tutuluyor_mu and giris_zamani is not None and a.get("maks_tutma_gun"):
        tutulan_gun = (pd.Timestamp.now(tz="UTC") - giris_zamani).total_seconds() / 86400
        if tutulan_gun >= a["maks_tutma_gun"]:
            acik_poz = portfoy.pozisyonlar[sembol]
            yon = acik_poz.get("yon", "LONG")
            kapanan_kaldirac = acik_poz.get("kaldirac", 1.0)
            fiyatlar = _portfoy_fiyatlari(portfoy, depo, sembol, fiyat)
            sonuc = portfoy.kapat(sembol, fiyat, a["islem_ucreti_yuzde"])
            if sonuc:
                etiket = "SAT" if yon == "LONG" else "KISA_KAPAT"
                islem_kaydet(saat, etiket, strateji_isim, sembol, fiyat, sonuc, portfoy,
                            fiyatlar, "sure_doldu", kaldirac=kapanan_kaldirac)
                print(f"   >> SURE DOLDU ({tutulan_gun:.0f} gun): {sembol} kapatildi  [{strateji_isim}]")
                return etiket

    try:
        poz = fn(df, **params)
    except Exception:
        return None
    son_sinyal = poz.iloc[-1]
    if pd.isna(son_sinyal):
        return None

    if son_sinyal == 1.0 and not tutuluyor_mu:
        bos_yer = portfoy.bos_pozisyon_yeri(a["maks_pozisyon"])
        if bos_yer <= 0:
            return None
        tutar = (portfoy.nakit * a["islem_orani"]) / bos_yer
        kaldirac = _kaldirac_hesapla(df, a)
        sonuc = portfoy.ac(sembol, strateji_isim, fiyat, tutar, a["islem_ucreti_yuzde"], yon="LONG", kaldirac=kaldirac)
        if sonuc:
            fiyatlar = _portfoy_fiyatlari(portfoy, depo, sembol, fiyat)
            islem_kaydet(saat, "AL", strateji_isim, sembol, fiyat, sonuc, portfoy,
                        fiyatlar, "sinyal", kaldirac=kaldirac)
            print(f"   >> SANAL ALIM: {sembol}  {sonuc['miktar']:.6f} "
                  f"({sonuc['tutar']:,.2f} USDT marjin, {kaldirac:.1f}x)  [{strateji_isim}]")
            return "AL"
    elif son_sinyal == -1.0 and not tutuluyor_mu:
        # SHORT: Trade-ajani'ndan tasinan stratejilerin orijinal (LONG+
        # SHORT) mantigi -1.0 uretebiliyor -- bkz. trade_ajani_stratejileri.py.
        bos_yer = portfoy.bos_pozisyon_yeri(a["maks_pozisyon"])
        if bos_yer <= 0:
            return None
        tutar = (portfoy.nakit * a["islem_orani"]) / bos_yer
        kaldirac = _kaldirac_hesapla(df, a)
        sonuc = portfoy.ac(sembol, strateji_isim, fiyat, tutar, a["islem_ucreti_yuzde"], yon="SHORT", kaldirac=kaldirac)
        if sonuc:
            fiyatlar = _portfoy_fiyatlari(portfoy, depo, sembol, fiyat)
            islem_kaydet(saat, "KISA_AC", strateji_isim, sembol, fiyat, sonuc, portfoy,
                        fiyatlar, "sinyal", kaldirac=kaldirac)
            print(f"   >> SANAL KISA (SHORT) ACILIS: {sembol}  {sonuc['miktar']:.6f} "
                  f"({sonuc['tutar']:,.2f} USDT marjin, {kaldirac:.1f}x)  [{strateji_isim}]")
            return "KISA_AC"
    elif son_sinyal == 0.0 and tutuluyor_mu:
        # ONCE fiyatlari topla (pozisyon hala listede), SONRA kapat --
        # aksi halde kapatilan pozisyon toplam degerden eksik sayilirdi.
        yon = portfoy.pozisyonlar[sembol].get("yon", "LONG")
        kapanan_kaldirac = portfoy.pozisyonlar[sembol].get("kaldirac", 1.0)
        fiyatlar = _portfoy_fiyatlari(portfoy, depo, sembol, fiyat)
        sonuc = portfoy.kapat(sembol, fiyat, a["islem_ucreti_yuzde"])
        if sonuc:
            etiket = "SAT" if yon == "LONG" else "KISA_KAPAT"
            islem_kaydet(saat, etiket, strateji_isim, sembol, fiyat, sonuc, portfoy,
                        fiyatlar, "sinyal", kaldirac=kapanan_kaldirac)
            aciklama = "SATIS" if yon == "LONG" else "KISA KAPATMA"
            print(f"   >> SANAL {aciklama}: {sembol}  {sonuc['miktar']:.6f} "
                  f"({sonuc['tutar']:,.2f} USDT)  [{strateji_isim}]")
            return etiket
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
    _saglik.update({"mum_verisi_ok": True, "hata": None, "verisiz_coin": []})

    atama_yok = not (durum or {}).get("pozisyon_stratejileri")
    if rotasyon_zamani_mi(durum, a) or atama_yok:
        durum = rotasyonu_uygula(portfoy, durum, depo, a)

    atamalar = (durum or {}).get("pozisyon_stratejileri", {})
    if not atamalar:
        print("[!] Henuz coin/strateji ataması yok.")
        _dongu_sonu(portfoy, depo, a, 0)
        return durum

    islem_oldu = False
    for sembol, strateji_isim in list(atamalar.items()):
        sonuc = tek_coin_kontrolu(portfoy, sembol, strateji_isim, depo, a)
        if sonuc:
            islem_oldu = True

    if islem_oldu:
        portfoy.kaydet()

    _dongu_sonu(portfoy, depo, a, len(atamalar))
    return durum


def _dongu_sonu(portfoy, depo, a, atama_sayisi):
    """
    Her dongunun sonu: saglik raporunu yaz, saglik DURUMU DEGISTIYSE
    (saglikli <-> veri yok) Telegram'a uyari at, bu dongudeki islemleri
    TEK mesajda gonder, ozeti yazdir.
    """
    verisiz = sorted(set(_saglik["verisiz_coin"]))
    _saglik["verisiz_coin"] = verisiz
    if verisiz:
        print(f"[!] {len(verisiz)} coin icin mum verisi alinamadi "
              f"(sinyal/likidasyon KONTROL EDILEMEDI): {', '.join(verisiz[:10])} "
              f"-- son hata: {vk.son_mum_hatasi}")
        if len(verisiz) * 2 > max(atama_sayisi, 1):
            _saglik["mum_verisi_ok"] = False
            _saglik["hata"] = _saglik["hata"] or vk.son_mum_hatasi

    try:
        onceki_ok = json.loads(SAGLIK_DOSYASI.read_text(encoding="utf-8")).get("mum_verisi_ok", True)
    except Exception:
        onceki_ok = True
    _saglik_kaydet()
    if onceki_ok and not _saglik["mum_verisi_ok"]:
        _telegram_gonder("⚠️ SANAL TRADER VERİ ALAMIYOR\nRotasyon, çıkış sinyalleri ve "
                         "likidasyon kontrolü yapılamıyor; pozisyonlar donmuş durumda.\n"
                         f"Sebep: {_saglik['hata']}")
    elif not onceki_ok and _saglik["mum_verisi_ok"]:
        _telegram_gonder("✅ Sanal Trader yeniden veri alabiliyor, kontroller normale döndü.")

    fiyatlar = _portfoy_fiyatlari(portfoy, depo)
    toplam = portfoy.toplam_deger(fiyatlar)
    kar = portfoy.kar_yuzdesi(fiyatlar)
    saat = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{saat}] {len(portfoy.pozisyonlar)}/{a['maks_pozisyon']} pozisyon acik  "
          f"toplam={toplam:,.2f} USDT ({kar:+.2f}%)")

    if _olaylar:
        _telegram_gonder(
            "📒 Sanal Trader — SANAL para, gerçek işlem DEĞİL\n\n" + "\n".join(_olaylar)
            + f"\n\nPortföy: {toplam:,.0f}$ ({kar:+.1f}%) · "
              f"{len(portfoy.pozisyonlar)}/{a['maks_pozisyon']} pozisyon · nakit {portfoy.nakit:,.0f}$")
        _olaylar.clear()


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
