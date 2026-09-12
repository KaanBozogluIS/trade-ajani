r"""
GOSTERGELER  (teknik analiz hesaplari)
=======================================

TradingView'de en cok kullanilan tekniklerin hesap kismi. Bu dosya
SADECE MATEMATIK icerir -- cizim isini grafikler.py yapar.

Her fonksiyon bir pandas Series ya da DataFrame alir, hesaplanmis
degerleri dondurur. Hicbiri "al/sat" demez, sadece "sayi budur" der.
Yorumu kullaniciya birakiyoruz.

ONEMLI HATIRLATMA: Bu gostergelerin hicbiri gelecegi bilmez. Hepsi
GECMIS fiyattan hesaplanir ve fiyatin ARDINDAN gelir (gecikmelidirler).
Onceki turlarda test ettigimiz gibi (bkz. README.md), bu gostergelere
dayanan standart stratejilerin hicbiri rastgele karar vermekten
istatistiksel olarak ayirt edilemedi. Burada olmalari "populer olduklari
icin" -- "ise yaradiklari icin" degil.
"""

import numpy as np
import pandas as pd


# ============================================================
#  HAREKETLI ORTALAMALAR
# ============================================================

def ema(kapanis, periyot):
    """
    EMA (Exponential Moving Average) -- ustel hareketli ortalama.
    SMA'dan farki: son fiyatlara daha fazla agirlik verir, o yuzden
    fiyat degisimine SMA'dan daha hizli tepki verir.
    """
    return kapanis.ewm(span=periyot, adjust=False).mean()


# ============================================================
#  MACD
# ============================================================

def macd(kapanis, hizli=12, yavas=26, sinyal=9):
    """
    MACD (Moving Average Convergence Divergence).

    Iki EMA'nin farki (MACD cizgisi) ve o farkin kendi ortalamasi
    (sinyal cizgisi). Aradaki fark "histogram" olarak cizilir.

      MACD sinyali YUKARI keserse -> momentum yukselise donuyor olabilir
      MACD sinyali ASAGI keserse  -> momentum dususe donuyor olabilir

    Histogram buyudukce momentum guclendigini, kuculdukce zayifladigini
    gosterir -- fiyat henuz donmeden once.
    """
    h = ema(kapanis, hizli)
    y = ema(kapanis, yavas)
    macd_cizgisi = h - y
    sinyal_cizgisi = macd_cizgisi.ewm(span=sinyal, adjust=False).mean()
    histogram = macd_cizgisi - sinyal_cizgisi
    return macd_cizgisi, sinyal_cizgisi, histogram


# ============================================================
#  STOKASTIK OSILATOR
# ============================================================

def stokastik(df, k_periyot=14, k_yumusatma=3, d_periyot=3):
    """
    Stokastik Osilator -- fiyat, son <k_periyot> mumun araligina gore
    NEREDE duruyor (0-100 arasi)?

      100'e yakin -> son donemin ZIRVESINE yakin
        0'a yakin -> son donemin DIBINE yakin

    RSI'ya benzer okunur (80 uzeri asiri alim, 20 alti asiri satim
    sayilir) ama fiyatin kendisinden, kazanc/kayiptan degil, hesaplanir.
    %K hizli cizgi, %D onun ortalamasi (daha yavas, daha az yalanci
    sinyal verir).
    """
    en_dusuk = df["dusuk"].rolling(k_periyot).min()
    en_yuksek = df["yuksek"].rolling(k_periyot).max()
    aralik = (en_yuksek - en_dusuk).replace(0, np.nan)
    k_ham = 100 * (df["kapanis"] - en_dusuk) / aralik
    k = k_ham.rolling(k_yumusatma).mean()
    d = k.rolling(d_periyot).mean()
    return k, d


# ============================================================
#  VWAP
# ============================================================

def vwap(df):
    """
    VWAP (Volume Weighted Average Price) -- hacim agirlikli ortalama
    fiyat. Grafikte gorunen ilk mumdan itibaren biriktirilir ("ankorlu"
    VWAP). Kurumsal islemcilerin siklikla "adil fiyat" olarak kullandigi
    bir referans cizgisidir: fiyat VWAP'in uzerindeyse o donem ortalamaya
    gore pahali, altindaysa ucuz alinmis sayilir.

    NOT: Gercek borsalarda VWAP genelde HER GUN sifirdan baslar (seans
    ici). Burada grafige yuklenen mum sayisi kadar geriye gidip oradan
    itibaren biriktiriyoruz -- "bu ekrandaki mumlar boyunca ortalama
    fiyat" olarak okuyun.
    """
    tipik_fiyat = (df["yuksek"] + df["dusuk"] + df["kapanis"]) / 3
    hacim = df["hacim"].replace(0, np.nan)
    return (tipik_fiyat * hacim).cumsum() / hacim.cumsum()


