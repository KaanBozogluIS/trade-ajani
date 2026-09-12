r"""
ANALIZ BOTU
===========

Piyasada YAYGIN OLARAK IZLENEN teknik durumlari tarar ve HAM HALDE
bildirir: "destek/direnc seviyesine yaklasti", "RSI'da uyumsuzluk var",
"hacimde para girisi isaretleri var" gibi.

BU BIR TAVSIYE MOTORU DEGILDIR.

    - Hicbir fonksiyon "AL", "SAT", "simdi", "girin", "cikin" demez.
    - Tek bir "genel sinyal" ya da puan URETILMEZ -- bilerek. Cunku
      boyle bir puan, "gozlemleri toplayip bir tavsiyeye cevirmek"
      olurdu. Kullanicinin istedigi tam olarak bunun tersi: HAM
      gozlemleri gormek, yorumu kendisi yapmak.
    - Her gozlem BAGIMSIZDIR ve BIRBIRIYLE CELISEBILIR. Fiyat
      dususurken hem "asagi yonlu" hem "yukari yonlu" okunan gozlemler
      AYNI ANDA gorunebilir -- bu bir hata degil, piyasanin dogasi.

DURUSTLUK NOTU: Onceki turlarda test ettigimiz gibi (bkz. README.md,
tarama.py), bu gozlemlerin DAYANDIGI standart gostergelerin (RSI, MACD,
hareketli ortalama...) hicbiri rastgele karar vermekten istatistiksel
olarak ayirt edilemedi. Burada olmalarinin sebebi "yaygin izlenmeleri",
yani PIYASA KATILIMCILARININ dikkate aldigi seyler olmalari -- "ise
yaradiklarinin kanitlanmis olmasi" degil.

KALIP: Her "gozlem_*" fonksiyonu bir liste dondurur. Her oge:
    {
        "kategori": str,   # "Trend", "Momentum", "Destek/Direnc" ...
        "baslik": str,     # kisa, tek cumlelik ozet
        "aciklama": str,   # ne gozlemlendigi + yaygin olarak nasil
                            # yorumlandigi (netral dilde, emir kipi yok)
        "yon": "yukari" | "asagi" | "notr",  # SADECE siniflandirma
                                              # etiketi -- talimat degil
    }
"""

import numpy as np
import pandas as pd

from desenler import fair_value_gap_bolgeleri, order_block_bolgeleri
from desenler import swing_noktalari as _swing_noktalari
from gostergeler import ema, macd, stokastik, vwap
from stratejiler import atr, rsi

# Birden fazla yerde (gozlem_volatilite VE tarama_adayi) kullanilan,
# gozlem basliklarini eslestirmek icin paylasilan sabitler.
_SIKISMA_BASLIK = "Volatilite sıkışması (TTM Squeeze)"
_HACIM_SINYAL_BASLIKLARI = {
    "Hacimde belirgin bir patlama var",
    "Fiyat durgunken hacim para girişi işareti veriyor",
}


# ============================================================
#  ORTAK YARDIMCILAR
# ============================================================

def _uyumsuzluk_bul(fiyat, gosterge, pencere=3, bakilan=60):
    """
    Fiyat ile bir gosterge (RSI, OBV gibi) arasinda "uyumsuzluk"
    (divergence) arar -- YAYGIN IZLENEN ama KANITLANMAMIS bir teknik
    analiz kavramidir.

    POZITIF (boga) UYUMSUZLUK: fiyat daha DUSUK bir dip yapiyor ama
    gosterge daha YUKSEK bir dip yapiyor. Yorum: dusus ivmesi
    zayifliyor olabilir -- fiyatin kendisi bunu HENUZ yansitmiyor.
    Kullanicinin ornegindeki tam olarak budur: "piyasa dusuyor ama
    grafikte gormedigim bir sey donusu isaret ediyor olabilir."

    NEGATIF (ayi) UYUMSUZLUK: fiyat daha YUKSEK bir tepe yapiyor ama
    gosterge daha DUSUK bir tepe yapiyor. Yorum: yukselis ivmesi
    zayifliyor olabilir.

    ONEMLI SINIRLAMA: Bu otomatik tespit gurultuye acik. Bulunan her
    uyumsuzluk "kesin donus" demek DEGILDIR -- sadece "yaygin izlenen
    bir durum su an mevcut" demektir.
    """
    n = len(fiyat)
    baslangic = max(0, n - bakilan)
    f = list(fiyat[baslangic:])
    g = list(gosterge[baslangic:])

    tepe_idx, dip_idx = _swing_noktalari(f, pencere)
    sonuc = {"boga": False, "ayi": False}

    if len(dip_idx) >= 2:
        i1, i2 = dip_idx[-2], dip_idx[-1]
        if not (pd.isna(g[i1]) or pd.isna(g[i2])):
            if f[i2] < f[i1] and g[i2] > g[i1]:
                sonuc["boga"] = True

    if len(tepe_idx) >= 2:
        i1, i2 = tepe_idx[-2], tepe_idx[-1]
        if not (pd.isna(g[i1]) or pd.isna(g[i2])):
            if f[i2] > f[i1] and g[i2] < g[i1]:
                sonuc["ayi"] = True

    return sonuc


def _obv(df):
    """
    OBV (On Balance Volume) -- "dengeli hacim". Fiyat yukseldiginde o
    gunun hacmini toplar, dustugunde cikarir; kumulatif bir toplamdir.

    FIKIR: hacim, fiyattan ONCE hareket edebilir. Fiyat yatay/dususte
    gorunurken OBV yukseliyorsa, bu "sessiz birikim" -- para girisinin
    grafikte henuz fiyata yansimamis olabilecegi -- olarak yorumlanir.
    Kullanicinin "alttan para girisi var" tarifine karsilik gelen
    gosterge budur.
    """
    yon = np.sign(df["kapanis"].diff().fillna(0))
    return (yon * df["hacim"]).cumsum()


def _son(seri):
    """Bir serinin son (NaN olmayan) degerini dondurur, yoksa None."""
    gecerli = seri.dropna()
    return float(gecerli.iloc[-1]) if len(gecerli) else None


def _keltner_kanali(df, periyot=20, katsayi=1.5):
    """
    Keltner Kanali: ustel ortalama +/- ATR'nin bir kati.

    Bollinger bantlarindan (standart sapma tabanli) farki, oynakligi
    ATR (ortalama gercek aralik) ile olcmesi -- tek bir buyuk fitilden
    Bollinger kadar etkilenmez, o yuzden daha "sakin" bir kiyas cizgisi
    verir. Sikisma tespitinde bunu Bollinger'a KIYASLA kullanmak (asagida
    "TTM Squeeze" yontemi), sadece Bollinger'in kendi gecmisine bakmaktan
    daha guvenilir sayilir -- iki farkli oynaklik olcusunu karsilastirir.
    """
    orta = ema(df["kapanis"], periyot)
    a = atr(df, periyot)
    return orta - katsayi * a, orta + katsayi * a


