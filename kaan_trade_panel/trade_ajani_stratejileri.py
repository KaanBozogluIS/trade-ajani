r"""
TRADE AJANI STRATEJILERI (aktarilmis)
======================================

Bu dosya, "Trade-ajani" adli ayri bir projede (C:\Users\Kaan\OneDrive\
Masaustu\Trade-ajani) sifirdan tasarlanip gercek IS/OOS (egitim/test
donemi ayrimi) taramalariyle DOGRULANMIS 4 stratejinin bu projenin
(kaan-trade) kalibina UYARLANMIS halidir.

NEDEN AYRI DOSYA: mevcut stratejiler.py / strateji_desenleri.py'ye
DOKUNULMADI - hicbir test edilmis kod degistirilmedi, sadece EKLENDI.
Bu dosyayi tarama.py/sanal_trader.py'nin kullandigi listeye eklemek
isterseniz asagidaki STRATEJILER listesini ilgili dosyaya birlestirin
(bkz. dosya sonu).

UYARLAMA KURALLARI (Trade-ajani -> kaan-trade):
  1) Sutun adlari: close/high/low/open/volume -> kapanis/yuksek/dusuk/
     acilis/hacim.
  2) Trade-ajani'deki stratejilerin bir kismi SHORT (kisa pozisyon) da
     uretiyordu. Bu proje LONG-ONLY (bkz. strateji_desenleri.py'deki ayni
     kural) - o yuzden SHORT sinyalleri "pozisyondan CIK" olarak
     yorumlandi, "kisa ac" olarak DEGIL (digerleriyle tutarli).
  3) Trade-ajani'deki "bekleyen kurulum" (pending) durum makinesi (bolgeye
     deginme -> pencere icinde onay bekleme) BIREBIR korundu - bu,
     Trade-ajani'de defalarca (once ayni-barda-cok-kosul tuzagina
     dusulerek) sinanmis, dogru calisan mimari.
  4) Sabit stop-loss/take-profit (R-kati hedef) mantigi, kaan-trade'in
     "pozisyondayim/degilim" (0/1) kalibina gore ADAPTE edildi: hedefe ya
     da stopa DOKUNULDUGUNDA pozisyon KAPANIR (0.0 doner).

DURUSTLUK NOTU (kaan-trade'in kendi gelenegiyle AYNI): bu stratejiler
Trade-ajani'de kendi veri kumeleri/zaman dilimlerinde dogrulandi - AYNI
sonuc burada, bu projenin FARKLI veri kaynagi/evreninde tekrar
GARANTI DEGIL. tarama.py ile, digerleriyle AYNI rastgele-kontrol-grubu
yontemiyle yeniden olculmeli.

Trade-ajani'deki dogrulanmis kaynak dosyalar (referans):
  - core/strategies/breakout_retest_recovery.py ("altcoin_stratejisi")
  - core/strategies/reversal_pullback.py ("tepe_dip_stratejisi")
  - core/strategies/volume_absorption.py ("hacim_uyumsuzlugu_stratejisi")
  - core/strategies/major_trend_rider.py ("major_stratejisi")
"""

import numpy as np
import pandas as pd

from stratejiler import atr, rsi


def _swing_noktalari_basit(yuksek, dusuk, sol=5, sag=5):
    """Trade-ajani'deki core/smc.py'nin swing_points() ile AYNI fikir,
    bagimliliksiz kucuk bir kopyasi: bir bar, solundaki VE sagindaki <sol>/
    <sag> bardan daha yuksek/dusukse swing noktasidir - ama ancak <sag>
    bar SONRASI onaylanabilir (ileriye bakma yok)."""
    n = len(yuksek)
    tepe = np.zeros(n, dtype=bool)
    dip = np.zeros(n, dtype=bool)
    for i in range(sol, n - sag):
        pencere_yuksek = yuksek[i - sol:i + sag + 1]
        pencere_dusuk = dusuk[i - sol:i + sag + 1]
        if yuksek[i] == pencere_yuksek.max():
            tepe[i] = True
        if dusuk[i] == pencere_dusuk.min():
            dip[i] = True
    # Onay <sag> bar GECIKMELI - o barin swing oldugu ancak <sag> bar
    # sonra "bilinir".
    tepe_onay = np.zeros(n, dtype=bool)
    dip_onay = np.zeros(n, dtype=bool)
    tepe_onay[sag:] = tepe[:-sag] if sag > 0 else tepe
    dip_onay[sag:] = dip[:-sag] if sag > 0 else dip
    return tepe_onay, dip_onay, tepe, dip