# ============================================================
#  PARABOLIK SAR
# ============================================================

def parabolik_sar(df, baslangic_af=0.02, artis_af=0.02, azami_af=0.2):
    """
    Parabolic SAR (Stop And Reverse) -- fiyatin ustunde ya da altinda
    noktalar halinde cizilen bir trend takip gostergesi.

      Noktalar fiyatin ALTINDA -> yukselis trendi
      Noktalar fiyatin USTUNDE -> dusus trendi

    Nokta fiyata degdiginde (fiyat noktayi "kirdiginda") trend yon
    degistirir. Trend suresince noktalar fiyata dogru hizlanarak yaklasir
    (af = hizlanma katsayisi, her yeni zirve/dip ile biraz artar) --
    bu yuzden "parabolik" denir.

    Bu ADIM ADIM (iteratif) bir hesap oldugu icin vektorel yazilamaz;
    her mum bir onceki mumun sonucuna bagli.
    """
    yuksek = df["yuksek"].to_numpy()
    dusuk = df["dusuk"].to_numpy()
    n = len(df)
    sar = np.full(n, np.nan)
    if n < 3:
        return pd.Series(sar, index=df.index)

    yukselis = dusuk[1] >= dusuk[0]
    sar[0] = dusuk[0] if yukselis else yuksek[0]
    zirve_dip = yuksek[0] if yukselis else dusuk[0]
    af = baslangic_af

    for i in range(1, n):
        onceki_sar = sar[i - 1]
        yeni_sar = onceki_sar + af * (zirve_dip - onceki_sar)

        if yukselis:
            sinir1 = dusuk[i - 1]
            sinir2 = dusuk[i - 2] if i >= 2 else dusuk[i - 1]
            yeni_sar = min(yeni_sar, sinir1, sinir2)
            if dusuk[i] < yeni_sar:
                yukselis = False
                yeni_sar = zirve_dip
                zirve_dip = dusuk[i]
                af = baslangic_af
            elif yuksek[i] > zirve_dip:
                zirve_dip = yuksek[i]
                af = min(af + artis_af, azami_af)
        else:
            sinir1 = yuksek[i - 1]
            sinir2 = yuksek[i - 2] if i >= 2 else yuksek[i - 1]
            yeni_sar = max(yeni_sar, sinir1, sinir2)
            if yuksek[i] > yeni_sar:
                yukselis = True
                yeni_sar = zirve_dip
                zirve_dip = yuksek[i]
                af = baslangic_af
            elif dusuk[i] < zirve_dip:
                zirve_dip = dusuk[i]
                af = min(af + artis_af, azami_af)

        sar[i] = yeni_sar

    return pd.Series(sar, index=df.index)


# ============================================================
#  FIBONACCI GERI CEKILME SEVIYELERI
# ============================================================

FIB_ORANLAR = (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0)


def fibonacci_seviyeleri(df):
    """
    Ekrandaki mumların en yuksek ve en dusuk noktasi arasina standart
    Fibonacci oranlarinda yatay cizgiler yerlestirir.

    FIKIR (TradingView'de cok kullanilir): buyuk bir hareketten sonra
    fiyatin "geri cekilirken" sik sik bu oranlarda (ozellikle %38,2 ve
    %61,8) durdugu iddia edilir. Bu bir dogal yasa degil, sadece
    yeterince kisi bu seviyelere baktigi icin kendi kendini
    gerccekleştiren bir beklenti olabilir -- bilimsel kaniti zayiftir.

    Donen deger: [(oran, fiyat), ...] seklinde bir liste.
    """
    if df is None or len(df) < 2:
        return []
    zirve = float(df["yuksek"].max())
    dip = float(df["dusuk"].min())
    aralik = zirve - dip
    if aralik <= 0:
        return []
    return [(oran, zirve - oran * aralik) for oran in FIB_ORANLAR]