def _fiyat_yaz(x):
    """
    Fiyat seviyesini bilimsel gosterime (1.234e+04 gibi) DUSMEDEN yazar.
    "%.4g" bunun yerine kullanilirsa 4 basamaktan fazla haneli fiyatlarda
    (BTC gibi) bilimsel gosterime kayar -- uygulama.py'deki fiyat_yaz ile
    ayni mantik burada da ayri bir kopya olarak tutuluyor, cunku bu modul
    Streamlit'e bagimli olmamali (bkz. dosya basindaki not).
    """
    a = abs(x)
    if a >= 1:
        return f"{x:,.2f}"
    if a >= 0.01:
        return f"{x:,.4f}"
    return f"{x:,.8f}".rstrip("0")


# ============================================================
#  1) TREND
# ============================================================

def gozlem_trend(df):
    gozlemler = []
    kapanis = df["kapanis"]
    son_fiyat = float(kapanis.iloc[-1])

    for periyot in (50, 100, 200):
        if len(kapanis) < periyot:
            continue
        ort = float(kapanis.rolling(periyot).mean().iloc[-1])
        fark = (son_fiyat / ort - 1) * 100
        if abs(fark) < 0.5:
            gozlemler.append({
                "kategori": "Trend", "yon": "notr",
                "baslik": f"Fiyat {periyot} günlük ortalamayı test ediyor",
                "aciklama": f"Fiyat ({son_fiyat:,.2f}), {periyot} günlük "
                            f"ortalamaya çok yakın (%{abs(fark):.2f} mesafede). "
                            "Bu tür seviyeler piyasa katılımcıları tarafından "
                            "sık sık destek ya da direnç olarak izlenir.",
            })
        elif fark > 0:
            gozlemler.append({
                "kategori": "Trend", "yon": "yukari",
                "baslik": f"{periyot} günlük ortalamanın üzerinde",
                "aciklama": f"Fiyat, {periyot} günlük ortalamanın %{fark:.1f} "
                            "üzerinde seyrediyor. Uzun vadeli trend takipçileri "
                            "bu durumu genelde 'yükseliş eğilimi' olarak okur.",
            })
        else:
            gozlemler.append({
                "kategori": "Trend", "yon": "asagi",
                "baslik": f"{periyot} günlük ortalamanın altında",
                "aciklama": f"Fiyat, {periyot} günlük ortalamanın %{abs(fark):.1f} "
                            "altında seyrediyor. Uzun vadeli trend takipçileri "
                            "bu durumu genelde 'düşüş eğilimi' olarak okur.",
            })

    # Golden cross / death cross: SMA50, SMA200'u son birkac mumda kesti mi?
    if len(kapanis) >= 210:
        sma50 = kapanis.rolling(50).mean()
        sma200 = kapanis.rolling(200).mean()
        simdi_ustte = sma50.iloc[-1] > sma200.iloc[-1]
        for i in range(2, 11):
            if len(kapanis) <= i:
                break
            onceki_ustte = sma50.iloc[-i] > sma200.iloc[-i]
            if onceki_ustte != simdi_ustte:
                if simdi_ustte:
                    gozlemler.append({
                        "kategori": "Trend", "yon": "yukari",
                        "baslik": "Yakın zamanda 'altın kesişim' oldu",
                        "aciklama": "50 günlük ortalama, 200 günlük ortalamayı "
                                    "yukarı yönde kesti (son birkaç mum içinde). "
                                    "Bu, uzun vadeli trend takipçilerinin "
                                    "yakından izlediği klasik bir işarettir.",
                    })
                else:
                    gozlemler.append({
                        "kategori": "Trend", "yon": "asagi",
                        "baslik": "Yakın zamanda 'ölüm kesişimi' oldu",
                        "aciklama": "50 günlük ortalama, 200 günlük ortalamayı "
                                    "aşağı yönde kesti (son birkaç mum içinde). "
                                    "Bu, uzun vadeli trend takipçilerinin "
                                    "yakından izlediği klasik bir işarettir.",
                    })
                break

    return gozlemler


# ============================================================
#  2) MOMENTUM  (RSI seviyesi + uyumsuzluk)
# ============================================================

def gozlem_momentum(df):
    gozlemler = []
    kapanis = df["kapanis"]
    r = rsi(kapanis, 14)
    son_rsi = _son(r)

    if son_rsi is not None:
        if son_rsi >= 70:
            gozlemler.append({
                "kategori": "Momentum", "yon": "asagi",
                "baslik": f"RSI aşırı alım bölgesinde ({son_rsi:.0f})",
                "aciklama": "RSI 70 üzerinde. Piyasada bu seviye yaygın olarak "
                            "'aşırı alım' sayılır ve kısa vadeli bir "
                            "soluklanma/düzeltme beklentisi doğurabilir -- "
                            "ama fiyat aşırı alımda uzun süre kalabilir de.",
            })
        elif son_rsi <= 30:
            gozlemler.append({
                "kategori": "Momentum", "yon": "yukari",
                "baslik": f"RSI aşırı satım bölgesinde ({son_rsi:.0f})",
                "aciklama": "RSI 30 altında. Piyasada bu seviye yaygın olarak "
                            "'aşırı satım' sayılır ve tepki alımı beklentisi "
                            "doğurabilir -- ama fiyat aşırı satımda uzun süre "
                            "kalabilir de.",
            })

    uyum = _uyumsuzluk_bul(kapanis.tolist(), r.tolist())
    if uyum["boga"]:
        gozlemler.append({
            "kategori": "Momentum", "yon": "yukari",
            "baslik": "RSI'da pozitif uyumsuzluk (boğa diverjansı)",
            "aciklama": "Fiyat son iki dipte daha düşük bir seviye görürken, "
                        "RSI aynı dönemde daha yüksek bir dip yaptı. Bu, "
                        "düşüşün momentum kaybettiğine işaret sayılan, "
                        "yaygın izlenen bir uyumsuzluk türüdür -- fiyatın "
                        "kendisi bunu henüz yansıtmıyor olabilir.",
        })
    if uyum["ayi"]:
        gozlemler.append({
            "kategori": "Momentum", "yon": "asagi",
            "baslik": "RSI'da negatif uyumsuzluk (ayı diverjansı)",
            "aciklama": "Fiyat son iki tepede daha yüksek bir seviye görürken, "
                        "RSI aynı dönemde daha düşük bir tepe yaptı. Bu, "
                        "yükselişin momentum kaybettiğine işaret sayılan, "
                        "yaygın izlenen bir uyumsuzluk türüdür.",
        })

    return gozlemler


# ============================================================
#  3) MACD
# ============================================================