# ============================================================
#  1) KIRILIM - GERI CEKILME - TOPARLANMA  ("altcoin_stratejisi")
# ============================================================
# Orta/kucuk cap altcoinlerde Trade-ajani'de dogrulandi (SEI/SHIB/FET/
# BICO/WLD/ZKC/BMT/PENGU/ZEN, 1sa). BTC/ETH gibi majorlerde CALISMADI -
# orada baska bir mekanik (asagida #4) gerekiyordu.

def kirilim_geri_cekilme_toparlanma(df, sol=5, sag=5, pencere=150, tolerans_yuzde=0.4,
                                     min_deginme=2, atr_periyot=14, kirilim_atr_kati=0.2,
                                     maks_bekleme=30, toparlanma_govde_orani=0.5,
                                     stop_atr_tamponu=0.3, hedef_r_kati=1.5):
    """
    COKLU-DOKUNUSLU destek/direnc + KARARLI kirilim (kapanis-bazli) +
    seviyeye GERI CEKILME + guclu kapanisli TOPARLANMA mumu ile giris.
    Trade-ajani'deki EN GUCLU tek sonuc (SEIUSDT 1sa: kazanma %56, kar
    faktoru 1.71) bu mekanikle bulundu.
    """
    yuksek = df["yuksek"].to_numpy()
    dusuk = df["dusuk"].to_numpy()
    acilis = df["acilis"].to_numpy()
    kapanis = df["kapanis"].to_numpy()
    n = len(df)

    tepe_onay, dip_onay, _, _ = _swing_noktalari_basit(yuksek, dusuk, sol, sag)
    a = atr(df, atr_periyot).to_numpy()
    tol = tolerans_yuzde / 100.0

    son_tepeler = []  # (indeks, fiyat)
    son_dipler = []

    def _gecerli_bolge(noktalar, en_buyuk_mu):
        if len(noktalar) < min_deginme:
            return None
        fiyatlar = [p for _, p in noktalar]
        capa = max(fiyatlar) if en_buyuk_mu else min(fiyatlar)
        kume = [p for p in fiyatlar if abs(p - capa) / capa <= tol]
        if len(kume) < min_deginme:
            return None
        return sum(kume) / len(kume)

    pozisyon = 0
    aktif_stop = aktif_hedef = None
    sonuc = np.full(n, np.nan)
    bekleyen = None  # {'seviye':float, 'baslangic':int}

    for i in range(n):
        if pozisyon == 1:
            if dusuk[i] <= aktif_stop or yuksek[i] >= aktif_hedef:
                pozisyon = 0
                aktif_stop = aktif_hedef = None

        if tepe_onay[i]:
            son_tepeler.append((i, yuksek[i]))
            son_tepeler[:] = [(j, p) for j, p in son_tepeler if i - j <= pencere]
        if dip_onay[i]:
            son_dipler.append((i, dusuk[i]))
            son_dipler[:] = [(j, p) for j, p in son_dipler if i - j <= pencere]

        if pozisyon == 0 and not np.isnan(a[i]) and a[i] > 0:
            destek = _gecerli_bolge(son_dipler, en_buyuk_mu=False)

            if bekleyen is None:
                if destek is not None and kapanis[i] < destek - kirilim_atr_kati * a[i]:
                    # asagi kirilim - LONG icin degil, sadece pozisyondan
                    # cikis anlamli (zaten pozisyon 0, bir sey yapmaya gerek yok)
                    pass
                elif destek is not None and kapanis[i] > destek + kirilim_atr_kati * a[i]:
                    bekleyen = {"seviye": destek, "baslangic": i}
            else:
                seviye = bekleyen["seviye"]
                gecersiz = kapanis[i] < seviye - kirilim_atr_kati * a[i]
                bar_araligi = max(yuksek[i] - dusuk[i], 1e-12)
                guclu_kapanis = (kapanis[i] - dusuk[i]) / bar_araligi >= toparlanma_govde_orani
                if gecersiz:
                    bekleyen = None
                elif dusuk[i] <= seviye + kirilim_atr_kati * a[i] and kapanis[i] > seviye \
                        and guclu_kapanis and kapanis[i] > acilis[i]:
                    pozisyon = 1
                    aktif_stop = seviye - stop_atr_tamponu * a[i]
                    risk = kapanis[i] - aktif_stop
                    aktif_hedef = kapanis[i] + hedef_r_kati * risk
                    bekleyen = None
                elif i - bekleyen["baslangic"] > maks_bekleme:
                    bekleyen = None

        sonuc[i] = float(pozisyon)

    return pd.Series(sonuc, index=df.index)