def gozlem_macd(df):
    gozlemler = []
    m, s, h = macd(df["kapanis"])
    son_h, onceki_h = _son(h), _son(h.iloc[:-1])
    son_m, son_s = _son(m), _son(s)

    if son_m is not None and son_s is not None:
        if son_m > son_s:
            gozlemler.append({
                "kategori": "MACD", "yon": "yukari",
                "baslik": "MACD, sinyal çizgisinin üzerinde",
                "aciklama": "MACD çizgisi sinyal çizgisinin üzerinde seyrediyor. "
                            "Momentum izleyiciler bunu 'yükseliş yönlü' olarak "
                            "okur.",
            })
        else:
            gozlemler.append({
                "kategori": "MACD", "yon": "asagi",
                "baslik": "MACD, sinyal çizgisinin altında",
                "aciklama": "MACD çizgisi sinyal çizgisinin altında seyrediyor. "
                            "Momentum izleyiciler bunu 'düşüş yönlü' olarak "
                            "okur.",
            })

    if son_h is not None and onceki_h is not None:
        if abs(son_h) > abs(onceki_h) and son_h * onceki_h >= 0:
            yon = "yukari" if son_h > 0 else "asagi"
            gozlemler.append({
                "kategori": "MACD", "yon": yon,
                "baslik": "MACD histogramı büyüyor",
                "aciklama": f"MACD histogramı {'pozitif' if son_h > 0 else 'negatif'} "
                            "yönde büyüyor -- momentumun bu yönde güçlendiğine "
                            "işaret sayılır.",
            })
        elif abs(son_h) < abs(onceki_h) and son_h * onceki_h >= 0:
            gozlemler.append({
                "kategori": "MACD", "yon": "notr",
                "baslik": "MACD histogramı küçülüyor",
                "aciklama": "MACD histogramı küçülüyor -- mevcut yöndeki "
                            "momentumun zayıfladığına işaret sayılır (henüz "
                            "yön değiştirmedi).",
            })

    return gozlemler


# ============================================================
#  4) VOLATILITE  (Bollinger, ATR)
# ============================================================

def gozlem_volatilite(df):
    gozlemler = []
    kapanis = df["kapanis"]
    if len(kapanis) < 25:
        return gozlemler

    orta = kapanis.rolling(20).mean()
    sapma = kapanis.rolling(20).std()
    ust = orta + 2 * sapma
    alt = orta - 2 * sapma
    son_fiyat = float(kapanis.iloc[-1])
    son_ust, son_alt = _son(ust), _son(alt)

    if son_ust and son_fiyat >= son_ust * 0.995:
        gozlemler.append({
            "kategori": "Volatilite", "yon": "asagi",
            "baslik": "Fiyat üst Bollinger bandına dayandı",
            "aciklama": "Fiyat, 20 günlük oynaklık bandının üst sınırına "
                        "yakın/üzerinde. Bu bölge yaygın olarak 'gerilmiş' "
                        "sayılır -- ama güçlü trendlerde fiyat bandın "
                        "üzerinde uzun süre 'yürüyebilir' de.",
        })
    if son_alt and son_fiyat <= son_alt * 1.005:
        gozlemler.append({
            "kategori": "Volatilite", "yon": "yukari",
            "baslik": "Fiyat alt Bollinger bandına dayandı",
            "aciklama": "Fiyat, 20 günlük oynaklık bandının alt sınırına "
                        "yakın/altında. Bu bölge yaygın olarak 'gerilmiş' "
                        "sayılır -- ama güçlü düşüş trendlerinde fiyat bandın "
                        "altında uzun süre kalabilir de.",
        })

    # --- Sikisma: TTM Squeeze yontemi -------------------------------
    # Bollinger bantlari Keltner kanalinin ICINE girdiginde "sikisma"
    # sayilir (iki farkli oynaklik olcusu -- std sapma ve ATR -- ayni
    # yonde "dar" diyor demektir). Sadece Bollinger'in kendi gecmisine
    # bakan eski yontemden daha guvenilir sayilir, cunku TEK bir olcuye
    # degil, IKI BAGIMSIZ olcunun uyusmasina dayanir.
    if len(kapanis) >= 40:
        alt_kc, ust_kc = _keltner_kanali(df, 20, 1.5)
        sikismada = (alt > alt_kc) & (ust < ust_kc)
        son_sikisma = bool(sikismada.iloc[-1])

        if son_sikisma:
            gozlemler.append({
                "kategori": "Volatilite", "yon": "notr",
                "baslik": _SIKISMA_BASLIK,
                "aciklama": "Bollinger bantları, Keltner kanalının İÇİNE "
                            "girdi -- oynaklık hem kendi geçmişine hem "
                            "ATR'ye göre olağan dışı düşük (TTM Squeeze "
                            "yöntemi). Piyasada 'sıkışma, patlamadan önce "
                            "gelir' diye yaygın bir söz vardır -- yönü "
                            "önceden belirtmiyor, sadece BÜYÜK bir hareket "
                            "ihtimalinin arttığını düşündürüyor.",
            })
        else:
            # Sikisma az once (son 3 mum icinde) ON'dan OFF'a mi gecti?
            son_dort = sikismada.tail(4)
            if len(son_dort) == 4 and not son_dort.iloc[-1] and son_dort.iloc[:-1].any():
                gozlemler.append({
                    "kategori": "Volatilite", "yon": "notr",
                    "baslik": "Sıkışma az önce sona erdi",
                    "aciklama": "Bollinger bantları birkaç mum önce Keltner "
                                "kanalının içindeyken şimdi dışına çıktı -- "
                                "sıkışma 'açıldı'. TTM Squeeze yönteminde bu, "
                                "hareketin başlamış olabileceğinin işareti "
                                "sayılır. Yön içermez -- hangi tarafa "
                                "açıldığını gösterge söylemez.",
                })

    a = atr(df, 14)
    if len(a.dropna()) >= 30:
        son_atr, eski_atr = _son(a), _son(a.iloc[:-15])
        if son_atr and eski_atr:
            fark = (son_atr / eski_atr - 1) * 100
            if fark > 25:
                gozlemler.append({
                    "kategori": "Volatilite", "yon": "notr",
                    "baslik": "Oynaklık belirgin şekilde artıyor",
                    "aciklama": f"Günlük fiyat hareketi (ATR) son 15 muma göre "
                                f"%{fark:.0f} arttı. Piyasa daha 'sinirli' "
                                "hareket ediyor -- bu her iki yönde de "
                                "büyük hareket riskini artırır.",
                })

    return gozlemler


# ============================================================
#  5) DESTEK / DIRENC
# ============================================================

def gozlem_destek_direnc(df, esik_yuzde=2.0, bakilan=150):
    """
    Ekrandaki gecmisten "swing" tepe/dip noktalarini bulur ve fiyatin
    bunlardan birine yakin olup olmadigina bakar.
    """
    gozlemler = []
    n = len(df)
    baslangic = max(0, n - bakilan)
    dilim = df.iloc[baslangic:].reset_index(drop=True)
    if len(dilim) < 20:
        return gozlemler

    yuksek = dilim["yuksek"].tolist()
    dusuk = dilim["dusuk"].tolist()
    tepe_idx, _ = _swing_noktalari(yuksek, pencere=3)
    _, dip_idx = _swing_noktalari(dusuk, pencere=3)

    direnc_seviyeleri = sorted({round(yuksek[i], 8) for i in tepe_idx}, reverse=True)
    destek_seviyeleri = sorted({round(dusuk[i], 8) for i in dip_idx})

    son_fiyat = float(df["kapanis"].iloc[-1])

    # En yakin direnc (fiyatin USTUNDEKI en yakin swing tepe)
    ustteki = [s for s in direnc_seviyeleri if s > son_fiyat]
    if ustteki:
        en_yakin = min(ustteki)
        mesafe = (en_yakin / son_fiyat - 1) * 100
        if mesafe <= esik_yuzde:
            gozlemler.append({
                "kategori": "Destek/Direnç", "yon": "asagi",
                "baslik": f"Direnç seviyesine yaklaşıyor ({_fiyat_yaz(en_yakin)})",
                "aciklama": f"Fiyat, geçmişte birkaç kez tepe yapılan "
                            f"{_fiyat_yaz(en_yakin)} seviyesine %{mesafe:.1f} mesafede. "
                            "Bu tür seviyeler yaygın olarak 'direnç' sayılır -- "
                            "fiyatın buradan geri dönmesi de kırıp devam etmesi "
                            "de sık görülür.",
            })

    # En yakin destek (fiyatin ALTINDAKI en yakin swing dip)
    altindaki = [s for s in destek_seviyeleri if s < son_fiyat]
    if altindaki:
        en_yakin = max(altindaki)
        mesafe = (son_fiyat / en_yakin - 1) * 100
        if mesafe <= esik_yuzde:
            gozlemler.append({
                "kategori": "Destek/Direnç", "yon": "yukari",
                "baslik": f"Destek seviyesine yaklaşıyor ({_fiyat_yaz(en_yakin)})",
                "aciklama": f"Fiyat, geçmişte birkaç kez dip yapılan "
                            f"{_fiyat_yaz(en_yakin)} seviyesine %{mesafe:.1f} mesafede. "
                            "Bu tür seviyeler yaygın olarak 'destek' sayılır -- "
                            "fiyatın buradan tepki vermesi de kırıp devam "
                            "etmesi de sık görülür.",
            })

    # Yil ici zirve/dip'e yakinlik (ayrica ilginc bir referans noktasi)
    yil_zirve = float(df["yuksek"].tail(365).max())
    yil_dip = float(df["dusuk"].tail(365).min())
    if son_fiyat >= yil_zirve * (1 - esik_yuzde / 100):
        gozlemler.append({
            "kategori": "Destek/Direnç", "yon": "notr",
            "baslik": "Son 1 yılın zirvesine yakın",
            "aciklama": f"Fiyat, son 365 günün en yükseği olan {_fiyat_yaz(yil_zirve)} "
                        "seviyesine yakın. Bu seviyeler psikolojik olarak da "
                        "yakından izlenir.",
        })
    if son_fiyat <= yil_dip * (1 + esik_yuzde / 100):
        gozlemler.append({
            "kategori": "Destek/Direnç", "yon": "notr",
            "baslik": "Son 1 yılın dibine yakın",
            "aciklama": f"Fiyat, son 365 günün en düşüğü olan {_fiyat_yaz(yil_dip)} "
                        "seviyesine yakın. Bu seviyeler psikolojik olarak da "
                        "yakından izlenir.",
        })

    return gozlemler


# ============================================================
#  6) HACIM VE PARA AKISI
# ============================================================

def gozlem_hacim(df):
    gozlemler = []
    hacim = df["hacim"]
    if len(hacim) < 25:
        return gozlemler

    ort_hacim = float(hacim.rolling(20).mean().iloc[-1])
    son_hacim = float(hacim.iloc[-1])
    if ort_hacim > 0 and son_hacim >= ort_hacim * 2:
        yon_fiyat = "yukari" if df["kapanis"].iloc[-1] >= df["acilis"].iloc[-1] else "asagi"
        gozlemler.append({
            "kategori": "Hacim", "yon": yon_fiyat,
            "baslik": "Hacimde belirgin bir patlama var",
            "aciklama": f"Son mumun hacmi, 20 mumluk ortalamanın "
                        f"{son_hacim/ort_hacim:.1f} katı. Bu, o mumdaki fiyat "
                        "hareketinin normalden çok daha fazla katılımcı "
                        "tarafından desteklendiğini gösterir.",
        })

    # OBV trend + fiyat karsilastirmasi
    obv = _obv(df)
    if len(obv) >= 20:
        obv_degisim = (obv.iloc[-1] - obv.iloc[-20])
        fiyat_degisim = (df["kapanis"].iloc[-1] / df["kapanis"].iloc[-20] - 1) * 100
        obv_yon = "yukari" if obv_degisim > 0 else ("asagi" if obv_degisim < 0 else "notr")

        if obv_yon == "yukari" and fiyat_degisim <= 0.5:
            gozlemler.append({
                "kategori": "Hacim", "yon": "yukari",
                "baslik": "Fiyat durgunken hacim para girişi işareti veriyor",
                "aciklama": "Son 20 mumda fiyat belirgin yükselmemiş olsa da, "
                            "yükselen mumlardaki hacim düşen mumlardakinden "
                            "daha ağır basıyor (OBV yükseliyor). Bu, bazı "
                            "analistlerin 'sessiz birikim' ya da 'para girişi' "
                            "olarak yorumladığı bir durumdur -- fiyatın "
                            "grafikte henüz görünmeyen bir talep olabileceğini "
                            "düşündürür.",
            })
        elif obv_yon == "asagi" and fiyat_degisim >= -0.5:
            gozlemler.append({
                "kategori": "Hacim", "yon": "asagi",
                "baslik": "Fiyat durgunken hacim para çıkışı işareti veriyor",
                "aciklama": "Son 20 mumda fiyat belirgin düşmemiş olsa da, "
                            "düşen mumlardaki hacim yükselen mumlardakinden "
                            "daha ağır basıyor (OBV düşüyor). Bazı analistler "
                            "bunu 'sessiz dağıtım' olarak yorumlar.",
            })

        uyum = _uyumsuzluk_bul(df["kapanis"].tolist(), obv.tolist())
        if uyum["boga"]:
            gozlemler.append({
                "kategori": "Hacim", "yon": "yukari",
                "baslik": "Hacimde (OBV) pozitif uyumsuzluk",
                "aciklama": "Fiyat daha düşük bir dip yaparken, hacim akışı "
                            "(OBV) daha yüksek bir dip yaptı -- düşüşün "
                            "hacim desteğini kaybettiğine işaret sayılır.",
            })
        if uyum["ayi"]:
            gozlemler.append({
                "kategori": "Hacim", "yon": "asagi",
                "baslik": "Hacimde (OBV) negatif uyumsuzluk",
                "aciklama": "Fiyat daha yüksek bir tepe yaparken, hacim akışı "
                            "(OBV) daha düşük bir tepe yaptı -- yükselişin "
                            "hacim desteğini kaybettiğine işaret sayılır.",
            })

    # VWAP konumu
    v = vwap(df)
    son_vwap = _son(v)
    if son_vwap:
        son_fiyat = float(df["kapanis"].iloc[-1])
        fark = (son_fiyat / son_vwap - 1) * 100
        if abs(fark) > 1:
            gozlemler.append({
                "kategori": "Hacim", "yon": "yukari" if fark > 0 else "asagi",
                "baslik": f"Fiyat, hacim ağırlıklı ortalamanın {'üzerinde' if fark > 0 else 'altında'}",
                "aciklama": f"Fiyat, ekrandaki mumlar boyunca hacim ağırlıklı "
                            f"ortalama fiyatın (VWAP) %{abs(fark):.1f} "
                            f"{'üzerinde' if fark > 0 else 'altında'}. Kurumsal "
                            "işlemciler bu çizgiyi sık sık bir 'adil fiyat' "
                            "referansı olarak kullanır.",
            })

    return gozlemler