# ============================================================
#  2) TEPE/DIP STRATEJISI (rejime gore duzeltme alimi / donus)
# ============================================================
# ADX trendliyse "trend icinde duzeltmede alim", ADX yataysa "aralik
# ucundan donus". Trade-ajani'de 20 farkli 1sa sembolde dogrulandi.

def tepe_dip(df, sol=5, sag=5, pencere=150, tolerans_yuzde=0.15, min_deginme=2,
             maks_onay_bekleme=30, gecersizlik_atr_kati=2.0,
             hacim_periyot=20, hacim_kati=1.1, toparlanma_govde_orani=0.5,
             rsi_periyot=14, rsi_asiri_satim_yatay=40.0, rsi_asiri_satim_trend=55.0,
             atr_periyot=14, stop_atr_tamponu=0.3, adx_periyot=14, adx_trend_esigi=22.0,
             ema_trend_periyot=200, hedef_r_kati_trend=2.0, hedef_r_kati_yatay=1.2):
    """LONG tarafi: destek bolgesine deginme -> pencere icinde RSI'nin
    (rejime gore sig/derin) esige indigi VE momentumun (basit MACD
    histogram donusu) en az bir kez toparlandigi GORULMESI -> hacim
    teyitli toparlanma mumuyla giris."""
    yuksek = df["yuksek"].to_numpy()
    dusuk = df["dusuk"].to_numpy()
    acilis = df["acilis"].to_numpy()
    kapanis_s = df["kapanis"]
    kapanis = kapanis_s.to_numpy()
    hacim = df["hacim"].to_numpy()
    n = len(df)

    tepe_onay, dip_onay, _, _ = _swing_noktalari_basit(yuksek, dusuk, sol, sag)
    a = atr(df, atr_periyot).to_numpy()
    r = rsi(kapanis_s, rsi_periyot).to_numpy()
    hizli = kapanis_s.ewm(span=12, adjust=False).mean()
    yavas = kapanis_s.ewm(span=26, adjust=False).mean()
    macd_cizgi = hizli - yavas
    macd_sinyal = macd_cizgi.ewm(span=9, adjust=False).mean()
    hist = (macd_cizgi - macd_sinyal).to_numpy()
    ema_trend = kapanis_s.ewm(span=ema_trend_periyot, adjust=False).mean().to_numpy()
    hacim_ort = df["hacim"].rolling(hacim_periyot, min_periods=hacim_periyot).mean().to_numpy()

    # basit ADX (Trade-ajani'deki core/indicators.py'nin ayni mantigi)
    yukselis = df["yuksek"].diff()
    dusuk_fark = -df["dusuk"].diff()
    plus_dm = pd.Series(np.where((yukselis > dusuk_fark) & (yukselis > 0), yukselis, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((dusuk_fark > yukselis) & (dusuk_fark > 0), dusuk_fark, 0.0), index=df.index)
    tr = atr(df, 1) * 1.0
    plus_di = 100.0 * plus_dm.ewm(alpha=1 / adx_periyot, adjust=False).mean() / atr(df, adx_periyot).replace(0, np.nan)
    minus_di = 100.0 * minus_dm.ewm(alpha=1 / adx_periyot, adjust=False).mean() / atr(df, adx_periyot).replace(0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / adx_periyot, adjust=False).mean().to_numpy()

    son_dipler = []
    tol = tolerans_yuzde / 100.0

    def _gecerli_bolge(noktalar):
        if len(noktalar) < min_deginme:
            return None
        fiyatlar = [p for _, p in noktalar]
        capa = min(fiyatlar)
        kume = [p for p in fiyatlar if abs(p - capa) / capa <= tol]
        if len(kume) < min_deginme:
            return None
        return sum(kume) / len(kume)

    pozisyon = 0
    aktif_stop = aktif_hedef = None
    sonuc = np.full(n, np.nan)
    bekleyen = None

    isinma = max(ema_trend_periyot, hacim_periyot, adx_periyot, rsi_periyot) + 2

    for i in range(n):
        if pozisyon == 1:
            if dusuk[i] <= aktif_stop or yuksek[i] >= aktif_hedef:
                pozisyon = 0
                aktif_stop = aktif_hedef = None

        if dip_onay[i]:
            son_dipler.append((i, dusuk[i]))
            son_dipler[:] = [(j, p) for j, p in son_dipler if i - j <= pencere]

        if pozisyon == 0 and i >= isinma and not np.isnan(a[i]) and a[i] > 0:
            tampon = stop_atr_tamponu * a[i]
            if bekleyen is None:
                destek = _gecerli_bolge(son_dipler)
                if destek is not None and dusuk[i] <= destek + tampon:
                    bekleyen = {"seviye": destek, "baslangic": i, "en_dusuk_rsi": r[i], "momentum_gorulduu": False}
            else:
                seviye = bekleyen["seviye"]
                if not np.isnan(r[i]):
                    bekleyen["en_dusuk_rsi"] = min(bekleyen["en_dusuk_rsi"], r[i])
                if i >= 2 and hist[i] > hist[i - 1] <= hist[i - 2]:
                    bekleyen["momentum_gorulduu"] = True

                gecersiz = kapanis[i] < seviye - gecersizlik_atr_kati * a[i]
                bar_araligi = max(yuksek[i] - dusuk[i], 1e-12)
                toparlanma = (kapanis[i] - dusuk[i]) / bar_araligi >= toparlanma_govde_orani and kapanis[i] > acilis[i]
                hacim_teyit = not np.isnan(hacim_ort[i]) and hacim[i] >= hacim_kati * hacim_ort[i]
                trend_mi = not np.isnan(adx[i]) and adx[i] >= adx_trend_esigi
                yukselis_mi = kapanis[i] > ema_trend[i]
                rsi_uygun = (trend_mi and yukselis_mi and bekleyen["en_dusuk_rsi"] <= rsi_asiri_satim_trend) or \
                            ((not trend_mi) and bekleyen["en_dusuk_rsi"] <= rsi_asiri_satim_yatay)

                if gecersiz:
                    bekleyen = None
                elif toparlanma and hacim_teyit and bekleyen["momentum_gorulduu"] and rsi_uygun:
                    pozisyon = 1
                    aktif_stop = min(seviye, dusuk[i]) - tampon
                    risk = kapanis[i] - aktif_stop
                    r_kati = hedef_r_kati_trend if trend_mi else hedef_r_kati_yatay
                    aktif_hedef = kapanis[i] + r_kati * risk
                    bekleyen = None
                elif i - bekleyen["baslangic"] > maks_onay_bekleme:
                    bekleyen = None

        sonuc[i] = float(pozisyon)

    return pd.Series(sonuc, index=df.index)


# ============================================================
#  3) HACIM-FIYAT UYUMSUZLUGU (Wyckoff "efor vs sonuc" - absorbsiyon)
# ============================================================

def hacim_uyumsuzlugu(df, sol=5, sag=5, pencere=150, tolerans_yuzde=0.15, min_deginme=2,
                       maks_onay_bekleme=30, gecersizlik_atr_kati=2.0,
                       hacim_periyot=20, absorbsiyon_hacim_kati=1.2, absorbsiyon_aralik_kati=1.1,
                       atr_periyot=14, stop_atr_tamponu=0.3, hedef_r_kati=2.0):
    """LONG tarafi: destek bolgesinde, HACIM (efor) anormal yuksekken
    fiyat araligi (sonuc) ATR'a gore KUCUKSE bu bir "absorbsiyon" mumu -
    buyuk hacim satisi KARSI TARAF EMMIS demek. Bu mumun UCU KIRILIRSA
    (yon teyidi) giris tetiklenir."""
    yuksek = df["yuksek"].to_numpy()
    dusuk = df["dusuk"].to_numpy()
    kapanis = df["kapanis"].to_numpy()
    hacim = df["hacim"].to_numpy()
    n = len(df)

    tepe_onay, dip_onay, _, _ = _swing_noktalari_basit(yuksek, dusuk, sol, sag)
    a = atr(df, atr_periyot).to_numpy()
    hacim_ort = df["hacim"].rolling(hacim_periyot, min_periods=hacim_periyot).mean().to_numpy()

    son_dipler = []
    tol = tolerans_yuzde / 100.0

    def _gecerli_bolge(noktalar):
        if len(noktalar) < min_deginme:
            return None
        fiyatlar = [p for _, p in noktalar]
        capa = min(fiyatlar)
        kume = [p for p in fiyatlar if abs(p - capa) / capa <= tol]
        if len(kume) < min_deginme:
            return None
        return sum(kume) / len(kume)

    pozisyon = 0
    aktif_stop = aktif_hedef = None
    sonuc = np.full(n, np.nan)
    bekleyen = None
    isinma = max(hacim_periyot, atr_periyot) + 2

    for i in range(n):
        if pozisyon == 1:
            if dusuk[i] <= aktif_stop or yuksek[i] >= aktif_hedef:
                pozisyon = 0
                aktif_stop = aktif_hedef = None

        if dip_onay[i]:
            son_dipler.append((i, dusuk[i]))
            son_dipler[:] = [(j, p) for j, p in son_dipler if i - j <= pencere]

        if pozisyon == 0 and i >= isinma and not np.isnan(a[i]) and a[i] > 0 and not np.isnan(hacim_ort[i]):
            tampon = stop_atr_tamponu * a[i]
            hacim_orani = hacim[i] / hacim_ort[i] if hacim_ort[i] > 0 else 0.0
            aralik_orani = (yuksek[i] - dusuk[i]) / a[i]
            absorbsiyon_mumu = hacim_orani >= absorbsiyon_hacim_kati and aralik_orani <= absorbsiyon_aralik_kati

            if bekleyen is None:
                destek = _gecerli_bolge(son_dipler)
                if destek is not None and dusuk[i] <= destek + tampon:
                    bekleyen = {"seviye": destek, "baslangic": i, "gorulduu": False, "teyit_seviyesi": None}
            else:
                seviye = bekleyen["seviye"]
                gecersiz = kapanis[i] < seviye - gecersizlik_atr_kati * a[i]
                if gecersiz:
                    bekleyen = None
                else:
                    if absorbsiyon_mumu:
                        bekleyen["gorulduu"] = True
                        bekleyen["teyit_seviyesi"] = max(bekleyen["teyit_seviyesi"] or 0.0, yuksek[i])
                    if bekleyen["gorulduu"] and bekleyen["teyit_seviyesi"] is not None \
                            and kapanis[i] > bekleyen["teyit_seviyesi"]:
                        pozisyon = 1
                        aktif_stop = min(seviye, dusuk[i]) - tampon
                        risk = kapanis[i] - aktif_stop
                        aktif_hedef = kapanis[i] + hedef_r_kati * risk
                        bekleyen = None
                    elif i - bekleyen["baslangic"] > maks_onay_bekleme:
                        bekleyen = None

        sonuc[i] = float(pozisyon)

    return pd.Series(sonuc, index=df.index)


# ============================================================
#  4) MAJOR TREND SURUCUSU (buyuk/likit coinler icin - chandelier stop)
# ============================================================
# BTC/ETH/SOL/BNB gibi buyuk coinlerde, altcoin_stratejisi calismayinca
# Trade-ajani'de ozel gelistirildi: sabit hedef YOK, "candan" (chandelier)
# iz suren stopla trend surdukce tasi.

def major_trend_surucusu(df, kirilim_periyot=55, adx_periyot=14, adx_min=20.0,
                          hacim_periyot=20, hacim_kati=1.3, atr_periyot=14,
                          ema_trend_periyot=100, chandelier_kati=3.0):
    yuksek = df["yuksek"].to_numpy()
    dusuk = df["dusuk"].to_numpy()
    kapanis_s = df["kapanis"]
    kapanis = kapanis_s.to_numpy()
    hacim = df["hacim"].to_numpy()
    n = len(df)

    ust = df["yuksek"].shift(1).rolling(kirilim_periyot, min_periods=kirilim_periyot).max().to_numpy()
    a = atr(df, atr_periyot).to_numpy()
    ema_trend = kapanis_s.ewm(span=ema_trend_periyot, adjust=False).mean().to_numpy()
    hacim_ort = df["hacim"].rolling(hacim_periyot, min_periods=hacim_periyot).mean().to_numpy()

    yukselis = df["yuksek"].diff()
    dusuk_fark = -df["dusuk"].diff()
    plus_dm = pd.Series(np.where((yukselis > dusuk_fark) & (yukselis > 0), yukselis, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((dusuk_fark > yukselis) & (dusuk_fark > 0), dusuk_fark, 0.0), index=df.index)
    plus_di = 100.0 * plus_dm.ewm(alpha=1 / adx_periyot, adjust=False).mean() / atr(df, adx_periyot).replace(0, np.nan)
    minus_di = 100.0 * minus_dm.ewm(alpha=1 / adx_periyot, adjust=False).mean() / atr(df, adx_periyot).replace(0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / adx_periyot, adjust=False).mean().to_numpy()

    giris_long = (kapanis > ust) & (adx >= adx_min) & (hacim >= hacim_kati * hacim_ort) & (kapanis > ema_trend)

    pozisyon = 0
    en_yuksek_beri = None
    sonuc = np.full(n, np.nan)

    for i in range(n):
        if pozisyon == 1:
            en_yuksek_beri = max(en_yuksek_beri, yuksek[i])
            iz_stop = en_yuksek_beri - chandelier_kati * a[i]
            if kapanis[i] < iz_stop:
                pozisyon = 0

        if pozisyon == 0 and not np.isnan(a[i]) and a[i] > 0 and not np.isnan(giris_long[i]) and giris_long[i]:
            pozisyon = 1
            en_yuksek_beri = yuksek[i]

        sonuc[i] = float(pozisyon)

    return pd.Series(sonuc, index=df.index)


# ============================================================
#  TEST EDILECEK LISTE (stratejiler.py'deki STRATEJILER ile AYNI kalip)
# ============================================================

STRATEJILER = [
    ("Kirilim-GeriCekilme-Toparlanma", kirilim_geri_cekilme_toparlanma, {}),
    ("Tepe/Dip (rejim uyarlanabilir)", tepe_dip, {}),
    ("Hacim-Fiyat Uyumsuzlugu", hacim_uyumsuzlugu, {}),
    ("Major Trend Surucusu", major_trend_surucusu, {}),
]


def isinma_suresi(isim, parametreler):
    """stratejiler.py'deki AYNI fonksiyonun kopyasi - bu 4 strateji
    varsayilan olarak en genis pencereyi (major icin ema_trend_periyot=100,
    tepe_dip icin ema_trend_periyot=200) kullaniyor, guvenli tahmin 210."""
    return 210