# ============================================================
#  7) VADELI PIYASA  (fonlama orani)
# ============================================================

def gozlem_vadeli(fonlama):
    """
    fonlama: veri_kaynaklari.fonlama_orani()'nin dondurdugu sozluk
    (None olabilir -- coin'in vadeli piyasasi yoksa).
    """
    if not fonlama or fonlama.get("oran_yuzde") is None:
        return []

    oran = fonlama["oran_yuzde"]
    gozlemler = []
    if oran >= 0.05:
        gozlemler.append({
            "kategori": "Vadeli Piyasa", "yon": "asagi",
            "baslik": "Fonlama oranı olağan dışı yüksek (pozitif)",
            "aciklama": f"8 saatlik fonlama oranı +%{oran:.3f} -- yıllık "
                        f"karşılığı yaklaşık %{fonlama['yillik_yuzde']:.0f}. "
                        "Bu, vadeli piyasada yükseliş bekleyenlerin çok "
                        "kalabalık olduğunu gösterir. Bazı analistler aşırı "
                        "kalabalık pozisyonlanmayı 'ters yönde risk' olarak "
                        "okur -- ama kalabalık haklı çıkabilir de.",
        })
    elif oran <= -0.02:
        gozlemler.append({
            "kategori": "Vadeli Piyasa", "yon": "yukari",
            "baslik": "Fonlama oranı olağan dışı düşük (negatif)",
            "aciklama": f"8 saatlik fonlama oranı %{oran:.3f} -- yıllık "
                        f"karşılığı yaklaşık %{fonlama['yillik_yuzde']:.0f}. "
                        "Bu, vadeli piyasada düşüş bekleyenlerin çok "
                        "kalabalık olduğunu gösterir. Bazı analistler aşırı "
                        "kalabalık pozisyonlanmayı 'ters yönde risk' olarak "
                        "okur -- ama kalabalık haklı çıkabilir de.",
        })
    return gozlemler


def gozlem_acik_pozisyon(oi_gecmisi):
    """
    oi_gecmisi: veri_kaynaklari.acik_pozisyon_gecmisi()'nin dondurdugu
    listesi (en eskiden en yeniye sirali acik pozisyon miktarlari).
    Coin'in vadeli piyasasi yoksa None gelir.

    Acik pozisyon artiyorsa vadeli piyasaya TAZE PARA giriyor demektir;
    azaliyorsa pozisyonlar kapaniyor demektir. TEK BASINA yon soylemez
    -- artis hem yukari hem asagi pozisyonlarla olabilir. Bu yuzden
    "notr" -- sadece "katilim artiyor/azaliyor" bilgisini tasir.
    """
    if not oi_gecmisi or len(oi_gecmisi) < 5:
        return []

    son, esik_gun_once = oi_gecmisi[-1], oi_gecmisi[-5]
    if not esik_gun_once:
        return []

    fark = (son / esik_gun_once - 1) * 100
    if fark >= 5:
        return [{
            "kategori": "Vadeli Piyasa", "yon": "notr",
            "baslik": f"Açık pozisyon artıyor (%{fark:+.0f})",
            "aciklama": f"Vadeli piyasadaki açık pozisyon son 5 günde "
                        f"%{fark:.0f} arttı -- piyasaya taze sözleşme (yeni "
                        "para) girdiğini gösterir. Fiyat hareketiyle "
                        "birlikte görülürse hareketin taze katılımla "
                        "desteklendiği düşünülür; tek başına yön belirtmez.",
        }]
    if fark <= -5:
        return [{
            "kategori": "Vadeli Piyasa", "yon": "notr",
            "baslik": f"Açık pozisyon azalıyor (%{fark:+.0f})",
            "aciklama": f"Vadeli piyasadaki açık pozisyon son 5 günde "
                        f"%{fark:.0f} azaldı -- pozisyonlar kapanıyor "
                        "demektir.",
        }]
    return []


# ============================================================
#  8) EMIR DEFTERI
# ============================================================

def gozlem_emir_defteri(defter):
    """
    defter: veri_kaynaklari.emir_defteri_ozeti()'nin dondurdugu sozluk.

    UYARI: emir defteri ANLIK bir fotograftir, saniyeler icinde
    tamamen degisebilir. Buradan gelen gozlem digerlerinden cok daha
    "gecici" sayilmalidir.
    """
    if not defter or defter.get("alis_baskisi") is None:
        return []

    baski = defter["alis_baskisi"]
    if baski >= 65:
        return [{
            "kategori": "Emir Defteri", "yon": "yukari",
            "baslik": f"Emir defterinde alış baskısı yüksek (%{baski:.0f})",
            "aciklama": "Bekleyen alış emirlerinin hacmi, satış emirlerinden "
                        "belirgin fazla. Bu ANLIK bir görüntüdür, saniyeler "
                        "içinde değişebilir -- yine de kısa vadeli bir "
                        "eğilim göstergesi olarak izlenir.",
        }]
    if baski <= 35:
        return [{
            "kategori": "Emir Defteri", "yon": "asagi",
            "baslik": f"Emir defterinde satış baskısı yüksek (%{100-baski:.0f})",
            "aciklama": "Bekleyen satış emirlerinin hacmi, alış emirlerinden "
                        "belirgin fazla. Bu ANLIK bir görüntüdür, saniyeler "
                        "içinde değişebilir.",
        }]
    return []


# ============================================================
#  9) BTC'YE GORE GORECE GUC
# ============================================================

def gozlem_goreli_guc(df_coin, df_btc, sembol_kodu):
    """
    Coin, ayni donemde BTC'ye gore daha mi iyi/kotu gidiyor?

    FIKIR: Butun piyasa dusuyorsa neredeyse her coin duser -- bu tek
    basina anlamli degildir. Ama bir coin, BTC ayni donemde %X
    duserken daha AZ dusuyor ya da yukseliyorsa, bu "goreli guc"
    o coine ozel bir talep olabilecegini dusundurur (bazen "akilli
    paranin nereye gittigi" olarak yorumlanir).
    """
    if df_btc is None or len(df_btc) < 20 or sembol_kodu == "BTC":
        return []

    n = min(len(df_coin), len(df_btc), 30)
    coin_getiri = (df_coin["kapanis"].iloc[-1] / df_coin["kapanis"].iloc[-n] - 1) * 100
    btc_getiri = (df_btc["kapanis"].iloc[-1] / df_btc["kapanis"].iloc[-n] - 1) * 100
    fark = coin_getiri - btc_getiri

    if abs(fark) < 3:
        return []

    if fark > 0:
        return [{
            "kategori": "Göreli Güç", "yon": "yukari",
            "baslik": f"BTC'den daha güçlü ({fark:+.1f} puan)",
            "aciklama": f"Son {n} mumda {sembol_kodu} %{coin_getiri:+.1f}, "
                        f"BTC ise %{btc_getiri:+.1f} getiri sağladı. "
                        f"{sembol_kodu}, BTC'ye göre {fark:.1f} puan daha "
                        "iyi performans gösterdi -- bu coine özel bir talep "
                        "olabileceğini düşündürür (kesin kanıt değildir).",
        }]
    return [{
        "kategori": "Göreli Güç", "yon": "asagi",
        "baslik": f"BTC'den daha zayıf ({fark:+.1f} puan)",
        "aciklama": f"Son {n} mumda {sembol_kodu} %{coin_getiri:+.1f}, "
                    f"BTC ise %{btc_getiri:+.1f} getiri sağladı. "
                    f"{sembol_kodu}, BTC'ye göre {abs(fark):.1f} puan daha "
                    "zayıf performans gösterdi.",
    }]


# ============================================================
#  10) LIKIDITE AVI  (Swing Failure Pattern / stop hunt)
# ============================================================
#
# KAVRAM (yaygin adlari: "likidite avi", "stop hunt", "liquidity
# sweep", "Swing Failure Pattern / SFP"): onceki bir swing dip/tepe
# seviyesinin cevresinde -- ozellikle o seviyeyi kiran/test eden
# noktalarda -- stop-loss ve kirilim (breakout) emirleri birikir.
# Fiyat bu seviyenin biraz OTESINE gecip (fitille) o emirleri
# "supurdukten" sonra, eger devam gucu yoksa hizla seviyenin GERI
# ICINE doner (kapanis o seviyenin tekrar dogru tarafinda kalir).
# Kullanicinin tarif ettigi "aniden kirmizi mum geldi, likiditeye
# dogru gitti, ama bu sahte olabilir" durumu tam olarak budur.
#
# NASIL TESPIT EDILIYOR (yaygin uygulanan tarif, arastirmayla
# dogrulandi -- bkz. README.md):
#   1. Onceki (son mum HARIC) bir swing dip/tepe seviyesi bulunur.
#   2. Son (kapanmis) mumun fitili o seviyenin OTESINE geciyor mu?
#   3. Ama son mumun KAPANISI seviyenin YINE DOGRU tarafinda mi?
#   4. Hacim o mumda ORTALAMANIN BELIRGIN UZERINDE mi (kullanicinin
#      istedigi "para giris/cikisina bakarak" teyidi budur -- bir
#      supurme gercek emir akisiyla mi oldu, yoksa sessiz bir
#      dalgalanma mi)?
# Sadece 1-3 saglanirsa "zayif" (hacim teyidi yok) sayilir; 4 de
# saglanirsa "guclu" (hacim teyitli) sayilir -- ikisi de gozlem
# listesine girer, sadece aciklama metni farklilasir.
#
# DURUSTLUK NOTU: Web arastirmasinda bu deseni "%66-68 basari orani"
# ile aniliyor bazi kaynaklar -- ama bu projede defalarca kanitladigimiz
# gibi (tarama.py) boyle rakamlara guvenmiyoruz, kimse bunu bagimsiz,
# kontrol-gruplu sekilde test edip yayinlamadi. O yuzden burada boyle
# bir basari orani ILERI SURULMUYOR -- sadece "bu, piyasada yaygin
# izlenen bir desenle eslesiyor" deniyor, "genelde doner" DENMIYOR.

def gozlem_likidite_avi(df, pencere=3, bakilan=150, hacim_esigi=1.5, esik_ust=15.0):
    """
    Son (kapanmis) mumun, onceki bir swing dip/tepe seviyesini fitille
    kirip kapanista geri donup donmedigine bakar. Swing seviyeleri SON
    MUM HARIC tutularak hesaplanir (kendi kendine referans olmasin).

    esik_ust: sarkma/asma yuzdesi bunun (%15) UZERINDEYSE gozlem
    ATLANIR. NEDEN: gercek bir "likidite avi" TANIM GEREGI kucuk,
    kisa surelli bir fitil sarkmasidir (genelde %0-3 arasi) -- yuzde
    onlarca/yuzlerce sarkma, ayni formule uysa bile artik "ince bir
    stop supurmesi" degil, tamamen farkli bir olay (buyuk bir pump/dump,
    ya da eski/durgun bir swing seviyesinin referans olarak anlamsiz
    kalmasi) demektir. Testte bunu yakaladik: bir coin'de "%159.85
    uzerine cikti" gibi anlamsiz bir deger cikti -- bu sinir onu eler.

    Donen "yon":
      "yukari" -> dip seviyesi supuruldu ama kapanis ustunde kaldi
                  (olasi sahte dusus / boga likidite avi)
      "asagi"  -> tepe seviyesi supuruldu ama kapanis altinda kaldi
                  (olasi sahte yukselis / ayi likidite avi)
    """
    if df is None:
        return []
    n = len(df)
    if n < 2 * pencere + 10:
        return []

    baslangic = max(0, n - 1 - bakilan)
    onceki = df.iloc[baslangic:n - 1].reset_index(drop=True)  # son mum HARIC
    if len(onceki) < 2 * pencere + 5:
        return []

    yuksekler = onceki["yuksek"].tolist()
    dusukler = onceki["dusuk"].tolist()
    tepe_idx, _ = _swing_noktalari(yuksekler, pencere)
    _, dip_idx = _swing_noktalari(dusukler, pencere)

    son = df.iloc[-1]
    son_yuksek, son_dusuk = float(son["yuksek"]), float(son["dusuk"])
    son_kapanis, son_hacim = float(son["kapanis"]), float(son["hacim"])

    ort_hacim = None
    if n >= 22:
        ort = df["hacim"].iloc[-21:-1].mean()  # son mum HARIC son 20 mum
        ort_hacim = float(ort) if ort == ort else None  # NaN kontrolu
    hacim_teyitli = bool(ort_hacim and ort_hacim > 0
                        and son_hacim >= ort_hacim * hacim_esigi)

    gozlemler = []
    esik = 0.0002  # binde 0.2 -- kayan nokta/yuvarlama gurultusunu ele

    def _hacim_cumlesi():
        if hacim_teyitli:
            return ("Bu mumun hacmi de son 20 mumun ortalamasının belirgin "
                    "üzerinde -- süpürmenin gerçek bir emir akışıyla "
                    "desteklendiği düşünülür.")
        return ("Hacim özellikle yüksek değildi -- bu da desenin daha zayıf "
                "bir teyide sahip olduğunu gösterir.")

    # --- BOGA: dip supuruldu, kapanis ustunde kaldi -------------
    if dip_idx:
        dip_seviye = dusukler[dip_idx[-1]]  # en son (en yakin) swing dip
        sarkma = ((dip_seviye - son_dusuk) / dip_seviye * 100) if dip_seviye > 0 else 0.0
        if (dip_seviye > 0 and son_dusuk < dip_seviye * (1 - esik)
                and son_kapanis > dip_seviye and sarkma <= esik_ust):
            gozlemler.append({
                "kategori": "Likidite",
                "yon": "yukari",
                "baslik": "Olası likidite avı — destek fitille kırıldı, kapanış geri döndü"
                          + (" (hacim teyitli)" if hacim_teyitli else ""),
                "aciklama": f"Fiyat, önceki bir dip seviyesi olan "
                            f"{_fiyat_yaz(dip_seviye)} seviyesinin %{sarkma:.2f} "
                            f"altına indi, ama son mum {_fiyat_yaz(son_kapanis)} "
                            "seviyesinde -- yine o dip seviyesinin ÜZERİNDE -- "
                            "kapandı. Bu, 'likidite avı' / 'Swing Failure "
                            "Pattern' olarak adlandırılan, o seviyenin altında "
                            "bekleyen stop-loss ve kırılım emirlerinin süpürülüp "
                            f"fiyatın geri toparlandığı örüntüyle eşleşiyor. "
                            f"{_hacim_cumlesi()} "
                            "Bu bir tahmin değildir -- desen yaygın izlenir ama "
                            "her sahte kırılım gerçekten dönmez.",
            })

    # --- AYI: tepe supuruldu, kapanis altinda kaldi --------------
    if tepe_idx:
        tepe_seviye = yuksekler[tepe_idx[-1]]  # en son (en yakin) swing tepe
        sarkma = ((son_yuksek - tepe_seviye) / tepe_seviye * 100) if tepe_seviye > 0 else 0.0
        if (tepe_seviye > 0 and son_yuksek > tepe_seviye * (1 + esik)
                and son_kapanis < tepe_seviye and sarkma <= esik_ust):
            gozlemler.append({
                "kategori": "Likidite",
                "yon": "asagi",
                "baslik": "Olası likidite avı — direnç fitille kırıldı, kapanış geri döndü"
                          + (" (hacim teyitli)" if hacim_teyitli else ""),
                "aciklama": f"Fiyat, önceki bir tepe seviyesi olan "
                            f"{_fiyat_yaz(tepe_seviye)} seviyesinin %{sarkma:.2f} "
                            f"üzerine çıktı, ama son mum {_fiyat_yaz(son_kapanis)} "
                            "seviyesinde -- yine o tepe seviyesinin ALTINDA -- "
                            "kapandı. Bu, 'likidite avı' / 'Swing Failure "
                            "Pattern' olarak adlandırılan, o seviyenin üstünde "
                            "bekleyen stop-loss ve kırılım emirlerinin süpürülüp "
                            f"fiyatın geri toparlandığı örüntüyle eşleşiyor. "
                            f"{_hacim_cumlesi()} "
                            "Bu bir tahmin değildir -- desen yaygın izlenir ama "
                            "her sahte kırılım gerçekten dönmez.",
            })

    return gozlemler


# ============================================================
#  11) FAIR VALUE GAP  (fiyat dengesizligi)
# ============================================================
#
# bkz. desenler.py basindaki tanim ve durustluk notu. Burada sadece
# ekrandaki EN YAKIN aktif (henuz doldurulmamis) bosluklari gozlem
# olarak bildiriyoruz -- coktan doldurulmus eski bosluklar gosterilmez,
# cunku artik "gecerli" sayilmazlar.

def gozlem_fair_value_gap(df, bakilan=150):
    if df is None:
        return []
    bolgeler = [b for b in fair_value_gap_bolgeleri(df, bakilan) if b["aktif"]]
    if not bolgeler:
        return []

    son_fiyat = float(df["kapanis"].iloc[-1])
    gozlemler = []
    for tur in ("boga", "ayi"):
        adaylar = [b for b in bolgeler if b["tur"] == tur]
        if not adaylar:
            continue
        en_yakin = min(adaylar, key=lambda b: abs(son_fiyat - (b["alt"] + b["ust"]) / 2))
        yon = "yukari" if tur == "boga" else "asagi"
        yon_kelime = "üzerinde" if son_fiyat > en_yakin["ust"] else (
            "altında" if son_fiyat < en_yakin["alt"] else "içinde")
        gozlemler.append({
            "kategori": "Fair Value Gap", "yon": yon,
            "baslik": f"Doldurulmamış {'boğa' if tur == 'boga' else 'ayı'} FVG "
                      f"({_fiyat_yaz(en_yakin['alt'])} – {_fiyat_yaz(en_yakin['ust'])})",
            "aciklama": f"Fiyat şu an bu boşluğun {yon_kelime}. "
                        "'Fair value gap' (fiyat dengesizliği), güçlü tek yönlü bir "
                        "hareket sırasında 3 mum arasında kimsenin işlem yapmadığı bir "
                        "aralık kalmasıdır. Bazı analistler fiyatın er ya da geç buraya "
                        "dönüp 'doldurduğunu' iddia eder -- bu TEK bir kaynakça kabul "
                        "görmüş bir kural değildir ve burada bir tahmin olarak "
                        "sunulmuyor, sadece 'bu bölge hâlâ dolmamış' bilgisi veriliyor.",
        })
    return gozlemler


# ============================================================
#  12) ORDER BLOCK  (guclu hareketin baslangic bolgesi)
# ============================================================
#
# bkz. desenler.py basindaki tanim ve durustluk notu. Sadece ekrandaki
# EN YAKIN aktif (henuz gecersiz kilinmamis) bolgeleri bildirir.

def gozlem_order_block(df, bakilan=150):
    if df is None:
        return []
    bolgeler = [b for b in order_block_bolgeleri(df, bakilan) if b["aktif"]]
    if not bolgeler:
        return []

    son_fiyat = float(df["kapanis"].iloc[-1])
    gozlemler = []
    for tur in ("boga", "ayi"):
        adaylar = [b for b in bolgeler if b["tur"] == tur]
        if not adaylar:
            continue
        en_yakin = min(adaylar, key=lambda b: abs(son_fiyat - (b["alt"] + b["ust"]) / 2))
        yon = "yukari" if tur == "boga" else "asagi"
        gozlemler.append({
            "kategori": "Order Block", "yon": yon,
            "baslik": f"Geçerliliğini koruyan {'boğa' if tur == 'boga' else 'ayı'} "
                      f"Order Block ({_fiyat_yaz(en_yakin['alt'])} – {_fiyat_yaz(en_yakin['ust'])})",
            "aciklama": "'Order block', güçlü bir hareketten hemen önceki son ters "
                        "yönlü mumun bıraktığı bölgedir -- bazı analistler burayı "
                        "büyük (kurumsal) emirlerin biriktiği yer sayar ve fiyat bu "
                        "bölgeye geri dönüp tepki verirse hareketin devam edeceğini "
                        "düşünür. Bu TEK bir kaynakça kabul görmüş bir kural değildir "
                        "ve burada bir tahmin olarak sunulmuyor, sadece 'bu bölge hâlâ "
                        "geçersiz kılınmadı' bilgisi veriliyor.",
        })
    return gozlemler


# ============================================================
#  HEPSINI TOPLA
# ============================================================

def tum_gozlemler(df, fonlama=None, defter=None, df_btc=None, sembol_kodu="",
                   oi_gecmisi=None):
    """
    Butun gozlem fonksiyonlarini calistirir ve TEK bir liste halinde
    dondurur. Sira/oncelik ONEMLI DEGIL -- hicbir agirliklandirma ya
    da siralama "onem" ifade etmez, sadece kategoriye gore gruplu
    gosterim icin kullanilir (uygulama.py'de).
    """
    if df is None or len(df) < 25:
        return []

    hepsi = []
    hepsi += gozlem_trend(df)
    hepsi += gozlem_momentum(df)
    hepsi += gozlem_macd(df)
    hepsi += gozlem_volatilite(df)
    hepsi += gozlem_destek_direnc(df)
    hepsi += gozlem_hacim(df)
    hepsi += gozlem_vadeli(fonlama)
    hepsi += gozlem_acik_pozisyon(oi_gecmisi)
    hepsi += gozlem_emir_defteri(defter)
    hepsi += gozlem_goreli_guc(df, df_btc, sembol_kodu)
    hepsi += gozlem_likidite_avi(df)
    hepsi += gozlem_fair_value_gap(df)
    hepsi += gozlem_order_block(df)
    return hepsi


# ============================================================
#  PIYASA TARAMASI  (coklu coin, "sikisma + hacim" deseni)
# ============================================================
#
# BU FONKSIYON DA TAHMIN YAPMAZ. Yaptigi tek sey, coklu coin uzerinde
# ayni sikisma/hacim gozlemlerini (yukarida zaten var olan
# gozlem_volatilite / gozlem_hacim) arayip, HANGI coinlerde su an
# gorundugunu bulmak. Bircok buyuk hareketten once "once sikisma,
# sonra hacim" kalibi yaygin olarak izlenir -- ama bu, o kalibin
# gorulmesinin coinin YUKSELECEGI ya da DUSECEGI anlamina geldigi
# ANLAMINA GELMEZ. tarama.py'de kanitladigimiz gibi (16 stratejinin
# hicbiri rastgeleyi gecemedi), boyle bir garanti YOK. Bu fonksiyon
# sadece "burada dikkat cekici bir durum var, bakmaya deger" der.

def tarama_adayi(df):
    """
    Bir coin su an "sikisma" ve/veya "yukari yonlu hacim sinyali"
    gosteriyor mu diye bakar. Gunluk mum verisi bekler (en az ~50 mum).

    Hacim bacagi BILEREK sadece "yukari" etiketli hacim gozlemlerini
    sayar (patlama bir KIRMIZI mumda olduysa ya da "para cikisi"
    gorulduyse SAYILMAZ) -- kullanicinin istedigi "yukselen yapi/hacim"
    formulunun hacim bacagi budur.

    Donus: None (dikkat cekici bir sey yok) ya da:
        {"seviye": "guclu" | "sikisma", "gozlemler": [...]}
    "guclu"   : sikisma VE yukari yonlu hacim sinyali birlikte.
    "sikisma" : sadece sikisma var, yukari yonlu hacim henuz yok.

    "guclu"/"sikisma" bir "iyi/kotu" degerlendirmesi degildir -- sadece
    durumun ne kadar dikkat cekici oldugunu siniflandirir. "seviye"
    alani daha sonra uygulama.py'de vadeli piyasa teyidiyle "teyitli"ye
    yukseltilebilir (bkz. kurulum_teyidi).
    """
    if df is None or len(df) < 50:
        return None

    vol_obs = gozlem_volatilite(df)
    if not any(o["baslik"] == _SIKISMA_BASLIK for o in vol_obs):
        return None

    hac_obs = gozlem_hacim(df)
    hacim_gozlemleri = [o for o in hac_obs
                         if o["baslik"] in _HACIM_SINYAL_BASLIKLARI and o["yon"] == "yukari"]
    sikisma_gozlemi = [o for o in vol_obs if o["baslik"] == _SIKISMA_BASLIK]

    return {
        "seviye": "guclu" if hacim_gozlemleri else "sikisma",
        "gozlemler": sikisma_gozlemi + hacim_gozlemleri,
    }


def kurulum_teyidi(fonlama, oi_gecmisi):
    """
    Kullanicinin istedigi ucuncu bacak: "vadeli akis uygun mu?"

    Iki kosul BIRLIKTE aranir:
      1. Fonlama orani asiri POZITIF DEGIL (asiri pozitif = long'lar
         zaten kalabalik/pahali -- yeni bir yukselisin "yakit"i azalir).
      2. Acik pozisyon son 5 gunde en az %3 artmis (vadeli piyasaya
         TAZE para giriyor -- hareketin sadece eski pozisyonlarin
         yeniden fiyatlanmasi degil, gercek katilimla oldugunu
         dusundurur).

    ONEMLI SINIRLAMALAR:
      - Bircok altcoin'in Binance'te vadeli piyasasi YOK -- boyle
        coinler icin bu fonksiyon her zaman False doner (teyit
        edilemez demektir, "kotu" demek DEGILDIR).
      - Bu bir GARANTI DEGIL. Sadece vadeli piyasa akisinin, sikisma ve
        hacmin isaret ettigi yonle CELISMEDIGINI gosterir. tarama.py'de
        kanitladigimiz gibi hicbir gostergenin gelecegi guvenilir
        sekilde tahmin ettigi kanitlanmadi.
    """
    if not fonlama or fonlama.get("oran_yuzde") is None:
        return False
    if fonlama["oran_yuzde"] >= 0.05:
        return False

    if not oi_gecmisi or len(oi_gecmisi) < 5:
        return False
    son, esik_gun_once = oi_gecmisi[-1], oi_gecmisi[-5]
    if not esik_gun_once:
        return False

    return (son / esik_gun_once - 1) >= 0.03
